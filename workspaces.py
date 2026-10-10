import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from app.db import get_db
from app.auth import get_current_user
from app.rbac import Role, require_workspace_role
from app.schemas import (
    WorkspaceCreate, WorkspaceOut,
    WorkspaceMemberAdd, WorkspaceMemberUpdate, WorkspaceMemberOut
)

router = APIRouter(prefix="/workspaces", tags=["مساحات العمل وإدارة الأعضاء (Workspaces & RBAC)"])

@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(ws_in: WorkspaceCreate, current_user: dict = Depends(get_current_user)):
    ws_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())
    user_id = current_user["id"]
    slug_clean = ws_in.slug.lower().strip()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM workspaces WHERE slug = ?", (slug_clean,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="المعرف الفريد (slug) مستخدم بالفعل، يرجى اختيار اسم آخر"
            )
        
        cursor.execute(
            "INSERT INTO workspaces (id, name, slug, description, created_by) VALUES (?, ?, ?, ?, ?)",
            (ws_id, ws_in.name.strip(), slug_clean, ws_in.description.strip(), user_id)
        )
        
        # Creator is automatically the OWNER
        cursor.execute(
            "INSERT INTO workspace_members (id, workspace_id, user_id, role) VALUES (?, ?, ?, ?)",
            (member_id, ws_id, user_id, Role.OWNER.value)
        )
        
        cursor.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,))
        row = dict(cursor.fetchone())
        row["current_user_role"] = Role.OWNER.value
        return row

@router.get("", response_model=List[WorkspaceOut])
def list_my_workspaces(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT w.*, wm.role as current_user_role
            FROM workspaces w
            INNER JOIN workspace_members wm ON w.id = wm.workspace_id
            WHERE wm.user_id = ?
            ORDER BY w.created_at DESC
        """, (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        return rows

@router.get("/{id}", response_model=WorkspaceOut)
def get_workspace(id: str, current_user: dict = Depends(get_current_user)):
    membership = require_workspace_role(id, current_user["id"], Role.GUEST)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workspaces WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مساحة العمل غير موجودة")
        ws_dict = dict(row)
        ws_dict["current_user_role"] = membership["role"]
        return ws_dict

@router.post("/{id}/members", response_model=WorkspaceMemberOut, status_code=status.HTTP_201_CREATED)
def add_workspace_member(id: str, member_in: WorkspaceMemberAdd, current_user: dict = Depends(get_current_user)):
    # Requires ADMIN or OWNER role
    require_workspace_role(id, current_user["id"], Role.ADMIN)
    
    role_requested = member_in.role.lower().strip()
    valid_roles = [r.value for r in Role]
    if role_requested not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"الدور غير صالح. الأدوار المتاحة: {', '.join(valid_roles)}"
        )
    
    with get_db() as conn:
        cursor = conn.cursor()
        # Find target user by email
        cursor.execute("SELECT id, email, full_name FROM users WHERE email = ?", (member_in.email.lower().strip(),))
        target_user = cursor.fetchone()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="المستخدم المراد إضافته غير مسجل في النظام"
            )
        
        target_user_id = target_user["id"]
        # Check if already a member
        cursor.execute(
            "SELECT id FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (id, target_user_id)
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="المستخدم عضو بالفعل في مساحة العمل"
            )
            
        new_member_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO workspace_members (id, workspace_id, user_id, role) VALUES (?, ?, ?, ?)",
            (new_member_id, id, target_user_id, role_requested)
        )
        
        cursor.execute("""
            SELECT wm.id, wm.workspace_id, wm.user_id, wm.role, wm.joined_at, u.email, u.full_name
            FROM workspace_members wm
            JOIN users u ON wm.user_id = u.id
            WHERE wm.id = ?
        """, (new_member_id,))
        return dict(cursor.fetchone())

@router.get("/{id}/members", response_model=List[WorkspaceMemberOut])
def list_workspace_members(id: str, current_user: dict = Depends(get_current_user)):
    require_workspace_role(id, current_user["id"], Role.VIEWER)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT wm.id, wm.workspace_id, wm.user_id, wm.role, wm.joined_at, u.email, u.full_name
            FROM workspace_members wm
            JOIN users u ON wm.user_id = u.id
            WHERE wm.workspace_id = ?
            ORDER BY wm.joined_at ASC
        """, (id,))
        return [dict(r) for r in cursor.fetchall()]

@router.patch("/{id}/members/{user_id}", response_model=WorkspaceMemberOut)
def update_member_role(
    id: str, user_id: str, role_update: WorkspaceMemberUpdate, current_user: dict = Depends(get_current_user)
):
    current_mem = require_workspace_role(id, current_user["id"], Role.ADMIN)
    new_role = role_update.role.lower().strip()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?", (id, user_id))
        target_mem = cursor.fetchone()
        if not target_mem:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="العضو غير موجود في مساحة العمل")
        
        # Only Owner can demote an Owner or grant Owner role
        if (target_mem["role"] == Role.OWNER.value or new_role == Role.OWNER.value) and current_mem["role"] != Role.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="فقط مالك مساحة العمل يمكنه تعديل صلاحيات المالك"
            )
            
        cursor.execute(
            "UPDATE workspace_members SET role = ? WHERE workspace_id = ? AND user_id = ?",
            (new_role, id, user_id)
        )
        
        cursor.execute("""
            SELECT wm.id, wm.workspace_id, wm.user_id, wm.role, wm.joined_at, u.email, u.full_name
            FROM workspace_members wm
            JOIN users u ON wm.user_id = u.id
            WHERE wm.workspace_id = ? AND wm.user_id = ?
        """, (id, user_id))
        return dict(cursor.fetchone())

@router.delete("/{id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(id: str, user_id: str, current_user: dict = Depends(get_current_user)):
    current_mem = require_workspace_role(id, current_user["id"], Role.ADMIN)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?", (id, user_id))
        target_mem = cursor.fetchone()
        if not target_mem:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="العضو غير موجود في مساحة العمل")
        
        if target_mem["role"] == Role.OWNER.value:
            # Check if there are other owners
            cursor.execute(
                "SELECT COUNT(*) as count FROM workspace_members WHERE workspace_id = ? AND role = 'owner'",
                (id,)
            )
            if cursor.fetchone()["count"] <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="لا يمكن إزالة المالك الوحيد لمساحة العمل"
                )
                
        cursor.execute("DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?", (id, user_id))
