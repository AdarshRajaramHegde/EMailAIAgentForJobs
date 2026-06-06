"""
Database engine, session management, and CRUD helpers.
"""

import hashlib
from datetime import datetime
from typing import Optional, List

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from config import settings
from database.models import Base, Company, Job, Application, ApplicationLog


# ── Engine & Session ──────────────────────────────────────────

engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    # SQLite needs check_same_thread=False for multi-threaded access
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Create all tables if they don't exist."""
    import os
    # Ensure data directory exists for SQLite
    if "sqlite" in settings.database_url:
        db_path = settings.database_url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully.")


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()


# ── URL Hashing ───────────────────────────────────────────────

def hash_url(url: str) -> str:
    """Generate a SHA-256 hash for a URL (used for deduplication)."""
    normalized = url.strip().lower().rstrip("/")
    return hashlib.sha256(normalized.encode()).hexdigest()


# ── Company CRUD ──────────────────────────────────────────────

def upsert_company(session: Session, name: str, career_page_url: str = None, **kwargs) -> Company:
    """Insert or update a company by name + career page URL."""
    existing = session.query(Company).filter(
        Company.name == name,
        Company.career_page_url == career_page_url,
    ).first()

    if existing:
        for k, v in kwargs.items():
            if hasattr(existing, k) and v is not None:
                setattr(existing, k, v)
        existing.updated_at = datetime.utcnow()
        session.commit()
        return existing

    company = Company(name=name, career_page_url=career_page_url, **kwargs)
    session.add(company)
    session.commit()
    logger.info(f"Added company: {name}")
    return company


def get_companies_to_check(session: Session, hours_since_last_check: int = 6) -> List[Company]:
    """Get companies whose career pages haven't been checked recently."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours_since_last_check)
    
    return session.query(Company).filter(
        Company.is_active == True,
        Company.career_page_url.isnot(None),
        (
            (Company.last_checked == None) |
            (Company.last_checked <= cutoff)
        ),
    ).all()


# ── Job CRUD ──────────────────────────────────────────────────

def upsert_job(session: Session, url: str, title: str, source: str, **kwargs) -> Optional[Job]:
    """Insert a job if it doesn't already exist (by URL hash). Returns None if duplicate."""
    url_h = hash_url(url)
    existing = session.query(Job).filter(Job.url_hash == url_h).first()
    if existing:
        return None  # duplicate

    job = Job(
        url=url,
        url_hash=url_h,
        title=title,
        source=source,
        **kwargs,
    )
    session.add(job)
    session.commit()
    logger.info(f"New job discovered: '{title}' from {source}")
    return job


def get_jobs_by_status(session: Session, status: str, limit: int = 100) -> List[Job]:
    """Get jobs with a given status, ordered by score descending."""
    return (
        session.query(Job)
        .filter(Job.status == status)
        .order_by(Job.relevance_score.desc().nullslast())
        .limit(limit)
        .all()
    )


def get_unscored_jobs(session: Session, limit: int = 50) -> List[Job]:
    """Get jobs that haven't been scored yet."""
    return (
        session.query(Job)
        .filter(Job.relevance_score == None, Job.status == "new")
        .limit(limit)
        .all()
    )


def is_already_applied(session: Session, url: str) -> bool:
    """Check if we've already applied to a job by its URL."""
    url_h = hash_url(url)
    return session.query(Job).filter(
        Job.url_hash == url_h,
        Job.status.in_(["applied", "flagged"]),
    ).first() is not None


# ── Application CRUD ─────────────────────────────────────────

def create_application(session: Session, job_id: int, method: str, **kwargs) -> Application:
    """Create a new application record."""
    app = Application(job_id=job_id, method=method, **kwargs)
    session.add(app)
    session.commit()
    return app


def log_application_event(session: Session, application_id: int, event: str, details: str = None,
                           screenshot_path: str = None):
    """Log an event for an application."""
    log_entry = ApplicationLog(
        application_id=application_id,
        event=event,
        details=details,
        screenshot_path=screenshot_path,
    )
    session.add(log_entry)
    session.commit()


# ── Statistics ────────────────────────────────────────────────

def get_daily_stats(session: Session) -> dict:
    """Get today's application statistics."""
    today = datetime.utcnow().date()
    total_applied = session.query(Application).filter(
        func.date(Application.applied_at) == today,
        Application.status == "applied",
    ).count()

    total_discovered = session.query(Job).filter(
        func.date(Job.discovered_at) == today,
    ).count()

    total_flagged = session.query(Job).filter(
        func.date(Job.discovered_at) == today,
        Job.status == "flagged",
    ).count()

    return {
        "date": str(today),
        "jobs_discovered": total_discovered,
        "applications_submitted": total_applied,
        "flagged_for_review": total_flagged,
    }


def get_weekly_stats(session: Session) -> dict:
    """Get this week's application statistics."""
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)

    total_applied = session.query(Application).filter(
        Application.applied_at >= week_ago,
        Application.status == "applied",
    ).count()

    total_discovered = session.query(Job).filter(
        Job.discovered_at >= week_ago,
    ).count()

    interviews = session.query(Application).filter(
        Application.applied_at >= week_ago,
        Application.status == "interview",
    ).count()

    responses = session.query(Application).filter(
        Application.applied_at >= week_ago,
        Application.response_received == True,
    ).count()

    response_rate = (responses / total_applied * 100) if total_applied > 0 else 0

    return {
        "period": f"{week_ago.date()} to {datetime.utcnow().date()}",
        "jobs_discovered": total_discovered,
        "applications_submitted": total_applied,
        "responses_received": responses,
        "response_rate": f"{response_rate:.1f}%",
        "interview_invites": interviews,
    }
