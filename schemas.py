from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: Any = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=2000)


class WorkspaceOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str = ""
    created_by: str
    created_at: Any = None
    tenant_id: Optional[str] = None
    current_user_role: Optional[str] = None


class WorkspaceMemberAdd(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    role: str = "viewer"


class WorkspaceMemberUpdate(BaseModel):
    role: str = Field(min_length=3, max_length=20)


class WorkspaceMemberOut(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: str
    joined_at: Any = None
    email: Optional[str] = None
    full_name: Optional[str] = None


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = ""
    content_type: str = "markdown"
    parent_id: Optional[str] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    content: Optional[str] = None
    change_summary: Optional[str] = Field(default="", max_length=1000)


class DocumentOut(BaseModel):
    id: str
    workspace_id: str
    parent_id: Optional[str] = None
    title: str
    content: str = ""
    content_type: str = "markdown"
    is_archived: bool = False
    created_by: str
    created_at: Any = None
    updated_at: Any = None


class DocumentNode(BaseModel):
    id: str
    workspace_id: str
    parent_id: Optional[str] = None
    title: str
    content_type: str = "markdown"
    is_archived: bool = False
    children: List["DocumentNode"] = Field(default_factory=list)


DocumentNode.model_rebuild()


class DocumentPermissionAdd(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    permission: str = "view"


class DocumentVersionOut(BaseModel):
    id: str
    document_id: str
    version_number: int
    content: str
    change_summary: str = ""
    created_by: str
    created_at: Any = None


class AISearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=30)


class AISearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[Dict[str, Any]]


class AIAskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=20)


class AIAskResponse(BaseModel):
    query: str
    answer: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks_count: int = 0


class AISummarizeResponse(BaseModel):
    document_id: str
    title: str
    summary: str
    key_takeaways: List[str]
    word_count: int


class OpportunityReport(BaseModel):
    members: List[str]
    extracted_skills: dict
    complementary_skills: str
    selected_problem: str
    target_customer: str
    proposed_opportunity: str
    team_roles: dict
    value_proposition: str
    revenue_model: str
    missing_skills: List[str]
    risks: List[str]
    opportunity_score: int
    validation_plan: List[str]
    final_recommendation: str
