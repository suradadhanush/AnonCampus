"""
User + Institution models — production-hardened
- student_id: unique per institution, NEVER exposed in API
- academic_year: DB CHECK 1-4
- allowed_email_domain: strict registration gate
- anon_id: safe public identifier
- trust_score: DB CHECK 0.1-2.1
"""
import uuid
import enum

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, Enum, ForeignKey, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class UserRole(str, enum.Enum):
    student = "student"
    admin = "admin"
    super_admin = "super_admin"


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(100), unique=True, nullable=False, index=True)
    allowed_email_domain = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    tier = Column(String(20), default="medium", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="institution", lazy="select")
    clusters = relationship("Cluster", back_populates="institution", lazy="select")
    issues = relationship("Issue", back_populates="institution", lazy="select")

    def __repr__(self):
        return f"<Institution id={self.id} domain={self.domain}>"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False)

    # Safe public identifier — UUID, never exposes student_id
    anon_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # PRIVATE — never returned in any API response, masked in logs
    student_id = Column(String(50), nullable=False)

    role = Column(Enum(UserRole), default=UserRole.student, nullable=False)

    department = Column(String(100), nullable=False, default="Unknown")
    academic_year = Column(Integer, nullable=False, default=1)

    trust_score = Column(Float, default=1.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    institution = relationship("Institution", back_populates="users")
    reports = relationship("Report", back_populates="reporter", foreign_keys="Report.reporter_id")
    votes = relationship("Vote", back_populates="voter")
    feedbacks = relationship("Feedback", back_populates="user")
    admin_actions = relationship("AdminAction", back_populates="admin",
                                  foreign_keys="AdminAction.admin_id")

    __table_args__ = (
        UniqueConstraint("institution_id", "student_id", name="uq_user_institution_student"),
        CheckConstraint("academic_year BETWEEN 1 AND 4", name="ck_user_academic_year"),
        CheckConstraint("trust_score BETWEEN 0.1 AND 2.1", name="ck_user_trust_score"),
        Index("ix_users_institution_id", "institution_id"),
        Index("ix_users_institution_role", "institution_id", "role"),
        Index("ix_users_anon_id", "anon_id"),
    )

    def __repr__(self):
        return f"<User id={self.id} role={self.role} inst={self.institution_id}>"
