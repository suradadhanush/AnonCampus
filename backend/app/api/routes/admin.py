"""
Admin routes — fully institution-scoped
Every query filters by admin.institution_id — no cross-tenant leakage.
Includes: explainability endpoint, event timeline, SLA tracking, stats.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.models.cluster import Cluster
from app.models.report import AdminAction, EventLog
from app.schemas.issue import (
    AdminStatusUpdate, ClusterResponse, ClusterDetailResponse,
    PaginatedResponse, ScoreExplanation,
)
from app.core.security import require_admin
from app.services.issue_service import admin_update_status

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    inst_id = admin.institution_id
    def _count(cond): return select(func.count()).where(and_(Cluster.institution_id == inst_id, cond))

    total     = (await db.execute(select(func.count()).where(Cluster.institution_id == inst_id))).scalar()
    escalated = (await db.execute(_count(Cluster.is_escalated == True))).scalar()
    active    = (await db.execute(_count(Cluster.status == "active"))).scalar()
    resolved  = (await db.execute(_count(Cluster.status == "resolved"))).scalar()
    overdue   = (await db.execute(
        select(func.count()).where(and_(
            Cluster.institution_id == inst_id,
            Cluster.sla_deadline < func.now(),
            Cluster.status.notin_(["resolved", "archived"]),
        ))
    )).scalar()
    return {
        "total_clusters": total,
        "escalated": escalated,
        "active": active,
        "resolved": resolved,
        "overdue_sla": overdue,
    }


@router.get("/issues", response_model=PaginatedResponse)
async def admin_list_clusters(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    escalated_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    conditions = [Cluster.institution_id == admin.institution_id]
    if escalated_only:
        conditions.append(Cluster.is_escalated == True)
    if status_filter:
        conditions.append(Cluster.status == status_filter.lower())

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


@router.get("/clusters/{cluster_id}")
async def get_cluster_detail(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Full cluster detail with explainability + event timeline"""
    cluster = await db.get(Cluster, cluster_id)
    if not cluster or cluster.institution_id != admin.institution_id:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Timeline: event_log entries for this cluster
    events_result = await db.execute(
        select(EventLog)
        .where(EventLog.cluster_id == cluster_id)
        .order_by(EventLog.created_at)
        .limit(100)
    )
    events = events_result.scalars().all()
    timeline = [
        {
            "event_type": e.event_type.value if hasattr(e.event_type, "value") else e.event_type,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]

    # Issue count
    from app.models.issue import Issue
    issue_count = (await db.execute(
        select(func.count()).where(Issue.cluster_id == cluster_id)
    )).scalar()

    # Explainability
    explanation = ScoreExplanation(
        confidence=cluster.confidence_score,
        diversity_valid=cluster.diversity_valid,
        escalated=cluster.is_escalated,
        escalation_type=cluster.escalation_type,
        reason={
            "reports": cluster.report_count,
            "supports": cluster.support_count,
            "contexts": cluster.context_count,
            "diversity": (
                f"valid ({len(cluster.departments_involved)} depts, "
                f"{len(cluster.years_involved)} years)"
                if cluster.diversity_valid
                else "invalid — insufficient cross-department spread"
            ),
            "severity": cluster.severity,
            "scope": cluster.scope,
        },
    )

    return {
        "cluster": ClusterResponse.model_validate(cluster),
        "explanation": explanation,
        "timeline": timeline,
        "issue_count": issue_count,
    }


@router.post("/update-status")
async def update_cluster_status(
    payload: AdminStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    cluster = await admin_update_status(db, payload, admin)
    if not cluster:
        raise HTTPException(status_code=400, detail="Invalid status transition or cluster not found")
    return {"message": "Status updated", "cluster_id": cluster.id, "new_status": cluster.status}


@router.get("/audit-log", response_model=PaginatedResponse)
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    base = select(AdminAction).where(AdminAction.institution_id == admin.institution_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    result = await db.execute(
        base.order_by(desc(AdminAction.created_at))
            .offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(
        items=[{
            "id": a.id, "cluster_id": a.cluster_id,
            "action_type": a.action_type, "old_status": a.old_status,
            "new_status": a.new_status, "reason": a.reason,
            "created_at": a.created_at.isoformat(),
        } for a in items],
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    )
