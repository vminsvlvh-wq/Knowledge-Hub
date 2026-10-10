"""Skills Intelligence MVP: self-reported skills, role targets and privacy-aware aggregates.

No skills are inferred from employee documents and this is not a personnel rating system.
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from app.auth import get_current_user
from app.db import get_db
from app.rbac import Role, require_workspace_role

router = APIRouter(prefix='/workspaces/{workspace_id}/skills', tags=['Skills Intelligence'])
MIN_AGGREGATE_GROUP = 3


class SkillAssessmentIn(BaseModel):
    skill_name: str = Field(min_length=2, max_length=100)
    level: int = Field(ge=0, le=5)
    evidence_note: str = Field(default='', max_length=500)

    @field_validator('skill_name')
    @classmethod
    def clean_skill(cls, value):
        clean = value.strip()
        if len(clean) < 2:
            raise ValueError('minimum 2 non-space characters')
        return clean


class MyProfileIn(BaseModel):
    role_name: str = Field(min_length=2, max_length=120)
    skills: List[SkillAssessmentIn] = Field(default_factory=list, max_length=75)

    @field_validator('role_name')
    @classmethod
    def clean_role(cls, value):
        clean = value.strip()
        if len(clean) < 2:
            raise ValueError('minimum 2 non-space characters')
        return clean


class RequirementIn(BaseModel):
    role_name: str = Field(min_length=2, max_length=120)
    skill_name: str = Field(min_length=2, max_length=100)
    target_level: int = Field(ge=1, le=5)

    @field_validator('role_name', 'skill_name')
    @classmethod
    def clean_string(cls, value):
        clean = value.strip()
        if len(clean) < 2:
            raise ValueError('minimum 2 non-space characters')
        return clean


def _get_requirements(conn, workspace_id: str, role_name: str):
    return [dict(x) for x in conn.execute(
        'SELECT id,role_name,skill_name,target_level FROM role_skill_requirements '
        'WHERE workspace_id=? AND role_name=? ORDER BY skill_name', (workspace_id, role_name)
    ).fetchall()]


def _get_profile(conn, workspace_id: str, user_id: str):
    row = conn.execute('SELECT role_name,updated_at FROM skill_profiles WHERE workspace_id=? AND user_id=?',
                       (workspace_id, user_id)).fetchone()
    if not row:
        return {'role_name': '', 'updated_at': None, 'skills': [], 'source': 'self_reported'}
    skills = [dict(x) for x in conn.execute(
        'SELECT skill_name,level,evidence_note FROM skill_assessments WHERE workspace_id=? AND user_id=? ORDER BY skill_name',
        (workspace_id, user_id)).fetchall()]
    return {'role_name': row['role_name'], 'updated_at': row['updated_at'],
            'skills': skills, 'source': 'self_reported'}


@router.get('/requirements')
def list_requirements(workspace_id: str, user=Depends(get_current_user)):
    require_workspace_role(workspace_id, user['id'], Role.VIEWER)
    with get_db() as conn:
        return [dict(x) for x in conn.execute(
            'SELECT id,role_name,skill_name,target_level FROM role_skill_requirements WHERE workspace_id=? '
            'ORDER BY role_name,skill_name', (workspace_id,)).fetchall()]


@router.post('/requirements', status_code=201)
def upsert_requirement(workspace_id: str, body: RequirementIn, user=Depends(get_current_user)):
    require_workspace_role(workspace_id, user['id'], Role.ADMIN)
    with get_db() as conn:
        existing = conn.execute('SELECT id FROM role_skill_requirements WHERE workspace_id=? AND role_name=? AND skill_name=?',
                                (workspace_id, body.role_name, body.skill_name)).fetchone()
        if existing:
            rid = existing['id']
            conn.execute('UPDATE role_skill_requirements SET target_level=? WHERE id=?', (body.target_level, rid))
        else:
            rid = str(uuid.uuid4())
            conn.execute('INSERT INTO role_skill_requirements (id,workspace_id,role_name,skill_name,target_level) VALUES (?,?,?,?,?)',
                         (rid, workspace_id, body.role_name, body.skill_name, body.target_level))
    return {'id': rid, **body.model_dump()}


@router.delete('/requirements/{requirement_id}', status_code=204)
def delete_requirement(workspace_id: str, requirement_id: str, user=Depends(get_current_user)):
    require_workspace_role(workspace_id, user['id'], Role.ADMIN)
    with get_db() as conn:
        result = conn.execute('DELETE FROM role_skill_requirements WHERE workspace_id=? AND id=?', (workspace_id, requirement_id))
        if result.rowcount == 0:
            raise HTTPException(404, 'متطلب المهارة غير موجود')


@router.get('/my-profile')
def my_profile(workspace_id: str, user=Depends(get_current_user)):
    require_workspace_role(workspace_id, user['id'], Role.VIEWER)
    with get_db() as conn:
        return _get_profile(conn, workspace_id, user['id'])


@router.put('/my-profile')
def save_profile(workspace_id: str, body: MyProfileIn, user=Depends(get_current_user)):
    require_workspace_role(workspace_id, user['id'], Role.VIEWER)
    names = [x.skill_name.casefold() for x in body.skills]
    if len(names) != len(set(names)):
        raise HTTPException(400, 'لا يمكن تكرار نفس المهارة في التقييم')
    with get_db() as conn:
        conn.execute('''INSERT INTO skill_profiles (workspace_id,user_id,role_name)
          VALUES (?,?,?) ON CONFLICT(workspace_id,user_id)
          DO UPDATE SET role_name=excluded.role_name,updated_at=CURRENT_TIMESTAMP''',
          (workspace_id, user['id'], body.role_name))
        # Replace only this employee's self-reported skills, in one transaction.
        conn.execute('DELETE FROM skill_assessments WHERE workspace_id=? AND user_id=?',
                     (workspace_id, user['id']))
        for skill in body.skills:
            conn.execute('''INSERT INTO skill_assessments
              (id,workspace_id,user_id,skill_name,level,evidence_note)
              VALUES (?,?,?,?,?,?)''',
              (str(uuid.uuid4()), workspace_id, user['id'], skill.skill_name,
               skill.level, skill.evidence_note))
        return _get_profile(conn, workspace_id, user['id'])


@router.get('/my-gap')
def my_gap(workspace_id: str, user=Depends(get_current_user)):
    require_workspace_role(workspace_id, user['id'], Role.VIEWER)
    with get_db() as conn:
        profile = _get_profile(conn, workspace_id, user['id'])
        reqs = _get_requirements(conn, workspace_id, profile['role_name']) if profile['role_name'] else []
    assessed = {x['skill_name'].casefold(): x['level'] for x in profile['skills']}
    gaps = []
    for req in reqs:
        level = assessed.get(req['skill_name'].casefold())
        gap = max(0, req['target_level'] - level) if level is not None else None
        gaps.append({'skill_name':req['skill_name'], 'target_level':req['target_level'],
                     'current_level':level,'gap':gap,
                     'status':'unassessed' if level is None else ('below_target' if gap else 'meets_target')})
    return {'role_name': profile['role_name'], 'source':'self_reported', 'gaps':gaps,
            'note':'هذه مقارنة إرشادية لتقييم الموظف الذاتي؛ المهارة غير المقيمة ليست مهارة مفقودة.'}


@router.get('/gap-summary')
def gap_summary(workspace_id: str, role_name: str = '', user=Depends(get_current_user)):
    require_workspace_role(workspace_id, user['id'], Role.ADMIN)
    with get_db() as conn:
        roles = [x['role_name'] for x in conn.execute('''SELECT DISTINCT role_name FROM role_skill_requirements
                 WHERE workspace_id=? ORDER BY role_name''', (workspace_id,)).fetchall()]
        if role_name:
            roles = [r for r in roles if r == role_name]
        groups = []
        for role in roles:
            users = conn.execute('SELECT user_id FROM skill_profiles WHERE workspace_id=? AND role_name=? '
                                 'AND user_id IN (SELECT user_id FROM workspace_members WHERE workspace_id=?)',
                                 (workspace_id,role,workspace_id)).fetchall()
            n = len(users)
            if n < MIN_AGGREGATE_GROUP:
                groups.append({'role_name':role,'suppressed':True,'reason':'insufficient_group_size',
                               'minimum_group_size':MIN_AGGREGATE_GROUP})
                continue
            requirements = _get_requirements(conn, workspace_id, role)
            user_ids = [u['user_id'] for u in users]
            placeholders = ','.join('?' for _ in user_ids)
            assessments = conn.execute(f'''SELECT user_id,skill_name,level FROM skill_assessments
               WHERE workspace_id=? AND user_id IN ({placeholders})''', [workspace_id]+user_ids).fetchall()
            levels = {(r['user_id'],r['skill_name'].casefold()):r['level'] for r in assessments}
            summary = []
            for req in requirements:
                vals=[levels.get((uid,req['skill_name'].casefold())) for uid in user_ids]
                observed=[x for x in vals if x is not None]
                if len(observed) < MIN_AGGREGATE_GROUP:
                    summary.append({'skill_name':req['skill_name'], 'suppressed':True,
                                    'reason':'insufficient_assessments'})
                    continue
                summary.append({'skill_name':req['skill_name'], 'suppressed':False, 'target_level':req['target_level'],
                                'assessed':len(observed), 'unassessed':n-len(observed),
                                'below_target':sum(x < req['target_level'] for x in observed),
                                'meets_target':sum(x >= req['target_level'] for x in observed)})
            groups.append({'role_name':role,'suppressed':False,'profile_count':n,'skills':summary})
    return {'groups':groups,'source':'self_reported',
            'note':'مجاميع مبنية على التقييم الذاتي، ولا تستخدم لترتيب الموظفين أو اتخاذ قرارات توظيف تلقائية.'}
