"""
AI Cover Letter Generator — creates personalized cover letters for each job.
"""

import os
from datetime import datetime

from loguru import logger

from config import settings
from ai.llm_client import LLMClient


class CoverLetterGenerator:
    """Generates tailored cover letters using AI."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "tailored")
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate(self, job_title: str, job_description: str,
                       company_name: str = "", resume_text: str = "") -> dict:
        """
        Generate a tailored cover letter.
        Returns: {"text": str, "file_path": str}
        """
        if not self.llm.is_available:
            logger.warning("LLM not available. Generating template cover letter.")
            return self._template_cover_letter(job_title, company_name)

        system_prompt = """You are an expert career coach and cover letter writer.
Write a compelling, personalized cover letter that:
- Opens with a strong hook (not "I am writing to apply...")
- Demonstrates knowledge of the company
- Highlights 2-3 most relevant achievements from the resume
- Uses keywords from the job description naturally
- Shows enthusiasm and cultural fit
- Is concise (250-350 words)
- Ends with a clear call to action
- Maintains professional yet personable tone
- DO NOT use generic filler phrases"""

        prompt = f"""Write a cover letter for this job application:

JOB TITLE: {job_title}
COMPANY: {company_name}
JOB DESCRIPTION:
{job_description[:2000]}

CANDIDATE DETAILS:
- Name: {settings.user_name}
- Email: {settings.user_email}
- Phone: {settings.user_phone}
- Location: {settings.target_location}
- Experience Level: {settings.experience_level}

CANDIDATE RESUME (key points):
{resume_text[:2000] if resume_text else "Experience as a " + settings.target_job_title}

Write the cover letter now. Format it as a proper letter with date, greeting, body paragraphs, and sign-off."""

        try:
            response = await self.llm.generate(
                prompt,
                system_prompt=system_prompt,
                max_tokens=1500,
                temperature=0.7,
            )

            # Save to file
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_company = "".join(c for c in company_name if c.isalnum() or c in " -_")[:30]
            filename = f"cover_letter_{safe_company}_{timestamp}.txt"
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "w") as f:
                f.write(response)

            logger.info(f"Cover letter saved: {filepath}")

            return {
                "text": response,
                "file_path": filepath,
            }

        except Exception as e:
            logger.error(f"Cover letter generation failed: {e}")
            return self._template_cover_letter(job_title, company_name)

    def _template_cover_letter(self, job_title: str, company_name: str) -> dict:
        """Generate a basic template cover letter when AI is unavailable."""
        text = f"""Dear Hiring Manager,

I am excited to apply for the {job_title} position at {company_name}. As an experienced {settings.experience_level.lower()}-level professional based in {settings.target_location}, I am confident in my ability to make a meaningful contribution to your team.

My background in {settings.target_job_title.lower()} has equipped me with the skills and experience needed for this role. I am passionate about delivering high-quality work and am eager to bring my expertise to {company_name}.

I would welcome the opportunity to discuss how my experience aligns with your needs. Please feel free to contact me at {settings.user_email} or {settings.user_phone}.

Thank you for considering my application.

Best regards,
{settings.user_name}
"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_company = "".join(c for c in company_name if c.isalnum() or c in " -_")[:30]
        filename = f"cover_letter_{safe_company}_{timestamp}.txt"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w") as f:
            f.write(text)

        return {"text": text, "file_path": filepath}
