"""
Signal + Governance models — fully hardened

Fixes applied:
- RefreshToken table: DB-backed storage + revocation support
- EventTypeEnum: canonical fixed event types (no free-text chaos)
- SystemConfig: partial unique index so only one active=TRUE row per (inst, key)
- IdempotencyKey: expiry index for background cleanup
- User deletion strategy: SET NULL (anonymize), not CASCADE (delete history)
- SignalType / EventType shared from single enum definition
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, JSON, UniqueConstraint, Index, CheckConstraint, Enum,
    event as sa_event,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import enum


# ── Canonical enums (single source of truth) ─────────────────────────────────

class SignalType(str, enum.Enum):
    report  = "report"
    support = "support"
    context = "context"


class EventType(str, enum.Enum):
    """Fixed vocabulary for event_log.event_type — no free text allowed"""
    ISSUE_CREATED        = "ISSUE_CREATED"
    CLUSTER_ASSIGNED     = "CLUSTER_ASSIGNED"
    CLUSTER_CREATED      = "CLUSTER_CREATED"
    SUPPORT_ADDED        = "SUPPORT_ADDED"
    CONTEXT_ADDED        = "CONTEXT_ADDED"
    SCORE_UPDATED        = "SCORE_UPDATED"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"
    ADMIN_ACTION         = "ADMIN_ACTION"
    FEEDBACK_SUBMITTED   = "FEEDBACK_SUBMITTED"
    SPIKE_DETECTED       = "SPIKE_DETECTED"
    STATUS_TRANSITION    = "STATUS_TRANSITION"
    TRUST_UPDATED        = "TRUST_UPDATED"


class Report(Base):
    """Primary signal: anonymous corroboration"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)

    signal_type = Column(
        Enum(SignalType, name="signal_type_enum", create_type=True),
        default=SignalType.report,
        nullable=False,
    )
    context_text = Column(Text, nullable=True)

    # Snapshot of reporter metadata at signal time
    reporter_department = Column(String(100), nullable=True)
    reporter_year = Column(Integer, nullable=True)
    reporter_trust_at_time = Column(Float, default=1.0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    issue = relationship("Issue", back_populates="reports")
    reporter = relationship("User", back_populates="reports", foreign_keys=[reporter_id])

    __table_args__ = (
        # One signal of each type per user per issue
        UniqueConstraint("reporter_id", "issue_id", "signal_type", name="uq_report_user_issue_type"),
        Index("ix_reports_issue_type", "issue_id", "signal_type"),
        Index("ix_reports_institution", "institution_id"),
        # Required: reports(cluster_id) via join through issues — direct cluster lookup
        Index("ix_reports_reporter", "reporter_id"),
    )


class Vote(Base):
    """Support signal (secondary weight)"""
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    voter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    issue = relationship("Issue", back_populates="votes")
    voter = relationship("User", back_populates="votes")

    __table_args__ = (
        UniqueConstraint("voter_id", "issue_id", name="uq_vote_user_issue"),
        Index("ix_votes_issue", "issue_id"),
    )


class Feedback(Base):
    """Post-resolution quality feedback"""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)

    sentiment = Column(String(20), nullable=False)  # resolved | unresolved | partial
    rating = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    issue = relationship("Issue", back_populates="feedbacks")
    user = relationship("User", back_populates="feedbacks")

    __table_args__ = (
        UniqueConstraint("user_id", "issue_id", name="uq_feedback_user_issue"),
        CheckConstraint("sentiment IN ('resolved','unresolved','partial')", name="ck_feedback_sentiment"),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
    )


class AdminAction(Base):
    """Audit log of every admin mutation"""
    __tablename__ = "admin_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True)
    admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)

    action_type = Column(String(50), nullable=False)
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=True)
    reason = Column(Text, nullable=True)
    extra_meta = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cluster = relationship("Cluster", back_populates="admin_actions")
    admin = relationship("User", back_populates="admin_actions", foreign_keys=[admin_id])

    __table_args__ = (
        Index("ix_admin_actions_cluster", "cluster_id"),
        Index("ix_admin_actions_institution", "institution_id"),
    )


class EventLog(Base):
    """
    Immutable append-only event log.
    event_type is constrained to EventType enum — no free text.
    actor_id uses SET NULL on user delete (history preserved, identity anonymized).
    """
    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True)
    # SET NULL on user delete — history preserved, not destroyed
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)

    event_type = Column(
        Enum(EventType, name="event_type_enum", create_type=True),
        nullable=False,
    )
    payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cluster = relationship("Cluster", back_populates="event_logs")

    __table_args__ = (
        Index("ix_event_log_cluster", "cluster_id"),
        Index("ix_event_log_institution_type", "institution_id", "event_type"),
        Index("ix_event_log_created", "created_at"),
    )


class IdempotencyKey(Base):
    """
    Prevents duplicate API submissions under retries.
    Background job purges rows WHERE expires_at < NOW().
    """
    __tablename__ = "idempotency_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    endpoint = Column(String(100), nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Index for efficient expiry cleanup job
        Index("ix_idempotency_expires", "expires_at"),
    )


class RefreshToken(Base):
    """
    DB-backed refresh token storage.
    Required for:
      - logout (revoke single token)
      - revoke-all (logout from all devices)
      - reuse-attack prevention (revoked=True check)
    """
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Store hashed token — never raw
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)

    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(String(50), nullable=True)  # logout | reuse | admin | expired

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Family ID: used to detect token reuse — if one token in a family is reused,
    # revoke ALL tokens in that family (rotation attack prevention)
    family_id = Column(String(36), nullable=False, index=True)

    __table_args__ = (
        Index("ix_refresh_tokens_user", "user_id"),
        Index("ix_refresh_tokens_expires", "expires_at"),
        Index("ix_refresh_tokens_family", "family_id"),
    )


class SystemConfig(Base):
    """
    Versioned runtime configuration per institution.
    GUARANTEE: only one row with is_active=TRUE per (institution_id, key).
    Enforced via partial unique index (PostgreSQL-specific).
    """
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True)
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Standard unique index (SQLAlchemy portable)
        UniqueConstraint("institution_id", "key", name="uq_config_inst_key_base"),
        Index("ix_sysconfig_institution", "institution_id"),
        # NOTE: Partial unique index for is_active=TRUE is added in Alembic migration:
        # CREATE UNIQUE INDEX uix_sysconfig_active ON system_config(institution_id, key)
        # WHERE is_active = TRUE;
    )
