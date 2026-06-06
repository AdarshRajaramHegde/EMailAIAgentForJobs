"""
SQLAlchemy ORM models for the AI Job Application Agent.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, Enum, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


# ── Enums ─────────────────────────────────────────────────────

class JobStatus(str, enum.Enum):
    NEW = "new"
    FILTERED = "filtered"
    SCORED = "scored"
    NOTIFIED = "notified"
    TAILORED = "tailored"
    APPLIED = "applied"
    FLAGGED = "flagged"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FLAGGED = "flagged"
    FAILED = "failed"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"


class JobType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    UNKNOWN = "unknown"


class ApplicationMethod(str, enum.Enum):
    EASY_APPLY = "easy_apply"
    FORM_FILL = "form_fill"
    EMAIL = "email"
    MANUAL = "manual"


# ── Models ────────────────────────────────────────────────────

class Company(Base):
    """Companies with their career page URLs."""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    website = Column(String(500))
    career_page_url = Column(String(500))
    linkedin_url = Column(String(500))
    industry = Column(String(100))
    source = Column(String(100))  # e.g. "crunchbase", "ida_ireland", "google_search"
    location = Column(String(255))
    last_checked = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs = relationship("Job", back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("name", "career_page_url", name="uq_company_career"),
        Index("ix_company_name", "name"),
    )

    def __repr__(self):
        return f"<Company(id={self.id}, name='{self.name}')>"


class Job(Base):
    """Individual job listings discovered from any source."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(300), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    company_name = Column(String(255))  # denormalized for convenience
    url = Column(String(1000), nullable=False)
    url_hash = Column(String(64), unique=True, nullable=False)  # SHA-256 for dedup
    description = Column(Text)
    location = Column(String(255))
    salary_min = Column(Float)
    salary_max = Column(Float)
    salary_currency = Column(String(10))
    job_type = Column(String(50), default=JobType.UNKNOWN.value)
    source = Column(String(100), nullable=False)  # linkedin, indeed, career_page, etc.
    external_id = Column(String(255))  # ID from the source platform
    is_easy_apply = Column(Boolean, default=False)
    requires_cover_letter = Column(Boolean, default=False)
    application_email = Column(String(255))  # if apply-by-email

    # Scoring
    relevance_score = Column(Float)
    score_breakdown = Column(Text)  # JSON breakdown

    # Status
    status = Column(String(50), default=JobStatus.NEW.value)
    flag_reason = Column(Text)  # why it was flagged for manual review

    # Timestamps
    posted_at = Column(DateTime)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="jobs")
    application = relationship("Application", back_populates="job", uselist=False)

    __table_args__ = (
        Index("ix_job_status", "status"),
        Index("ix_job_source", "source"),
        Index("ix_job_score", "relevance_score"),
        Index("ix_job_discovered", "discovered_at"),
    )

    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.title}', source='{self.source}')>"


class Application(Base):
    """Record of every application submitted (or attempted)."""
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)
    status = Column(String(50), default=ApplicationStatus.PENDING.value)
    method = Column(String(50))  # easy_apply, form_fill, email, manual
    tailored_resume_path = Column(String(500))
    cover_letter_path = Column(String(500))
    applied_at = Column(DateTime)
    response_received = Column(Boolean, default=False)
    response_date = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job = relationship("Job", back_populates="application")
    logs = relationship("ApplicationLog", back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_application_status", "status"),
        Index("ix_application_date", "applied_at"),
    )

    def __repr__(self):
        return f"<Application(id={self.id}, job_id={self.job_id}, status='{self.status}')>"


class ApplicationLog(Base):
    """Detailed event log for each application step."""
    __tablename__ = "application_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    event = Column(String(100), nullable=False)  # e.g. "form_filled", "resume_uploaded", "submitted"
    details = Column(Text)
    screenshot_path = Column(String(500))
    timestamp = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="logs")

    def __repr__(self):
        return f"<ApplicationLog(id={self.id}, event='{self.event}')>"
