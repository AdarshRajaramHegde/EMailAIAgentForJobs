"""
Email Notifier — sends daily summaries, high-relevance alerts, and weekly reports.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from loguru import logger
from jinja2 import Template
from sqlalchemy import func

from config import settings
from database.db import get_session, get_daily_stats, get_weekly_stats
from database.models import Job, Application, JobStatus


class EmailNotifier:
    """Sends email notifications via Resend (preferred free) or Gmail SMTP."""

    def __init__(self):
        self.resend_key = settings.resend_api_key
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password

    def send_daily_summary(self):
        """Send daily summary of all activity."""
        session = get_session()
        try:
            stats = get_daily_stats(session)

            # Get today's discovered jobs (with links)
            today = datetime.utcnow().date()
            new_jobs = (
                session.query(Job)
                .filter(func.date(Job.discovered_at) == today)
                .order_by(Job.relevance_score.desc().nullslast())
                .limit(100)
                .all()
            )

            # Get today's applied jobs
            applied_jobs = (
                session.query(Job)
                .join(Application)
                .filter(
                    Application.status == "applied",
                    func.date(Application.applied_at) == today,
                )
                .order_by(Job.relevance_score.desc())
                .limit(50)
                .all()
            )

            # Get flagged jobs
            flagged_jobs = (
                session.query(Job)
                .filter(
                    Job.status == JobStatus.FLAGGED.value,
                    func.date(Job.discovered_at) == today,
                )
                .order_by(Job.discovered_at.desc())
                .limit(20)
                .all()
            )

            html = self._render_daily_summary(stats, new_jobs, applied_jobs, flagged_jobs)
            self._send_email(
                subject=f"🎯 Daily Job Report — {stats['date']}",
                html_body=html,
            )
            logger.info(f"Daily summary sent: {len(new_jobs)} jobs discovered")

        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
        finally:
            session.close()

    def send_new_jobs_email(self, jobs: list):
        """Send an immediate email with a list of newly discovered jobs."""
        if not jobs:
            return

        date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        
        jobs_html = ""
        for job in jobs:
            score_color = "#22c55e" if (job.relevance_score or 0) >= 80 else "#eab308" if (job.relevance_score or 0) >= 60 else "#ef4444"
            jobs_html += f"""
            <div style="margin-bottom: 20px; padding: 15px; border: 1px solid #e5e7eb; border-radius: 8px;">
                <h3 style="margin: 0 0 8px 0; color: #1e3a5f;">{job.title}</h3>
                <p style="margin: 0 0 4px 0; color: #4b5563;">🏢 <strong>{job.company_name}</strong> | 📍 {job.location or 'Remote'}</p>
                <p style="margin: 0 0 8px 0; color: #6b7280; font-size: 14px;">Source: {job.source} | Score: <span style="color: {score_color}; font-weight: bold;">{job.relevance_score or 'N/A'}</span></p>
                <a href="{job.url}" style="display: inline-block; background: #2563eb; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 14px;">View & Apply →</a>
            </div>"""

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #2563eb, #1e3a5f); padding: 24px; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0;">🆕 New Jobs Discovered</h1>
                <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0;">{date_str}</p>
            </div>
            <div style="background: white; padding: 24px; border: 1px solid #e5e7eb; border-radius: 0 0 12px 12px;">
                <p style="color: #374151; margin-bottom: 20px;">The AI agent has found <strong>{len(jobs)}</strong> new job listings that match your criteria.</p>
                {jobs_html}
                <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
                <p style="color: #9ca3af; font-size: 12px; text-align: center;">AI Job Application Agent — Real-time Notification</p>
            </div>
        </div>
        """

        self._send_email(
            subject=f"🚀 {len(jobs)} New Jobs Found: {jobs[0].title}...",
            html_body=html,
        )
        logger.info(f"New jobs email sent with {len(jobs)} listings")

    def send_high_relevance_alert(self, job: Job):
        """Send an immediate alert for a high-relevance job (90+)."""
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 24px; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">🔥 High-Relevance Job Found!</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0;">Score: {job.relevance_score}/100</p>
            </div>
            <div style="background: #fff; padding: 24px; border: 1px solid #eee; border-radius: 0 0 12px 12px;">
                <h2 style="color: #333; margin-top: 0;">{job.title}</h2>
                <p style="color: #666;">🏢 {job.company_name}</p>
                <p style="color: #666;">📍 {job.location}</p>
                <p style="color: #666;">🔗 Source: {job.source}</p>
                <a href="{job.url}" style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; margin-top: 12px;">View Job →</a>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">AI Job Application Agent — Auto-alert for score ≥ {settings.high_relevance_threshold}</p>
            </div>
        </div>
        """

        self._send_email(
            subject=f"🔥 Score {job.relevance_score}: {job.title} at {job.company_name}",
            html_body=html,
        )
        logger.info(f"High-relevance alert sent: {job.title} (score {job.relevance_score})")

    def send_weekly_report(self):
        """Send weekly analytics report."""
        session = get_session()
        try:
            stats = get_weekly_stats(session)

            # Get top-scoring jobs
            top_jobs = (
                session.query(Job)
                .filter(Job.relevance_score.isnot(None))
                .order_by(Job.relevance_score.desc())
                .limit(10)
                .all()
            )

            html = self._render_weekly_report(stats, top_jobs)
            self._send_email(
                subject=f"📊 Weekly Job Report — {stats['period']}",
                html_body=html,
            )
            logger.info("Weekly report sent")

        except Exception as e:
            logger.error(f"Failed to send weekly report: {e}")
        finally:
            session.close()

    def _render_daily_summary(self, stats: dict, new_jobs: list, applied_jobs: list, flagged_jobs: list) -> str:
        """Render daily summary HTML."""
        new_jobs_html = ""
        for job in new_jobs:
            score_color = "#22c55e" if (job.relevance_score or 0) >= 80 else "#eab308" if (job.relevance_score or 0) >= 60 else "#ef4444"
            new_jobs_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;"><a href="{job.url}" style="color: #2563eb; text-decoration: none;">{job.title}</a></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{job.company_name}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;"><span style="color: {score_color}; font-weight: bold;">{job.relevance_score or 'N/A'}</span></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{job.source}</td>
            </tr>"""

        applied_html = ""
        for job in applied_jobs:
            score_color = "#22c55e" if (job.relevance_score or 0) >= 80 else "#eab308" if (job.relevance_score or 0) >= 60 else "#ef4444"
            applied_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{job.title}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{job.company_name}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;"><span style="color: {score_color}; font-weight: bold;">{job.relevance_score or 'N/A'}</span></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{job.source}</td>
            </tr>"""

        flagged_html = ""
        for job in flagged_jobs:
            flagged_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{job.title}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{job.company_name}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">⚠️ {job.flag_reason}</td>
            </tr>"""

        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #1e3a5f, #2563eb); padding: 24px; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0;">📋 Daily Job Report</h1>
                <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0;">{stats['date']}</p>
            </div>
            <div style="background: white; padding: 24px; border: 1px solid #e5e7eb;">
                <div style="display: flex; gap: 16px; margin-bottom: 24px;">
                    <div style="flex: 1; background: #f0fdf4; padding: 16px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 32px; font-weight: bold; color: #22c55e;">{stats['jobs_discovered']}</div>
                        <div style="color: #666; font-size: 12px;">Jobs Found</div>
                    </div>
                    <div style="flex: 1; background: #eff6ff; padding: 16px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 32px; font-weight: bold; color: #2563eb;">{stats['applications_submitted']}</div>
                        <div style="color: #666; font-size: 12px;">Applied</div>
                    </div>
                    <div style="flex: 1; background: #fef9c3; padding: 16px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 32px; font-weight: bold; color: #eab308;">{stats['flagged_for_review']}</div>
                        <div style="color: #666; font-size: 12px;">Flagged</div>
                    </div>
                </div>

                <h3 style="color: #1e3a5f;">🆕 New Jobs Discovered</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f3f4f6;">
                            <th style="padding: 8px; text-align: left;">Title</th>
                            <th style="padding: 8px; text-align: left;">Company</th>
                            <th style="padding: 8px; text-align: left;">Score</th>
                            <th style="padding: 8px; text-align: left;">Source</th>
                        </tr>
                    </thead>
                    <tbody>{new_jobs_html or '<tr><td colspan="4" style="padding: 16px; text-align: center; color: #999;">No jobs discovered today</td></tr>'}</tbody>
                </table>

                {"<h3 style='color: #1e3a5f; margin-top: 24px;'>✅ Recently Applied</h3><table style='width: 100%; border-collapse: collapse;'><thead><tr style='background: #f3f4f6;'><th style='padding: 8px; text-align: left;'>Title</th><th style='padding: 8px; text-align: left;'>Company</th><th style='padding: 8px; text-align: left;'>Score</th><th style='padding: 8px; text-align: left;'>Source</th></tr></thead><tbody>" + applied_html + "</tbody></table>" if applied_html else ""}

                {"<h3 style='color: #1e3a5f; margin-top: 24px;'>⚠️ Flagged for Manual Review</h3><table style='width: 100%; border-collapse: collapse;'><thead><tr style='background: #fef9c3;'><th style='padding: 8px; text-align: left;'>Title</th><th style='padding: 8px; text-align: left;'>Company</th><th style='padding: 8px; text-align: left;'>Reason</th></tr></thead><tbody>" + flagged_html + "</tbody></table>" if flagged_html else ""}
            </div>
            <div style="background: #f9fafb; padding: 16px; text-align: center; border-radius: 0 0 12px 12px; border: 1px solid #e5e7eb; border-top: none;">
                <p style="color: #9ca3af; font-size: 12px; margin: 0;">AI Job Application Agent — Automated Report</p>
            </div>
        </div>
        """

    def _render_weekly_report(self, stats: dict, top_jobs: list) -> str:
        """Render weekly report HTML."""
        jobs_html = ""
        for job in top_jobs:
            jobs_html += f"<tr><td style='padding: 8px;'>{job.title}</td><td style='padding: 8px;'>{job.company_name}</td><td style='padding: 8px; font-weight: bold;'>{job.relevance_score}</td></tr>"

        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #7c3aed, #a855f7); padding: 24px; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0;">📊 Weekly Analytics Report</h1>
                <p style="color: rgba(255,255,255,0.8);">{stats['period']}</p>
            </div>
            <div style="background: white; padding: 24px; border: 1px solid #e5e7eb;">
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
                    <tr><td style="padding: 12px; font-weight: bold;">Jobs Discovered</td><td style="padding: 12px; font-size: 24px;">{stats['jobs_discovered']}</td></tr>
                    <tr style="background: #f9fafb;"><td style="padding: 12px; font-weight: bold;">Applications Sent</td><td style="padding: 12px; font-size: 24px;">{stats['applications_submitted']}</td></tr>
                    <tr><td style="padding: 12px; font-weight: bold;">Responses</td><td style="padding: 12px; font-size: 24px;">{stats['responses_received']}</td></tr>
                    <tr style="background: #f9fafb;"><td style="padding: 12px; font-weight: bold;">Response Rate</td><td style="padding: 12px; font-size: 24px;">{stats['response_rate']}</td></tr>
                    <tr><td style="padding: 12px; font-weight: bold;">Interview Invites</td><td style="padding: 12px; font-size: 24px; color: #22c55e;">🎉 {stats['interview_invites']}</td></tr>
                </table>
                <h3>Top Scoring Jobs</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead><tr style="background: #f3f4f6;"><th style="padding: 8px; text-align: left;">Title</th><th style="padding: 8px;">Company</th><th style="padding: 8px;">Score</th></tr></thead>
                    <tbody>{jobs_html}</tbody>
                </table>
            </div>
            <div style="background: #f9fafb; padding: 16px; text-align: center; border-radius: 0 0 12px 12px;">
                <p style="color: #9ca3af; font-size: 12px;">AI Job Application Agent — Weekly Report</p>
            </div>
        </div>
        """

    def _send_email(self, subject: str, html_body: str):
        """Send an HTML email via Resend or SMTP."""
        if self.resend_key:
            try:
                import httpx
                response = httpx.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.resend_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": "Job Agent <onboarding@resend.dev>",
                        "to": settings.notification_email,
                        "subject": subject,
                        "html": html_body,
                    },
                    timeout=10.0
                )
                if response.status_code in [200, 201]:
                    logger.info("Email sent via Resend")
                    return
                else:
                    logger.warning(f"Resend failed ({response.status_code}): {response.text}. Falling back to SMTP...")
            except Exception as e:
                logger.warning(f"Resend error: {e}. Falling back to SMTP...")

        # Fallback to SMTP
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Job Agent <{settings.smtp_user}>"
        msg["To"] = settings.notification_email
        msg["Subject"] = subject

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
