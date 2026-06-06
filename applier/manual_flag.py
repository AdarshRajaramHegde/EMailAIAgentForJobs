"""
Manual Flag System — detects jobs requiring manual intervention
(video interviews, assessments, portfolios) and flags them for review.
"""

import re
from typing import List, Tuple

from loguru import logger

from database.db import get_session
from database.models import Job, JobStatus


class ManualFlagDetector:
    """Detects applications that require manual steps."""

    # Patterns that indicate extra steps are needed
    FLAG_PATTERNS = {
        "video_interview": [
            r"video\s*interview",
            r"hirevue",
            r"spark\s*hire",
            r"video\s*screening",
            r"recorded\s*interview",
            r"one-way\s*interview",
        ],
        "assessment": [
            r"assessment",
            r"coding\s*challenge",
            r"coding\s*test",
            r"technical\s*test",
            r"aptitude\s*test",
            r"psychometric",
            r"hackerrank",
            r"codility",
            r"leetcode",
            r"take.?home",
        ],
        "portfolio": [
            r"portfolio",
            r"work\s*samples",
            r"design\s*samples",
            r"code\s*samples",
            r"github\s*profile",
            r"project\s*examples",
        ],
        "cover_letter_required": [
            r"cover\s*letter\s*required",
            r"must\s*include\s*cover\s*letter",
            r"cover\s*letter\s*is\s*mandatory",
        ],
        "referral_needed": [
            r"referral\s*required",
            r"employee\s*referral",
            r"internal\s*candidates\s*only",
        ],
        "security_clearance": [
            r"security\s*clearance",
            r"background\s*check\s*required",
            r"dbs\s*check",
            r"garda\s*vetting",
        ],
    }

    def check_job(self, title: str, description: str) -> Tuple[bool, List[str]]:
        """
        Check if a job requires manual intervention.
        Returns: (should_flag, list_of_reasons)
        """
        text = f"{title} {description}".lower()
        reasons = []

        for flag_type, patterns in self.FLAG_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.I):
                    reasons.append(flag_type)
                    break  # Only need one match per category

        should_flag = len(reasons) > 0
        return should_flag, reasons

    def flag_job(self, job_id: int, reasons: List[str]):
        """Mark a job as flagged for manual review."""
        session = get_session()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FLAGGED.value
                job.flag_reason = ", ".join(reasons)
                session.commit()
                logger.info(f"🚩 Job flagged: ID={job_id}, Reasons: {', '.join(reasons)}")
        finally:
            session.close()

    def get_flagged_jobs(self) -> List[Job]:
        """Get all flagged jobs."""
        session = get_session()
        try:
            return session.query(Job).filter(Job.status == JobStatus.FLAGGED.value).all()
        finally:
            session.close()
