"""
AI Resume Tailor — reads job descriptions and tailors the user's resume.
"""

import os
import json
from datetime import datetime
from typing import Optional

from loguru import logger

from config import settings
from ai.llm_client import LLMClient


class ResumeTailor:
    """Tailors resumes to specific job descriptions using AI."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()
        self.base_resume_text = self._load_base_resume()
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "tailored")
        os.makedirs(self.output_dir, exist_ok=True)

    def _load_base_resume(self) -> str:
        """Load the base resume text from the default configuration."""
        return self._load_resume_text(settings.base_resume_path)

    def _load_resume_text(self, resume_path: str) -> str:
        """Load resume text from a specific path."""
        if not os.path.exists(resume_path):
            logger.warning(f"Resume not found at {resume_path}. Using placeholder.")
            return self._placeholder_resume(resume_path)

        # Try PDF
        if resume_path.endswith(".pdf"):
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(resume_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except Exception as e:
                logger.error(f"Failed to read PDF resume: {e}")
                return self._placeholder_resume(resume_path)

        # Try plain text / docx
        elif resume_path.endswith(".docx"):
            try:
                from docx import Document
                doc = Document(resume_path)
                return "\n".join(p.text for p in doc.paragraphs)
            except Exception as e:
                logger.error(f"Failed to read DOCX resume: {e}")
                return self._placeholder_resume(resume_path)

        else:
            try:
                with open(resume_path, "r") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read resume: {e}")
                return self._placeholder_resume(resume_path)

    def _placeholder_resume(self, resume_path: str = None) -> str:
        path = resume_path or settings.base_resume_path
        return f"""
{settings.user_name}
{settings.user_email} | {settings.user_phone}
{settings.linkedin_profile_url}

PROFESSIONAL SUMMARY
Experienced {settings.experience_level} {settings.target_job_title} based in {settings.target_location}.

SKILLS
[Please add your base resume to: {path}]

EXPERIENCE
[Add your experience]

EDUCATION
[Add your education]
"""

    async def tailor_resume(self, job_title: str, job_description: str,
                            company_name: str = "", base_resume_path: str = None) -> dict:
        """
        Generate a tailored resume for a specific job.
        Returns: {"text": str, "file_path": str, "keywords_matched": list}
        """
        # Load the specific resume if provided, otherwise use the one loaded in __init__
        resume_text = self.base_resume_text
        if base_resume_path:
            resume_text = self._load_resume_text(base_resume_path)

        if not self.llm.is_available:
            logger.warning("LLM not available. Returning base resume.")
            return {"text": resume_text, "file_path": None, "keywords_matched": []}

        system_prompt = """You are an expert resume writer and ATS optimization specialist.
Your job is to tailor a candidate's resume for a specific job posting.
Rules:
- Keep all factual information from the original resume
- Reorder and reword bullet points to emphasize relevant experience
- Add keywords from the job description naturally into the resume
- Optimize for ATS (Applicant Tracking Systems)
- Maintain professional formatting
- Do NOT fabricate experience or skills the candidate doesn't have
- Output only the tailored resume text, nothing else"""

        prompt = f"""Tailor this resume for the following job:

JOB TITLE: {job_title}
COMPANY: {company_name}
JOB DESCRIPTION:
{job_description[:3000]}

ORIGINAL RESUME:
{resume_text}

Return the tailored resume text optimized for this specific job. Include a section at the end called "KEYWORDS MATCHED" listing the keywords you incorporated."""

        try:
            response = await self.llm.generate(
                prompt,
                system_prompt=system_prompt,
                max_tokens=3000,
                temperature=0.3,  # Low temp for accuracy
            )

            # Extract keywords
            keywords = []
            if "KEYWORDS MATCHED" in response:
                kw_section = response.split("KEYWORDS MATCHED")[-1]
                keywords = [k.strip().strip("-•").strip() for k in kw_section.split("\n") if k.strip()]

            # Save to file
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_company = "".join(c for c in company_name if c.isalnum() or c in " -_")[:30]
            filename = f"resume_{safe_company}_{timestamp}.txt"
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "w") as f:
                f.write(response)

            logger.info(f"Tailored resume saved: {filepath}")

            return {
                "text": response,
                "file_path": filepath,
                "keywords_matched": keywords,
            }

        except Exception as e:
            logger.error(f"Resume tailoring failed: {e}")
            return {"text": self.base_resume_text, "file_path": None, "keywords_matched": []}
