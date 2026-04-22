"""
Cluster model — hardened
- status as DB ENUM (enforces valid values)
- severity CHECK 0-1
- score fields with constraints
- institution_id indexed
"""
import enum
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    Text, ForeignKey, JSON, Index, CheckConstraint, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class ClusterStatus(str, enum.Enum):
    new = "new"
    active = "active"
    dormant = "dormant"
    archived = "archived"
    resolved = "resolved"
    reopened = "reopened"


# Valid state machine transitions — enforced at service layer
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "new": ["active"],
    "active": ["dormant", "resolved"],
    "dormant": ["active", "archived"],
    "archived": [],         # terminal
    "resolved": ["reopened"],
    "reopened": ["active"],
}


def is_valid_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, [])


class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"),
                             nullable=False)

    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    category = Column(String(100), default="general", nullable=False)

    # DB-enum status
    status = Column(
        Enum(ClusterStatus, name="cluster_status_enum", create_type=True),
        default=ClusterStatus.new,
        nullable=False,
    )

    severity = Column(Float, default=0.5, nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    visibility_score = Column(Float, default=0.0, nullable=False)
    diversity_score = Column(Float, default=0.0, nullable=False)
    diversity_valid = Column(Boolean, default=False, nullable=False)

    is_escalated = Column(Boolean, default=False, nullable=False)
    escalation_type = Column(String(30), nullable=True)  # normal | override

    report_count = Column(Integer, default=0, nullable=False)
    support_count = Column(Integer, default=0, nullable=False)
    context_count = Column(Integer, default=0, nullable=False)
    scope = Column(Float, default=0.0, nullable=False)

    centroid_embedding = Column(JSON, nullable=True)
    departments_involved = Column(JSON, default=list, nullable=False)
    years_involved = Column(JSON, default=list, nullable=False)

    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    # SLA persistence fields — required by system spec
    sla_status = Column(String(20), default="pending", nullable=False)  # pending | met | breached
    sla_breached_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())

    institution = relationship("Institution", back_populates="clusters")
    issues = relationship("Issue", back_populates="cluster")
    admin_actions = relationship("AdminAction", back_populates="cluster")
    event_logs = relationship("EventLog", back_populates="cluster")

    __table_args__ = (
        CheckConstraint("severity BETWEEN 0.0 AND 1.0", name="ck_cluster_severity"),
        CheckConstraint("confidence_score BETWEEN 0.0 AND 2.5", name="ck_cluster_confidence"),
        CheckConstraint("report_count >= 0", name="ck_cluster_report_count"),
        Index("ix_clusters_institution_status", "institution_id", "status"),
        Index("ix_clusters_institution_visibility", "institution_id", "visibility_score"),
        Index("ix_clusters_escalated", "institution_id", "is_escalated"),
    )

    def __repr__(self):
        return f"<Cluster id={self.id} status={self.status} conf={self.confidence_score:.2f}>"
