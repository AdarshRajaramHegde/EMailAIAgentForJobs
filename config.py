"""
Centralized configuration loaded from .env via Pydantic Settings.
100% FREE stack: Gemini API, Supabase, Gmail SMTP, GitHub Actions.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os

# Ensure .env is loaded from project root
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


class Settings(BaseSettings):
    """All application settings, loaded from environment / .env file."""

    # ── User Profile ──────────────────────────────────────────
    user_name: str = "Adarsh Rajaram Hegde"
    user_email: str = "contactadarshr@gmail.com"
    user_phone: str = "+353 89 451 6970"
    target_job_title: str = "Senior Product Manager"
    target_job_titles: str = "Senior Product Manager, Product Manager, Product Owner, Senior Product Owner, Technical Product Manager, Technical Program Manager, Product Leader, Product Strategy Leader"
    experience_level: str = "Senior"
    preferred_salary_min: int = 75000
    preferred_salary_max: int = 110000
    preferred_salary_currency: str = "EUR"
    preferred_industries: str = "Tech,Finance,Retail,Healthcare,Consulting"
    target_location: str = "Dublin, Ireland"
    base_resume_path: str = "ai/Resumes/Resumes/Adarsh Hegde - PM CV.pdf"
    base_resume_paths: str = "ai/Resumes/Resumes/Adarsh Hegde - PL CV.pdf, ai/Resumes/Resumes/Adarsh Hegde - PM CV.pdf, ai/Resumes/Resumes/Adarsh Hegde - PM VV.pdf, ai/Resumes/Resumes/Adarsh Hegde - PM.pdf, ai/Resumes/Resumes/Adarsh Hegde - Product Manager CV.pdf, ai/Resumes/Resumes/Adarsh Hegde - SA CV.pdf, ai/Resumes/Resumes/Adarsh Hegde - SPM CV.pdf, ai/Resumes/Resumes/Adarsh Hegde - SPMNS.pdf, ai/Resumes/Resumes/Adarsh Hegde - SPMTDVPS.pdf, ai/Resumes/Resumes/Adarsh Hegde - SPMV.pdf, ai/Resumes/Resumes/Adarsh Hegde - Senior BA Resume.pdf, ai/Resumes/Resumes/Adarsh Hegde - TPM N.pdf, ai/Resumes/Resumes/Adarsh Hegde - TPM.pdf, ai/Resumes/Resumes/Adarsh Hegde DPM CV.pdf, ai/Resumes/Resumes/Adarsh Hegde DPM-CV.pdf, ai/Resumes/Resumes/Adarsh Hegde PM CV-F.pdf, ai/Resumes/Resumes/Adarsh Hegde- DPM.pdf, ai/Resumes/Resumes/Adarsh Hegde- NBA.pdf, ai/Resumes/Resumes/Adarsh Hegde- SPM-AI.pdf, ai/Resumes/Resumes/Adarsh Hegde- SPON.pdf, ai/Resumes/Resumes/Adarsh Hegde-SPM CV.pdf, ai/Resumes/Resumes/Adarsh Hegde-SPMG.pdf, ai/Resumes/Resumes/Adarsh Hegde-SPMTNN.pdf, ai/Resumes/Resumes/Adarsh- SPMT.pdf, ai/Resumes/Resumes/Adarsh-CV (M).pdf, ai/Resumes/Resumes/Adarsh-Hegde-SPM.pdf, ai/Resumes/Resumes/AdarshHegde - CVN.pdf"
    linkedin_profile_url: str = "https://www.linkedin.com/in/contactadarshrajaram"

    # ── AI: Google Gemini (FREE) ──────────────────────────────
    gemini_api_key: str = ""

    # ── Database ──────────────────────────────────────────────
    supabase_url: str = ""
    supabase_key: str = ""
    database_url: str = "sqlite:///data/jobagent.db"

    # ── Email / Notifications (FREE) ──────────────────────────
    # Option A: Gmail SMTP (Requires 2FA + App Password)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    
    # Option B: Resend (FREE — 3,000 emails/month, easier setup)
    # Get free key at: https://resend.com
    resend_api_key: str = ""
    
    notification_email: str = ""

    # ── LinkedIn ──────────────────────────────────────────────
    linkedin_email: str = ""
    linkedin_password: str = ""

    # ── Workday ───────────────────────────────────────────────
    workday_email: str = ""
    workday_password: str = ""

    # ── SerpAPI (optional free tier) ──────────────────────────
    serpapi_key: str = ""

    # Scrapers
    scrape_interval_hours: int = 2
    career_page_check_hours: int = 6
    request_delay_min: int = 2
    request_delay_max: int = 5
    use_proxy: bool = False
    proxy_url: str = ""

    # ── Agent Behavior ────────────────────────────────────────
    dry_run: bool = False
    apply_automatically: bool = False
    email_all_listings: bool = True
    min_relevance_score: int = 70
    min_experience_years: int = 3
    high_relevance_threshold: int = 90
    max_daily_applications: int = 50

    # ── SerpAPI (optional free tier) ──────────────────────────
    serpapi_key: str = ""

    # ── Helpers ───────────────────────────────────────────────
    @property
    def industries_list(self) -> List[str]:
        return [i.strip() for i in self.preferred_industries.split(",") if i.strip()]

    @property
    def titles_list(self) -> List[str]:
        return [t.strip() for t in self.target_job_titles.split(",") if t.strip()]

    @property
    def resumes_list(self) -> List[str]:
        return [r.strip() for r in self.base_resume_paths.split(",") if r.strip()]

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    class Config:
        env_file = ENV_PATH
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton
settings = Settings()
