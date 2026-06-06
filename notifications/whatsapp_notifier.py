"""
WhatsApp Notifier — REPLACED with free email-only notifications.
Original used paid Twilio API. Now everything goes through Gmail SMTP (free).
This module is kept for backward compatibility but redirects to email.
"""

from loguru import logger

from config import settings


class WhatsAppNotifier:
    """
    Replaced with email-only notifications (free).
    All methods now send via Gmail instead of paid Twilio WhatsApp.
    """

    def __init__(self):
        self._available = bool(settings.smtp_user and settings.smtp_password)
        if self._available:
            logger.info("Notifications: using Gmail SMTP (free)")
        else:
            logger.warning("Gmail SMTP not configured — notifications disabled")

    @property
    def is_available(self) -> bool:
        return self._available

    def send_message(self, message: str):
        """Send notification via email (free) instead of WhatsApp (paid)."""
        if not self._available:
            return

        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(message)
            msg["From"] = f"Job Agent <{settings.smtp_user}>"
            msg["To"] = settings.notification_email
            msg["Subject"] = "🤖 Job Agent Alert"

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info(f"Email alert sent: {message[:50]}...")
        except Exception as e:
            logger.error(f"Email notification failed: {e}")

    def send_high_relevance_alert(self, title: str, company: str, score: float, url: str):
        """Send a high-relevance job alert via email."""
        message = (
            f"🔥 HIGH-RELEVANCE JOB FOUND!\n\n"
            f"📋 {title}\n"
            f"🏢 {company}\n"
            f"⭐ Score: {score}/100\n\n"
            f"🔗 {url}"
        )
        self.send_message(message)

    def send_daily_summary(self, discovered: int, applied: int, flagged: int):
        """Send daily summary via email."""
        message = (
            f"📊 Daily Job Report\n\n"
            f"🔍 Jobs Found: {discovered}\n"
            f"✅ Applied: {applied}\n"
            f"⚠️ Flagged: {flagged}"
        )
        self.send_message(message)
