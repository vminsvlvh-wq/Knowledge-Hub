from enum import Enum
from fastapi import HTTPException, status
from app.db import get_db

class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    GUEST = "guest"

ROLE_WEIGHTS = {
    Role.OWNER.value: 50,
    Role.ADMIN.value: 40,
    Role.EDITOR.value: 30,
    Role.VIEWER.value: 20,
    Role.GUEST.value: 10,
}

def get_workspace_membership(workspace_id: str, user_id: str) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT wm.id, wm.workspace_id, wm.user_id, wm.role, wm.joined_at
            FROM workspace_members wm
            JOIN workspaces w ON w.id = wm.workspace_id
            JOIN tenant_memberships tm ON tm.tenant_id = w.tenant_id AND tm.user_id = wm.user_id
            WHERE wm.workspace_id = ? AND wm.user_id = ?
        """, (workspace_id, user_id))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ليس لديك حق الوصول إلى مساحة العمل هذه"
            )
        return dict(row)

def require_workspace_role(workspace_id: str, user_id: str, min_role: Role) -> dict:
    membership = get_workspace_membership(workspace_id, user_id)
    user_role = membership["role"]
    if ROLE_WEIGHTS.get(user_role, 0) < ROLE_WEIGHTS[min_role.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"العملية تتطلب صلاحية بمستوى {min_role.value} على الأقل (دورك الحالي: {user_role})"
        )
    return membership

def check_document_access(document_id: str, user_id: str, required_permission: str = "view") -> dict:
    """
    Checks if user can view/edit/administer a document based on:
    1. Workspace role (Owner/Admin have full access; Editor has edit/view; Viewer has view).
    2. Document-specific permission overrides in document_permissions.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        # Fetch document and workspace
        cursor.execute("""
            SELECT d.*, w.tenant_id
            FROM documents d JOIN workspaces w ON w.id = d.workspace_id
            WHERE d.id = ?
        """, (document_id,))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المستند غير موجود")
        doc_dict = dict(doc)
        
        workspace_id = doc_dict["workspace_id"]
        
        # Tenant membership is a mandatory boundary, including direct document grants.
        cursor.execute(
            "SELECT id FROM tenant_memberships WHERE tenant_id = ? AND user_id = ?",
            (doc_dict["tenant_id"], user_id)
        )
        tenant_mem = cursor.fetchone()
        if not tenant_mem:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="ليس لديك عضوية في المؤسسة المالكة لهذا المستند")

        cursor.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id)
        )
        mem = cursor.fetchone()
        ws_role = mem["role"] if mem else None
        
        # Check direct document permission
        cursor.execute(
            "SELECT permission FROM document_permissions WHERE document_id = ? AND user_id = ?",
            (document_id, user_id)
        )
        doc_perm_row = cursor.fetchone()
        direct_perm = doc_perm_row["permission"] if doc_perm_row else None
        
        # Admin / Owner of workspace have full control
        if ws_role in (Role.OWNER.value, Role.ADMIN.value) or direct_perm == "admin":
            return doc_dict
        
        # Edit requirement
        if required_permission in ("edit", "collaborate"):
            if ws_role == Role.EDITOR.value or direct_perm in ("edit", "admin"):
                return doc_dict
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ليس لديك صلاحية تعديل هذا المستند"
            )
        
        # View requirement
        if required_permission == "view":
            if ws_role in (Role.EDITOR.value, Role.VIEWER.value) or direct_perm in ("view", "edit", "admin"):
                return doc_dict
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ليس لديك صلاحية قراءة هذا المستند"
            )
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="صلاحية وصول غير مصرح بها"
        )
