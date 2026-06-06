"""
ATS Keyword Optimizer — extracts ATS keywords from job descriptions
and ensures they are present in the tailored resume.
"""

import re
import json
from typing import List, Dict, Set
from collections import Counter

from loguru import logger

from ai.llm_client import LLMClient


class ATSOptimizer:
    """Extracts and optimizes for ATS (Applicant Tracking System) keywords."""

    # Common ATS-relevant keyword categories
    KEYWORD_CATEGORIES = {
        "technical_skills": [
            "python", "javascript", "typescript", "java", "c#", "c++", "go", "rust", "ruby", "php",
            "react", "angular", "vue", "node.js", "django", "flask", "spring", "express",
            "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins",
            "git", "ci/cd", "rest", "api", "graphql", "microservices",
            "machine learning", "ai", "data science", "deep learning",
            "html", "css", "sass", "webpack", "vite",
        ],
        "soft_skills": [
            "leadership", "communication", "teamwork", "problem-solving",
            "analytical", "strategic", "creative", "adaptable", "collaborative",
            "mentoring", "presentation", "stakeholder management",
        ],
        "methodologies": [
            "agile", "scrum", "kanban", "waterfall", "devops", "tdd", "bdd",
            "ci/cd", "pair programming", "code review", "sprint",
        ],
        "certifications": [
            "aws certified", "azure certified", "gcp certified",
            "pmp", "scrum master", "product owner",
            "cissp", "ceh", "comptia",
        ],
    }

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client

    def extract_keywords(self, job_description: str) -> Dict[str, List[str]]:
        """Extract ATS-relevant keywords from a job description."""
        desc_lower = job_description.lower()
        found = {}

        for category, keywords in self.KEYWORD_CATEGORIES.items():
            matches = [kw for kw in keywords if kw.lower() in desc_lower]
            if matches:
                found[category] = matches

        # Also extract custom keywords (capitalized phrases, multi-word terms)
        custom = self._extract_custom_keywords(job_description)
        if custom:
            found["custom_requirements"] = custom

        return found

    async def extract_keywords_ai(self, job_description: str) -> Dict[str, List[str]]:
        """Use AI to extract more nuanced ATS keywords."""
        if not self.llm or not self.llm.is_available:
            return self.extract_keywords(job_description)

        prompt = f"""Extract ALL ATS-relevant keywords from this job description.
Categorize them into:
1. technical_skills: programming languages, tools, frameworks
2. soft_skills: interpersonal and professional skills
3. qualifications: required degrees, certifications, years of experience
4. domain_knowledge: industry-specific knowledge
5. action_verbs: key action verbs used

Job Description:
{job_description[:3000]}

Return ONLY a JSON object with these categories as keys and arrays of keywords as values."""

        try:
            response = await self.llm.generate(prompt, max_tokens=1000, temperature=0.2)
            # Clean response (remove markdown code fences if present)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"AI keyword extraction failed: {e}")
            return self.extract_keywords(job_description)

    def check_resume_coverage(self, resume_text: str, keywords: Dict[str, List[str]]) -> Dict:
        """Check how many ATS keywords are present in the resume."""
        resume_lower = resume_text.lower()
        coverage = {}
        total_keywords = 0
        matched_keywords = 0

        for category, kw_list in keywords.items():
            matched = []
            missing = []
            for kw in kw_list:
                total_keywords += 1
                if kw.lower() in resume_lower:
                    matched.append(kw)
                    matched_keywords += 1
                else:
                    missing.append(kw)

            coverage[category] = {
                "matched": matched,
                "missing": missing,
                "coverage": f"{len(matched)}/{len(kw_list)}" if kw_list else "N/A",
            }

        overall = (matched_keywords / total_keywords * 100) if total_keywords > 0 else 0

        return {
            "overall_coverage": f"{overall:.0f}%",
            "total_keywords": total_keywords,
            "matched": matched_keywords,
            "categories": coverage,
        }

    def _extract_custom_keywords(self, text: str) -> List[str]:
        """Extract custom multi-word terms and requirements from text."""
        keywords = set()

        # Match "X years of experience" patterns
        exp_patterns = re.findall(r"\d+\+?\s*years?\s*(?:of\s*)?(?:experience|exp)", text, re.I)
        keywords.update(exp_patterns)

        # Match degree requirements
        degree_patterns = re.findall(
            r"(?:bachelor|master|phd|doctorate|degree)\s*(?:in\s+[\w\s]+)?",
            text, re.I
        )
        keywords.update(p.strip() for p in degree_patterns)

        # Match "experience with/in X" patterns
        exp_with = re.findall(r"experience\s+(?:with|in)\s+([\w\s,]+?)(?:\.|;|$)", text, re.I)
        for match in exp_with:
            for item in match.split(","):
                cleaned = item.strip()
                if 2 < len(cleaned) < 50:
                    keywords.add(cleaned)

        return list(keywords)
