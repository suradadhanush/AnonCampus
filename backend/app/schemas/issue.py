"""
Issue + Cluster schemas — with explainability layer
"""
import re
from pydantic import BaseModel, field_validator, Field
from typing import Optional, List, Any, Dict
from datetime import datetime


# ── Issue ─────────────────────────────────────────────────────────────────────

class IssueCreate(BaseModel):
    title: str = Field(..., min_length=10, max_length=500)
    body: str = Field(..., min_length=20, max_length=5000)
    category: Optional[str] = Field(default="general", max_length=50)
    severity: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("title", "body")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        # Strip emails
        v = re.sub(r'\b[\w.+-]+@[\w-]+\.\w+\b', '[EMAIL REDACTED]', v)
        # Strip phone numbers
        v = re.sub(r'\b(\+91|0)?[6-9]\d{9}\b', '[PHONE REDACTED]', v)
        # Strip HTML/script tags
        v = re.sub(r'<[^>]+>', '', v)
        return v.strip()


class IssueResponse(BaseModel):
    id: int
    title: str
    category: str
    status: str
    severity: float
    cluster_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class IssueDetailResponse(BaseModel):
    id: int
    title: str
    body: str
    category: str
    status: str
    severity: float
    cluster_id: Optional[int]
    is_moderated: bool
    moderation_flags: List[str]
    submitter_department: Optional[str]
    submitter_year: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Signals ───────────────────────────────────────────────────────────────────

class ContextAddRequest(BaseModel):
    context_text: str = Field(..., min_length=10, max_length=1000)

    @field_validator("context_text")
    @classmethod
    def sanitize(cls, v: str) -> str:
        v = re.sub(r'<[^>]+>', '', v)
        return v.strip()


class FeedbackCreate(BaseModel):
    sentiment: str = Field(..., pattern="^(resolved|unresolved|partial)$")
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)


# ── Explainability ────────────────────────────────────────────────────────────

class ScoreExplanation(BaseModel):
    """Human-readable breakdown of why this cluster has its score"""
    confidence: float
    diversity_valid: bool
    escalated: bool
    escalation_type: Optional[str]
    reason: Dict[str, Any]
    # reason example:
    # {
    #   "reports": 8, "supports": 12, "contexts": 2,
    #   "diversity": "valid (3 depts, 2 years, max_group=40%)",
    #   "severity": 0.72,
    #   "trust_weight": 1.05
    # }


# ── Cluster ───────────────────────────────────────────────────────────────────

class ClusterResponse(BaseModel):
    id: int
    title: str
    summary: Optional[str]
    category: str
    status: str
    severity: float
    confidence_score: float
    visibility_score: float
    diversity_score: float
    diversity_valid: bool
    is_escalated: bool
    escalation_type: Optional[str]
    report_count: int
    support_count: int
    context_count: int
    scope: float
    departments_involved: List[str]
    years_involved: List[int]
    sla_deadline: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime

    model_config = {"from_attributes": True}


class ClusterDetailResponse(ClusterResponse):
    """Extended cluster response with explainability"""
    explanation: Optional[ScoreExplanation] = None
    timeline: List[Dict[str, Any]] = []
    issue_count: int = 0


# ── Admin ─────────────────────────────────────────────────────────────────────

class AdminStatusUpdate(BaseModel):
    cluster_id: int
    new_status: str = Field(..., pattern="^(active|dormant|archived|resolved|reopened)$")
    reason: Optional[str] = Field(default=None, max_length=1000)


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
