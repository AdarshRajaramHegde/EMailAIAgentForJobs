"""
Report Generator — generates analytics data for notifications.
"""

from datetime import datetime, timedelta
from typing import Dict, List

from loguru import logger
from sqlalchemy import func

from database.db import get_session
from database.models import Job, Application, Company, ApplicationStatus, JobStatus


class ReportGenerator:
    """Generates analytics reports."""

    def generate_daily_report(self) -> Dict:
        """Generate a comprehensive daily report."""
        session = get_session()
        try:
            today = datetime.utcnow().date()

            # Jobs discovered today
            new_jobs = session.query(Job).filter(
                func.date(Job.discovered_at) == today
            ).all()

            # Applications submitted today
            applied_today = session.query(Application).filter(
                func.date(Application.applied_at) == today,
                Application.status == ApplicationStatus.APPLIED.value,
            ).all()

            # Flagged jobs
            flagged = session.query(Job).filter(
                Job.status == JobStatus.FLAGGED.value,
                func.date(Job.discovered_at) == today,
            ).all()

            # Source breakdown
            source_counts = {}
            for job in new_jobs:
                source_counts[job.source] = source_counts.get(job.source, 0) + 1

            # Score distribution
            scored = [j for j in new_jobs if j.relevance_score]
            avg_score = sum(j.relevance_score for j in scored) / len(scored) if scored else 0
            high_score_count = sum(1 for j in scored if j.relevance_score >= 90)

            return {
                "date": str(today),
                "total_discovered": len(new_jobs),
                "total_applied": len(applied_today),
                "total_flagged": len(flagged),
                "source_breakdown": source_counts,
                "avg_relevance_score": round(avg_score, 1),
                "high_relevance_count": high_score_count,
                "applied_jobs": [
                    {
                        "title": app.job.title,
                        "company": app.job.company_name,
                        "score": app.job.relevance_score,
                        "source": app.job.source,
                        "method": app.method,
                    }
                    for app in applied_today if app.job
                ],
                "flagged_jobs": [
                    {
                        "title": j.title,
                        "company": j.company_name,
                        "reason": j.flag_reason,
                        "url": j.url,
                    }
                    for j in flagged
                ],
            }
        finally:
            session.close()

    def generate_weekly_report(self) -> Dict:
        """Generate a comprehensive weekly report."""
        session = get_session()
        try:
            week_ago = datetime.utcnow() - timedelta(days=7)

            total_jobs = session.query(Job).filter(Job.discovered_at >= week_ago).count()
            total_applied = session.query(Application).filter(
                Application.applied_at >= week_ago,
                Application.status == ApplicationStatus.APPLIED.value,
            ).count()

            interviews = session.query(Application).filter(
                Application.created_at >= week_ago,
                Application.status == ApplicationStatus.INTERVIEW.value,
            ).count()

            responses = session.query(Application).filter(
                Application.created_at >= week_ago,
                Application.response_received == True,
            ).count()

            # Companies applied to
            companies = session.query(
                Job.company_name, func.count(Job.id)
            ).filter(
                Job.discovered_at >= week_ago,
                Job.status == JobStatus.APPLIED.value,
            ).group_by(Job.company_name).all()

            # Method breakdown
            methods = session.query(
                Application.method, func.count(Application.id)
            ).filter(
                Application.applied_at >= week_ago,
            ).group_by(Application.method).all()

            response_rate = (responses / total_applied * 100) if total_applied > 0 else 0

            return {
                "period": f"{week_ago.date()} to {datetime.utcnow().date()}",
                "total_discovered": total_jobs,
                "total_applied": total_applied,
                "interview_invites": interviews,
                "responses": responses,
                "response_rate": f"{response_rate:.1f}%",
                "top_companies": [{"name": c[0], "count": c[1]} for c in companies[:10]],
                "method_breakdown": {m[0]: m[1] for m in methods},
            }
        finally:
            session.close()
