"""Knowledge Transfer: capture, review and hand over critical institutional knowledge."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth import get_current_user
from app.db import get_db
from app.rbac import Role, require_workspace_role

router = APIRouter(prefix='/workspaces/{workspace_id}/knowledge-transfers', tags=['Knowledge Transfer'])

class TransferIn(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    knowledge_area: str = Field(min_length=2, max_length=120)
    procedure: str = Field(min_length=10, max_length=20000)
    criticality: Literal['low', 'medium', 'high'] = 'medium'
    source_document_id: str | None = None
    successor_id: str | None = None

class ReviewIn(BaseModel):
    status: Literal['draft', 'in_review', 'approved']
    review_note: str = Field(default='', max_length=1000)

def get_transfer(workspace_id: str, transfer_id: str):
    with get_db() as conn:
        row = conn.execute('SELECT * FROM knowledge_transfers WHERE id=? AND workspace_id=?', (transfer_id, workspace_id)).fetchone()
    if not row:
        raise HTTPException(404, 'سجل نقل المعرفة غير موجود')
    return dict(row)

def check_member(workspace_id: str, user_id: str):
    require_workspace_role(workspace_id, user_id, Role.VIEWER)

@router.post('', status_code=201)
def create_transfer(workspace_id: str, body: TransferIn, user=Depends(get_current_user)):
    require_workspace_role(workspace_id, user['id'], Role.EDITOR)
    with get_db() as conn:
        if body.source_document_id:
            doc = conn.execute('SELECT id FROM documents WHERE id=? AND workspace_id=?', (body.source_document_id, workspace_id)).fetchone()
            if not doc:
                raise HTTPException(400, 'المستند المرجعي ليس في مساحة العمل')
            # A document can have user-specific access restrictions; do not expose its contents here.
        if body.successor_id:
            member = conn.execute('SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?', (workspace_id, body.successor_id)).fetchone()
            if not member:
                raise HTTPException(400, 'المستلم ليس عضواً في مساحة العمل')
        transfer_id = str(uuid.uuid4())
        conn.execute('''INSERT INTO knowledge_transfers
            (id,workspace_id,title,knowledge_area,procedure,criticality,source_document_id,owner_id,successor_id)
            VALUES (?,?,?,?,?,?,?,?,?)''', (transfer_id,workspace_id,body.title,body.knowledge_area,body.procedure,body.criticality,body.source_document_id,user['id'],body.successor_id))
    return get_transfer(workspace_id, transfer_id)

@router.get('')
def list_transfers(workspace_id: str, user=Depends(get_current_user)):
    check_member(workspace_id, user['id'])
    with get_db() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM knowledge_transfers WHERE workspace_id=? ORDER BY created_at DESC,id', (workspace_id,)).fetchall()]

@router.get('/risk-summary')
def risk_summary(workspace_id: str, user=Depends(get_current_user)):
    check_member(workspace_id, user['id'])
    with get_db() as conn:
        rows = conn.execute('SELECT criticality,status,successor_id FROM knowledge_transfers WHERE workspace_id=?', (workspace_id,)).fetchall()
    return {'total':len(rows), 'high_priority_unapproved':sum(r['criticality']=='high' and r['status']!='approved' for r in rows), 'without_successor':sum(not r['successor_id'] for r in rows), 'approved':sum(r['status']=='approved' for r in rows), 'note':'مؤشرات مبنية على السجلات المدخلة فقط، وليست تقييماً شاملاً لمخاطر المؤسسة.'}

@router.get('/{transfer_id}')
def read_transfer(workspace_id: str, transfer_id: str, user=Depends(get_current_user)):
    check_member(workspace_id, user['id'])
    return get_transfer(workspace_id, transfer_id)

@router.patch('/{transfer_id}/review')
def review_transfer(workspace_id: str, transfer_id: str, body: ReviewIn, user=Depends(get_current_user)):
    require_workspace_role(workspace_id, user['id'], Role.ADMIN if body.status=='approved' else Role.EDITOR)
    current = get_transfer(workspace_id, transfer_id)
    if current['status']=='approved':
        raise HTTPException(409, 'سجل نقل المعرفة المعتمد مقفل ولا يمكن تعديل حالته')
    if body.status=='approved' and not current['successor_id']:
        raise HTTPException(400, 'لا يمكن اعتماد نقل المعرفة بدون تحديد مستلم')
    if body.status=='approved':
        with get_db() as conn:
            member=conn.execute('SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?',
                                (workspace_id,current['successor_id'])).fetchone()
            if not member:
                raise HTTPException(400, 'المستلم لم يعد عضواً في مساحة العمل')
    with get_db() as conn:
        conn.execute('UPDATE knowledge_transfers SET status=?,review_note=?,reviewed_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND workspace_id=?', (body.status,body.review_note,user['id'],transfer_id,workspace_id))
    return get_transfer(workspace_id, transfer_id)
