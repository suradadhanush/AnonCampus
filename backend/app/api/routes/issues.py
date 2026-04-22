"""
Issues API routes — all queries institution-scoped
Rate limits enforced per action
Idempotency-Key header supported on POST /issues
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.models.issue import Issue
from app.models.cluster import Cluster
from app.schemas.issue import (
    IssueCreate, IssueResponse, IssueDetailResponse,
    FeedbackCreate, ContextAddRequest, PaginatedResponse,
    ClusterResponse, ClusterDetailResponse, ScoreExplanation,
)
from app.core.security import get_current_user
from app.middleware.rate_limit import (
    check_issue_submit_limit, check_support_limit,
    check_feedback_limit, get_idempotency_key,
)
from app.services.issue_service import submit_issue, add_support, add_context, submit_feedback

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
async def create_issue(
    payload: IssueCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_issue_submit_limit(current_user.id)
    idem_key = get_idempotency_key(request)
    issue = await submit_issue(db, payload, current_user, idempotency_key=idem_key)
    return issue


@router.get("/clusters", response_model=PaginatedResponse)
async def list_clusters(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    feed_type: Optional[str] = Query(None, description="new|active|trending"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student feed — clusters sorted by visibility score"""
    conditions = [
        Cluster.institution_id == current_user.institution_id,
        Cluster.status != "archived",
    ]
    if status_filter:
        conditions.append(Cluster.status == status_filter.lower())
    elif feed_type == "new":
        conditions.append(Cluster.status == "new")
    elif feed_type == "active":
        conditions.append(Cluster.status == "active")
    elif feed_type == "trending":
        conditions.append(Cluster.visibility_score >= 0.5)

    base = select(Cluster).where(and_(*conditions))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    result = await db.execute(
        base.order_by(desc(Cluster.visibility_score))
            .offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(
        items=[ClusterResponse.model_validate(c) for c in items],
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get("", response_model=PaginatedResponse)
async def list_issues(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    sort_by: str = Query("created_at", pattern="^(created_at|severity)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conditions = [Issue.institution_id == current_user.institution_id]
    if status_filter:
        conditions.append(Issue.status == status_filter.lower())
    if category:
        conditions.append(Issue.category == category)

    base = select(Issue).where(and_(*conditions))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    order_col = desc(Issue.severity) if sort_by == "severity" else desc(Issue.created_at)
    result = await db.execute(
        base.order_by(order_col).offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(
        items=[IssueResponse.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get("/{issue_id}", response_model=IssueDetailResponse)
async def get_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = await db.get(Issue, issue_id)
    if not issue or issue.institution_id != current_user.institution_id:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@router.post("/{issue_id}/support", status_code=200)
async def support_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_support_limit(current_user.id)
    ok = await add_support(db, issue_id, current_user)
    if not ok:
        raise HTTPException(status_code=400, detail="Already supported or issue not found")
    return {"message": "Support recorded"}


@router.post("/{issue_id}/context", status_code=200)
async def add_issue_context(
    issue_id: int,
    payload: ContextAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await add_context(db, issue_id, current_user, payload.context_text)
    if not ok:
        raise HTTPException(status_code=400, detail="Context already added or issue not found")
    return {"message": "Context recorded"}


@router.post("/{issue_id}/feedback", status_code=200)
async def give_feedback(
    issue_id: int,
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_feedback_limit(current_user.id)
    ok = await submit_feedback(db, issue_id, current_user, payload)
    if not ok:
        raise HTTPException(status_code=400, detail="Feedback already submitted or issue not found")
    return {"message": "Feedback recorded"}


@router.get("/{issue_id}/cluster")
async def get_issue_cluster(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = await db.get(Issue, issue_id)
    if not issue or issue.institution_id != current_user.institution_id:
        raise HTTPException(status_code=404, detail="Issue not found")
    if not issue.cluster_id:
        return {"cluster": None}
    cluster = await db.get(Cluster, issue.cluster_id)
    return {"cluster": ClusterResponse.model_validate(cluster) if cluster else None}
