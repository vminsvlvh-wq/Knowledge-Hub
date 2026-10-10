import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from app.db import (
    get_db, index_document, semantic_search,
    rag_generate_answer, summarize_document
)
from app.auth import get_current_user
from app.rbac import Role, require_workspace_role, check_document_access
from app.schemas import (
    DocumentCreate, DocumentUpdate, DocumentOut,
    DocumentNode, DocumentPermissionAdd, DocumentVersionOut,
    AISearchRequest, AISearchResponse, AIAskRequest,
    AIAskResponse, AISummarizeResponse
)

router = APIRouter(tags=["إدارة المستندات والذكاء الاصطناعي (Documents & AI RAG)"])

def build_tree(items: List[dict], parent_id=None) -> List[DocumentNode]:
    branch = []
    for item in items:
        if item.get("parent_id") == parent_id:
            children = build_tree(items, item["id"])
            node = DocumentNode(
                id=item["id"],
                workspace_id=item["workspace_id"],
                parent_id=item["parent_id"],
                title=item["title"],
                content_type=item["content_type"],
                is_archived=bool(item["is_archived"]),
                children=children
            )
            branch.append(node)
    return branch

def get_user_accessible_document_ids(workspace_id: str, user_id: str) -> List[str]:
    """
    Returns document IDs the user is permitted to view:
    - Workspace Owner/Admin/Editor/Viewer have access to all active workspace documents.
    - Workspace Guest only has access to documents explicitly granted in document_permissions.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id)
        )
        mem = cursor.fetchone()
        if not mem:
            return []
        
        user_role = mem["role"]
        if user_role in (Role.OWNER.value, Role.ADMIN.value, Role.EDITOR.value, Role.VIEWER.value):
            cursor.execute(
                "SELECT id FROM documents WHERE workspace_id = ? AND is_archived = 0",
                (workspace_id,)
            )
            return [r["id"] for r in cursor.fetchall()]
        
        elif user_role == Role.GUEST.value:
            cursor.execute("""
                SELECT d.id FROM documents d
                JOIN document_permissions dp ON d.id = dp.document_id
                WHERE d.workspace_id = ? AND dp.user_id = ? AND d.is_archived = 0
            """, (workspace_id, user_id))
            return [r["id"] for r in cursor.fetchall()]
            
    return []

# --- Document Management Endpoints ---

@router.post("/workspaces/{workspace_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(workspace_id: str, doc_in: DocumentCreate, current_user: dict = Depends(get_current_user)):
    require_workspace_role(workspace_id, current_user["id"], Role.EDITOR)
    
    doc_id = str(uuid.uuid4())
    user_id = current_user["id"]
    
    with get_db() as conn:
        cursor = conn.cursor()
        if doc_in.parent_id:
            cursor.execute(
                "SELECT id FROM documents WHERE id = ? AND workspace_id = ?",
                (doc_in.parent_id, workspace_id)
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="المستند الأب المحدد غير موجود في مساحة العمل هذه"
                )
                
        cursor.execute("""
            INSERT INTO documents (id, workspace_id, parent_id, title, content, content_type, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id, workspace_id, doc_in.parent_id,
            doc_in.title.strip(), doc_in.content or "",
            doc_in.content_type or "markdown", user_id
        ))
        
        # Save initial version 1
        version_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO document_versions (id, document_id, version_number, content, change_summary, created_by)
            VALUES (?, ?, 1, ?, 'النسخة المبدئية', ?)
        """, (version_id, doc_id, doc_in.content or "", user_id))
        
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = dict(cursor.fetchone())
        row["is_archived"] = bool(row["is_archived"])

    # Auto-index into vector store
    index_document(doc_id, workspace_id, doc_in.content or "")
    return row

@router.get("/workspaces/{workspace_id}/documents", response_model=List[DocumentNode])
def list_workspace_documents_tree(workspace_id: str, current_user: dict = Depends(get_current_user)):
    require_workspace_role(workspace_id, current_user["id"], Role.VIEWER)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, workspace_id, parent_id, title, content_type, is_archived
            FROM documents
            WHERE workspace_id = ? AND is_archived = 0
            ORDER BY created_at ASC
        """, (workspace_id,))
        docs = [dict(r) for r in cursor.fetchall()]
        return build_tree(docs, parent_id=None)

@router.get("/documents/{id}", response_model=DocumentOut)
def get_document(id: str, current_user: dict = Depends(get_current_user)):
    doc = check_document_access(id, current_user["id"], required_permission="view")
    doc["is_archived"] = bool(doc["is_archived"])
    return doc

@router.put("/documents/{id}", response_model=DocumentOut)
def update_document(id: str, doc_update: DocumentUpdate, current_user: dict = Depends(get_current_user)):
    doc = check_document_access(id, current_user["id"], required_permission="edit")
    user_id = current_user["id"]
    
    new_title = doc_update.title if doc_update.title is not None else doc["title"]
    new_content = doc_update.content if doc_update.content is not None else doc["content"]
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE documents
            SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_title, new_content, id))
        
        if doc_update.content is not None and doc_update.content != doc["content"]:
            cursor.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_ver FROM document_versions WHERE document_id = ?",
                (id,)
            )
            next_version = cursor.fetchone()["next_ver"]
            version_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO document_versions (id, document_id, version_number, content, change_summary, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (version_id, id, next_version, new_content, doc_update.change_summary or "تعديل المستند", user_id))
            
        cursor.execute("SELECT * FROM documents WHERE id = ?", (id,))
        res = dict(cursor.fetchone())
        res["is_archived"] = bool(res["is_archived"])

    # Update AI vector index if content changed
    if doc_update.content is not None:
        index_document(id, doc["workspace_id"], new_content)

    return res

@router.delete("/documents/{id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_document(id: str, current_user: dict = Depends(get_current_user)):
    check_document_access(id, current_user["id"], required_permission="edit")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE documents SET is_archived = 1 WHERE id = ?", (id,))

@router.get("/documents/{id}/versions", response_model=List[DocumentVersionOut])
def get_document_versions(id: str, current_user: dict = Depends(get_current_user)):
    check_document_access(id, current_user["id"], required_permission="view")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, document_id, version_number, content, change_summary, created_by, created_at
            FROM document_versions
            WHERE document_id = ?
            ORDER BY version_number DESC
        """, (id,))
        return [dict(r) for r in cursor.fetchall()]

@router.post("/documents/{id}/permissions", status_code=status.HTTP_201_CREATED)
def assign_document_permission(id: str, perm_in: DocumentPermissionAdd, current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT workspace_id FROM documents WHERE id = ?", (id,))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المستند غير موجود")
        ws_id = doc["workspace_id"]
        
    require_workspace_role(ws_id, current_user["id"], Role.ADMIN)
    
    perm_val = perm_in.permission.lower().strip()
    if perm_val not in ("view", "edit", "admin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="نوع الصلاحية يجب أن يكون view أو edit أو admin")
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (perm_in.email.lower().strip(),))
        target_user = cursor.fetchone()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المستخدم المحدد غير موجود")
        
        target_uid = target_user["id"]
        perm_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO document_permissions (id, document_id, user_id, permission)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(document_id, user_id) DO UPDATE SET permission = excluded.permission
        """, (perm_id, id, target_uid, perm_val))
        
    return {"message": "تم تعيين الصلاحية بنجاح", "document_id": id, "user_id": target_uid, "permission": perm_val}

# --- AI & RAG Endpoints ---

@router.post("/workspaces/{workspace_id}/ai/search", response_model=AISearchResponse)
def workspace_semantic_search(
    workspace_id: str,
    req: AISearchRequest,
    current_user: dict = Depends(get_current_user)
):
    require_workspace_role(workspace_id, current_user["id"], Role.GUEST)
    allowed_doc_ids = get_user_accessible_document_ids(workspace_id, current_user["id"])
    
    results = semantic_search(
        workspace_id=workspace_id,
        query=req.query,
        allowed_document_ids=allowed_doc_ids,
        top_k=req.top_k
    )
    
    return {
        "query": req.query,
        "total_results": len(results),
        "results": results
    }

@router.post("/workspaces/{workspace_id}/ai/ask", response_model=AIAskResponse)
def workspace_rag_ask(
    workspace_id: str,
    req: AIAskRequest,
    current_user: dict = Depends(get_current_user)
):
    require_workspace_role(workspace_id, current_user["id"], Role.GUEST)
    allowed_doc_ids = get_user_accessible_document_ids(workspace_id, current_user["id"])
    
    rag_result = rag_generate_answer(
        workspace_id=workspace_id,
        query=req.query,
        allowed_document_ids=allowed_doc_ids,
        top_k=req.top_k
    )
    
    return rag_result

@router.post("/documents/{document_id}/ai/summarize", response_model=AISummarizeResponse)
def document_ai_summarize(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    doc = check_document_access(document_id, current_user["id"], required_permission="view")
    summary_data = summarize_document(doc["title"], doc["content"] or "")
    
    return {
        "document_id": document_id,
        "title": summary_data["title"],
        "summary": summary_data["summary"],
        "key_takeaways": summary_data["key_takeaways"],
        "word_count": summary_data["word_count"]
    }
