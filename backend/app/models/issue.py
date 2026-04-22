"""
Issue model — hardened
- severity CHECK 0-1
- submitter metadata for diversity tracking
- moderation flags stored
- institution_id always indexed
"""
import enum
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    Text, ForeignKey, JSON, Index, CheckConstraint, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class IssueStatus(str, enum.Enum):
    new = "new"
    active = "active"
    dormant = "dormant"
    archived = "archived"
    resolved = "resolved"
    reopened = "reopened"


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    cluster_id = Column(Integer, ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True)

    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(100), default="general", nullable=False)

    status = Column(
        Enum(IssueStatus, name="issue_status_enum", create_type=True),
        default=IssueStatus.new,
        nullable=False,
    )

    severity = Column(Float, default=0.5, nullable=False)
    embedding = Column(JSON, nullable=True)

    is_moderated = Column(Boolean, default=False, nullable=False)
    moderation_flags = Column(JSON, default=list, nullable=False)

    # Snapshot of submitter metadata at submission time (for diversity)
    submitter_department = Column(String(100), nullable=True)
    submitter_year = Column(Integer, nullable=True)
    submitter_trust_at_submission = Column(Float, default=1.0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    institution = relationship("Institution", back_populates="issues")
    cluster = relationship("Cluster", back_populates="issues")
    reports = relationship("Report", back_populates="issue", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="issue", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="issue", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("severity BETWEEN 0.0 AND 1.0", name="ck_issue_severity"),
        Index("ix_issues_institution_status", "institution_id", "status"),
        Index("ix_issues_institution_cluster", "institution_id", "cluster_id"),
    )

    def __repr__(self):
        return f"<Issue id={self.id} status={self.status} cluster={self.cluster_id}>"
