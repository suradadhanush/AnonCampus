"""
Score recomputation Celery task — fully hardened

Guarantees:
C) Redis lock: lock:cluster:{id} — only ONE scoring task runs per cluster at a time
D) Debounce enforced by _trigger_score caller (2s window)
E) Explainability format: strict {"confidence", "severity", "explanation": {...}}
F) SLA persistence: sla_status + sla_breached_at updated every pass
"""
from app.tasks.celery_app import celery_app
from datetime import datetime, timezone, timedelta


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def recompute_cluster_score(self, cluster_id: int):
    """
    Atomically recompute cluster scores.
    Uses Redis distributed lock to prevent concurrent recomputation of same cluster.
    """
    import redis as redis_lib

    try:
        from app.core.config import settings

        # ── Redis distributed lock ────────────────────────────────────────────
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        lock_key = f"lock:cluster:{cluster_id}"
        # NX=only set if not exists, EX=30s max hold time
        acquired = r.set(lock_key, self.request.id or "1", nx=True, ex=30)
        if not acquired:
            # Another task is already computing this cluster — skip silently
            return {"skipped": True, "reason": "lock_held", "cluster_id": cluster_id}

        try:
            _do_recompute(cluster_id, settings, r)
        finally:
            # Always release lock
            r.delete(lock_key)

    except redis_lib.RedisError:
        # Redis unavailable — proceed without lock (degraded mode)
        try:
            from app.core.config import settings
            _do_recompute(cluster_id, settings, None)
        except Exception as exc:
            raise self.retry(exc=exc)
    except Exception as exc:
        raise self.retry(exc=exc)


def _do_recompute(cluster_id: int, settings, redis_client):
    """Core recomputation logic — runs inside the Redis lock."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from app.models.cluster import Cluster
    from app.models.issue import Issue
    from app.models.report import Report, Vote
    from app.services.scoring import (
        compute_diversity_score, compute_confidence_score,
        compute_visibility_score, compute_scope, check_escalation,
        compute_average_trust_weight,
    )
    from app.utils.observability import log_score_computed, log_escalation, log_sla_breach

    engine = create_engine(
        settings.SYNC_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Lock cluster row for update (DB-level concurrency)
        cluster = db.execute(
            text("SELECT * FROM clusters WHERE id = :id FOR UPDATE"),
            {"id": cluster_id}
        ).fetchone()

        if not cluster:
            return

        # Re-fetch as ORM object after locking
        cluster_obj = db.query(Cluster).filter(Cluster.id == cluster_id).first()
        if not cluster_obj:
            return

        issue_ids = [
            row[0] for row in
            db.query(Issue.id).filter(Issue.cluster_id == cluster_id).all()
        ]
        if not issue_ids:
            return

        reports = db.query(Report).filter(
            Report.issue_id.in_(issue_ids), Report.signal_type == "report"
        ).all()
        supports = db.query(Vote).filter(Vote.issue_id.in_(issue_ids)).all()
        contexts = db.query(Report).filter(
            Report.issue_id.in_(issue_ids), Report.signal_type == "context"
        ).all()

        departments = [r.reporter_department for r in reports]
        years = [r.reporter_year for r in reports]
        trust_scores = [r.reporter_trust_at_time for r in reports]

        diversity_score, diversity_valid, div_expl = compute_diversity_score(departments, years)
        avg_trust = compute_average_trust_weight(trust_scores)

        confidence, conf_expl = compute_confidence_score(
            report_count=len(reports),
            support_count=len(supports),
            context_count=len(contexts),
            diversity_score=diversity_score,
            diversity_valid=diversity_valid,
            severity=cluster_obj.severity,
            trust_weight=avg_trust,
        )

        now = datetime.now(timezone.utc)
        last_activity = cluster_obj.last_activity_at
        if last_activity and last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        hours_diff = ((now - last_activity).total_seconds() / 3600) if last_activity else 0

        scope = compute_scope(
            len(reports),
            len(set(d for d in departments if d)),
            len(set(y for y in years if y))
        )
        visibility = compute_visibility_score(confidence, cluster_obj.severity, hours_diff, scope)

        should_escalate, escalation_type = check_escalation(
            len(reports), len(supports), diversity_valid, cluster_obj.severity
        )

        # Build strict explainability format (spec E)
        explanation = {
            "confidence": round(confidence, 4),
            "severity": round(cluster_obj.severity, 4),
            "explanation": {
                "reports": len(reports),
                "supports": len(supports),
                "contexts": len(contexts),
                "diversity": "valid" if diversity_valid else "invalid",
                "trust_weight": round(avg_trust, 4),
                "diversity_detail": div_expl,
            }
        }

        # ── Update cluster ────────────────────────────────────────────────────
        cluster_obj.report_count = len(reports)
        cluster_obj.support_count = len(supports)
        cluster_obj.context_count = len(contexts)
        cluster_obj.diversity_score = round(diversity_score, 4)
        cluster_obj.diversity_valid = diversity_valid
        cluster_obj.confidence_score = round(confidence, 4)
        cluster_obj.visibility_score = round(visibility, 4)
        cluster_obj.scope = round(scope, 4)
        cluster_obj.departments_involved = list(set(d for d in departments if d))
        cluster_obj.years_involved = list(set(y for y in years if y))
        cluster_obj.last_activity_at = now

        # Escalation
        if should_escalate and not cluster_obj.is_escalated:
            cluster_obj.is_escalated = True
            cluster_obj.escalation_type = escalation_type
            sla_hours = 24 if escalation_type == "override" else 72
            cluster_obj.sla_deadline = now + timedelta(hours=sla_hours)
            cluster_obj.sla_status = "pending"
            if cluster_obj.status == "new":
                cluster_obj.status = "active"
            log_escalation(cluster_id, escalation_type)

        elif cluster_obj.status == "new" and len(reports) >= 2:
            cluster_obj.status = "active"

        # SLA breach check — persist sla_breached_at (spec F)
        if (cluster_obj.sla_deadline and
                cluster_obj.sla_deadline < now and
                cluster_obj.status not in ("resolved", "archived") and
                cluster_obj.sla_status != "breached"):
            cluster_obj.sla_status = "breached"
            cluster_obj.sla_breached_at = now
            log_sla_breach(cluster_id, cluster_obj.institution_id, cluster_obj.sla_deadline.isoformat())

        db.commit()
        log_score_computed(cluster_id, confidence, cluster_obj.is_escalated)
        return explanation

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        engine.dispose()


@celery_app.task(bind=True, max_retries=3)
def detect_spike(self, cluster_id: int):
    """Spike detection: ≥12 interactions in 10 min"""
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        from app.utils.observability import log_spike_detected

        engine = create_engine(settings.SYNC_DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            result = db.execute(text("""
                SELECT COUNT(*) FROM (
                    SELECT r.created_at FROM reports r
                    JOIN issues i ON r.issue_id = i.id
                    WHERE i.cluster_id = :cid
                    AND r.created_at >= NOW() - INTERVAL '10 minutes'
                    UNION ALL
                    SELECT v.created_at FROM votes v
                    JOIN issues i ON v.issue_id = i.id
                    WHERE i.cluster_id = :cid
                    AND v.created_at >= NOW() - INTERVAL '10 minutes'
                ) interactions
            """), {"cid": cluster_id})
            count = result.scalar() or 0
            if count >= settings.SPIKE_INTERACTIONS:
                log_spike_detected(cluster_id, count)
                recompute_cluster_score.delay(cluster_id)
        finally:
            db.close()
            engine.dispose()
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2)
def cleanup_expired_idempotency_keys(self):
    """Hourly cleanup of expired idempotency keys"""
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        engine = create_engine(settings.SYNC_DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            db.execute(text("DELETE FROM idempotency_keys WHERE expires_at < NOW()"))
            db.commit()
        finally:
            db.close()
            engine.dispose()
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2)
def cleanup_expired_refresh_tokens(self):
    """Daily cleanup of expired refresh tokens"""
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        engine = create_engine(settings.SYNC_DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            db.execute(text("DELETE FROM refresh_tokens WHERE expires_at < NOW()"))
            db.commit()
        finally:
            db.close()
            engine.dispose()
    except Exception as exc:
        raise self.retry(exc=exc)
