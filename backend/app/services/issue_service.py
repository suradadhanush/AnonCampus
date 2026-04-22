"""
Issue service — production-hardened

Guarantees enforced:
A) Atomic transactions: issue + report + cluster + event_log in one session.begin()
B) Concurrency: SELECT ... FOR UPDATE on cluster before any mutation
C) State machine: ALLOWED_TRANSITIONS enforced, raises 400 on violation
D) Explainability: strict format returned on all scoring paths
E) SLA persistence: sla_status + sla_breached_at updated on every score pass
F) Event logging: EventType enum, never free text
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, text
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.cluster import Cluster, ALLOWED_TRANSITIONS, is_valid_transition
from app.models.issue import Issue
from app.models.report import Report, Vote, Feedback, AdminAction, EventType
from app.schemas.issue import IssueCreate, FeedbackCreate, AdminStatusUpdate
from app.services import clustering as cluster_svc
from app.services import scoring as score_svc
from app.services.moderation import moderate_text
from app.utils.observability import log_event, log_escalation
from app.core.config import settings


# ── Submit Issue — fully atomic ───────────────────────────────────────────────

async def submit_issue(
    db: AsyncSession,
    payload: IssueCreate,
    user: User,
    idempotency_key: Optional[str] = None,
) -> Issue:
    """
    Pipeline: Moderation → NLP → Cluster(FOR UPDATE) → Issue → Report → EventLog
    All writes in one atomic transaction.
    """
    # Idempotency check (read-only, before transaction)
    if idempotency_key:
        from app.middleware.rate_limit import check_idempotency
        cached = await check_idempotency(db, idempotency_key, user.id, "submit_issue")
        if cached:
            existing_id = cached.get("issue_id")
            if existing_id:
                issue = await db.get(Issue, existing_id)
                if issue:
                    return issue

    # Step 1: Moderation (pure computation, no DB)
    is_clean, flags, clean_title, clean_body = moderate_text(payload.title, payload.body)
    if not is_clean:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"error": "moderation_failed", "flags": flags})

    # Step 2: NLP classification with fallback
    try:
        category = payload.category or cluster_svc.classify_category(clean_body)
        severity = payload.severity if payload.severity is not None else cluster_svc.estimate_severity(clean_body)
        embedding = cluster_svc.get_embedding(f"{clean_title} {clean_body}")
    except Exception:
        category = payload.category or "general"
        severity = payload.severity if payload.severity is not None else 0.5
        embedding = None

    # Step 3: Find candidate clusters (read, institution-scoped)
    clusters_result = await db.execute(
        select(Cluster).where(
            and_(
                Cluster.institution_id == user.institution_id,
                Cluster.status.in_(["new", "active"]),
                Cluster.category == category,
            )
        ).limit(50)
    )
    existing_clusters = clusters_result.scalars().all()
    candidates = [(c.id, c.centroid_embedding, c.title) for c in existing_clusters]

    # Step 4: Clustering decision
    action, matched_cluster_id, sim_score = cluster_svc.determine_cluster_action(
        embedding, f"{clean_title} {clean_body}", candidates
    )

    # ── ALL WRITES IN ONE ATOMIC TRANSACTION ──────────────────────────────────
    async with db.begin():
        cluster_id: Optional[int] = None
        cluster_event = EventType.CLUSTER_ASSIGNED

        if action in ("same", "conditional") and matched_cluster_id:
            # CONCURRENCY: lock cluster row before updating
            locked = await db.execute(
                select(Cluster)
                .where(Cluster.id == matched_cluster_id)
                .with_for_update()
            )
            cluster = locked.scalar_one_or_none()
            if cluster:
                cluster_id = cluster.id
                new_count = cluster.report_count + 1
                cluster.centroid_embedding = cluster_svc.update_centroid(
                    cluster.centroid_embedding, embedding, new_count
                )
        else:
            cluster_event = EventType.CLUSTER_CREATED
            new_cluster = Cluster(
                institution_id=user.institution_id,
                title=clean_title,
                category=category,
                severity=severity,
                status="new",
                centroid_embedding=embedding,
                departments_involved=[user.department] if user.department else [],
                years_involved=[user.academic_year] if user.academic_year else [],
            )
            db.add(new_cluster)
            await db.flush()
            cluster_id = new_cluster.id

        # Create issue
        issue = Issue(
            institution_id=user.institution_id,
            cluster_id=cluster_id,
            title=clean_title,
            body=clean_body,
            category=category,
            status="new",
            severity=severity,
            embedding=embedding,
            is_moderated=True,
            moderation_flags=flags,
            submitter_department=user.department,
            submitter_year=user.academic_year,
            submitter_trust_at_submission=user.trust_score,
        )
        db.add(issue)
        await db.flush()

        # Auto-report signal from submitter
        report = Report(
            issue_id=issue.id,
            reporter_id=user.id,
            institution_id=user.institution_id,
            signal_type="report",
            reporter_department=user.department,
            reporter_year=user.academic_year,
            reporter_trust_at_time=user.trust_score,
        )
        db.add(report)

        # Trust update (within transaction)
        user.trust_score = score_svc.update_trust_score(user.trust_score, "valid_participation")

        # Event log (both events)
        await log_event(db, user.institution_id, EventType.ISSUE_CREATED,
                        cluster_id=cluster_id, actor_id=user.id,
                        payload={"issue_id": issue.id, "category": category, "severity": severity})
        await log_event(db, user.institution_id, cluster_event,
                        cluster_id=cluster_id, actor_id=user.id,
                        payload={"action": action, "similarity": round(sim_score, 4)})
    # ── END TRANSACTION ───────────────────────────────────────────────────────

    await db.refresh(issue)

    # Idempotency storage (separate small write, after main tx commits)
    if idempotency_key:
        from app.middleware.rate_limit import store_idempotency
        async with db.begin():
            await store_idempotency(db, idempotency_key, user.id,
                                    "submit_issue", 201, {"issue_id": issue.id})

    # Trigger async score recompute (fire-and-forget, outside tx)
    _trigger_score(cluster_id)
    return issue


# ── Support — atomic ──────────────────────────────────────────────────────────

async def add_support(db: AsyncSession, issue_id: int, user: User) -> bool:
    # Pre-check (no lock needed for read)
    issue = await db.get(Issue, issue_id)
    if not issue or issue.institution_id != user.institution_id:
        return False

    existing = await db.execute(
        select(Vote).where(and_(Vote.issue_id == issue_id, Vote.voter_id == user.id))
    )
    if existing.scalar_one_or_none():
        return False

    async with db.begin():
        vote = Vote(issue_id=issue_id, voter_id=user.id, institution_id=user.institution_id)
        db.add(vote)
        await log_event(db, user.institution_id, EventType.SUPPORT_ADDED,
                        cluster_id=issue.cluster_id, actor_id=user.id,
                        payload={"issue_id": issue_id})

    _trigger_score(issue.cluster_id)
    return True


# ── Context — atomic ──────────────────────────────────────────────────────────

async def add_context(db: AsyncSession, issue_id: int, user: User, context_text: str) -> bool:
    issue = await db.get(Issue, issue_id)
    if not issue or issue.institution_id != user.institution_id:
        return False

    existing = await db.execute(
        select(Report).where(and_(
            Report.issue_id == issue_id,
            Report.reporter_id == user.id,
            Report.signal_type == "context",
        ))
    )
    if existing.scalar_one_or_none():
        return False

    async with db.begin():
        report = Report(
            issue_id=issue_id, reporter_id=user.id, institution_id=user.institution_id,
            signal_type="context", context_text=context_text,
            reporter_department=user.department, reporter_year=user.academic_year,
            reporter_trust_at_time=user.trust_score,
        )
        db.add(report)
        await log_event(db, user.institution_id, EventType.CONTEXT_ADDED,
                        cluster_id=issue.cluster_id, actor_id=user.id,
                        payload={"issue_id": issue_id})

    _trigger_score(issue.cluster_id)
    return True


# ── Feedback — atomic ─────────────────────────────────────────────────────────

async def submit_feedback(db: AsyncSession, issue_id: int, user: User, payload: FeedbackCreate) -> bool:
    issue = await db.get(Issue, issue_id)
    if not issue or issue.institution_id != user.institution_id:
        return False

    existing = await db.execute(
        select(Feedback).where(and_(Feedback.issue_id == issue_id, Feedback.user_id == user.id))
    )
    if existing.scalar_one_or_none():
        return False

    async with db.begin():
        feedback = Feedback(
            issue_id=issue_id, user_id=user.id, institution_id=user.institution_id,
            sentiment=payload.sentiment, rating=payload.rating, comment=payload.comment,
        )
        db.add(feedback)
        trust_event = "correct_feedback" if (payload.rating and payload.rating >= 3) else "valid_participation"
        user.trust_score = score_svc.update_trust_score(user.trust_score, trust_event)
        await log_event(db, user.institution_id, EventType.FEEDBACK_SUBMITTED,
                        cluster_id=issue.cluster_id, actor_id=user.id,
                        payload={"issue_id": issue_id, "sentiment": payload.sentiment})
    return True


# ── Admin status update — atomic + FOR UPDATE ─────────────────────────────────

async def admin_update_status(db: AsyncSession, payload: AdminStatusUpdate, admin: User) -> Optional[Cluster]:
    """
    State machine enforced. Cluster locked with FOR UPDATE before write.
    SLA status updated on resolve.
    """
    from fastapi import HTTPException

    async with db.begin():
        # CONCURRENCY: lock cluster row
        locked = await db.execute(
            select(Cluster)
            .where(and_(Cluster.id == payload.cluster_id, Cluster.institution_id == admin.institution_id))
            .with_for_update()
        )
        cluster = locked.scalar_one_or_none()
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")

        if not is_valid_transition(cluster.status, payload.new_status):
            raise HTTPException(status_code=400, detail={
                "error": "invalid_transition",
                "current": cluster.status,
                "requested": payload.new_status,
                "allowed": ALLOWED_TRANSITIONS.get(cluster.status, []),
            })

        old_status = cluster.status
        cluster.status = payload.new_status
        cluster.updated_at = datetime.now(timezone.utc)

        # SLA persistence: mark met if resolved before deadline
        if payload.new_status == "resolved":
            now = datetime.now(timezone.utc)
            if cluster.sla_deadline:
                cluster.sla_status = "met" if now <= cluster.sla_deadline else "breached"
                if cluster.sla_status == "breached" and not cluster.sla_breached_at:
                    cluster.sla_breached_at = now
            else:
                cluster.sla_status = "met"

        action = AdminAction(
            cluster_id=cluster.id, admin_id=admin.id, institution_id=admin.institution_id,
            action_type="status_update", old_status=old_status,
            new_status=payload.new_status, reason=payload.reason,
        )
        db.add(action)

        await log_event(db, admin.institution_id, EventType.ADMIN_ACTION,
                        cluster_id=cluster.id, actor_id=admin.id,
                        payload={"action": "status_update", "old": old_status, "new": payload.new_status,
                                 "reason": payload.reason})

    await db.refresh(cluster)
    return cluster


# ── Score trigger with debounce ───────────────────────────────────────────────

def _trigger_score(cluster_id: Optional[int]) -> None:
    """
    Fire-and-forget Celery task with Redis debounce.
    Max 1 recompute per SCORE_DEBOUNCE_SECONDS per cluster.
    """
    if not cluster_id:
        return
    try:
        import redis as redis_sync
        from app.core.config import settings

        r = redis_sync.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1)
        debounce_key = f"score_debounce:{cluster_id}"

        # Only trigger if no recent trigger exists
        if r.set(debounce_key, "1", nx=True, ex=settings.SCORE_DEBOUNCE_SECONDS):
            from app.tasks.score_tasks import recompute_cluster_score
            recompute_cluster_score.delay(cluster_id)
    except Exception:
        # Fail open — score will eventually recompute
        try:
            from app.tasks.score_tasks import recompute_cluster_score
            recompute_cluster_score.delay(cluster_id)
        except Exception:
            pass
