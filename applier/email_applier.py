"""
Email Applier — sends application emails with tailored resume and cover letter.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime

from loguru import logger

from config import settings
from database.db import get_session, create_application, log_application_event
from database.models import ApplicationStatus


class EmailApplier:
    """Sends job applications via email with attached resume and cover letter."""

    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password

    def apply(self, to_email: str, job_title: str, company_name: str,
              job_id: int, resume_path: str = None,
              cover_letter_text: str = None, cover_letter_path: str = None) -> bool:
        """Send an application email."""
        session = get_session()

        try:
            # Create application record
            app = create_application(session, job_id=job_id, method="email")
            log_application_event(session, app.id, "email_draft_started",
                                  f"To: {to_email}")

            if settings.dry_run:
                logger.info(f"[DRY RUN] Would send email to: {to_email} for '{job_title}' at {company_name}")
                return True

            # Build email
            msg = MIMEMultipart()
            msg["From"] = f"{settings.user_name} <{settings.smtp_user}>"
            msg["To"] = to_email
            msg["Subject"] = f"Application for {job_title} — {settings.user_name}"

            # Email body
            if cover_letter_text:
                body = cover_letter_text
            else:
                body = f"""Dear Hiring Manager,

I am writing to express my interest in the {job_title} position at {company_name}.

As an experienced {settings.experience_level.lower()}-level {settings.target_job_title.lower()} based in {settings.target_location}, I believe my skills and experience make me a strong candidate for this role.

Please find my resume attached for your review. I would welcome the opportunity to discuss how I can contribute to your team.

Thank you for your consideration.

Best regards,
{settings.user_name}
{settings.user_email}
{settings.user_phone}
{settings.linkedin_profile_url}
"""

            msg.attach(MIMEText(body, "plain"))

            # Attach resume
            resume = resume_path or settings.base_resume_path
            if resume and os.path.exists(resume):
                with open(resume, "rb") as f:
                    attachment = MIMEApplication(f.read(), _subtype="pdf")
                    filename = f"{settings.user_name.replace(' ', '_')}_Resume.pdf"
                    attachment.add_header("Content-Disposition", "attachment", filename=filename)
                    msg.attach(attachment)

            # Attach cover letter if file exists
            if cover_letter_path and os.path.exists(cover_letter_path):
                with open(cover_letter_path, "rb") as f:
                    cl_attachment = MIMEApplication(f.read(), _subtype="pdf")
                    cl_filename = f"{settings.user_name.replace(' ', '_')}_Cover_Letter.pdf"
                    cl_attachment.add_header("Content-Disposition", "attachment", filename=cl_filename)
                    msg.attach(cl_attachment)

            # Send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            # Update records
            app.status = ApplicationStatus.APPLIED.value
            app.applied_at = datetime.utcnow()
            if resume_path:
                app.tailored_resume_path = resume_path
            if cover_letter_path:
                app.cover_letter_path = cover_letter_path
            session.commit()

            log_application_event(session, app.id, "email_sent",
                                  f"Email sent to {to_email}")
            logger.info(f"✅ Email application sent to {to_email} for '{job_title}'")
            return True

        except Exception as e:
            logger.error(f"Email application failed: {e}")
            return False
        finally:
            session.close()
