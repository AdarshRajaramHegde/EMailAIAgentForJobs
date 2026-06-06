"""
AI-Powered Relevance Scorer — scores each job 0-100 based on match quality.
"""

import json
import re
from typing import Optional, Dict
from loguru import logger

from config import settings


class RelevanceScorer:
    """Scores job listings for relevance using a mix of rule-based and AI scoring."""

    # Weight distribution (total = 100)
    WEIGHTS = {
        "title_match": 30,
        "location_match": 15,
        "experience_match": 15,
        "salary_match": 15,
        "skills_match": 15,
        "industry_match": 10,
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def score(self, title: str, description: str = "", location: str = "",
              salary_min: float = None, salary_max: float = None,
              company_name: str = "", **kwargs) -> Dict:
        """
        Score a job from 0-100 with breakdown.
        Returns: {"score": 0-100, "breakdown": {...}}
        """
        breakdown = {}

        # 1. Title match (0-30)
        breakdown["title_match"] = self._score_title(title)

        # 2. Location match (0-15)
        breakdown["location_match"] = self._score_location(location)

        # 3. Experience match (0-15)
        breakdown["experience_match"] = self._score_experience(title, description)

        # 4. Salary match (0-15)
        breakdown["salary_match"] = self._score_salary(salary_min, salary_max)

        # 5. Skills/keyword match (0-15)
        breakdown["skills_match"] = self._score_skills(description)

        # 6. Industry match (0-10)
        breakdown["industry_match"] = self._score_industry(company_name, description)

        total = sum(breakdown.values())
        total = min(100, max(0, total))  # clamp

        return {
            "score": round(total, 1),
            "breakdown": breakdown,
        }

    def select_best_resume_path(self, title: str, description: str) -> str:
        """Select the most relevant resume file based on keywords in the job title/description."""
        resumes = settings.resumes_list
        if not resumes:
            return settings.base_resume_path

        title_lower = title.lower()
        desc_lower = description.lower()

        # 1. AI / ML Product Manager
        if "ai" in title_lower or "machine learning" in title_lower or "artificial intelligence" in title_lower:
            for r in resumes:
                if "spm-ai" in r.lower() or "ai" in r.lower():
                    return r

        # 2. Technical Product Manager / Technical Program Manager / Scrum Master / Solutions Architect
        if "technical" in title_lower or "tpm" in title_lower or "architect" in title_lower or "system" in title_lower:
            for keyword in ["tpm", "technical", "architect"]:
                for r in resumes:
                    if keyword in r.lower():
                        return r

        # 3. Director of Product / Director / Lead / VP / Delivery
        if "director" in title_lower or "vp" in title_lower or "head" in title_lower or "delivery" in title_lower or "lead" in title_lower:
            for r in resumes:
                if "dpm" in r.lower():
                    return r
            for r in resumes:
                if "leader" in r.lower() or "pl" in r.lower():
                    return r

        # 4. Product Owner / Senior Product Owner
        if "owner" in title_lower or "po" in title_lower:
            for r in resumes:
                if "spon" in r.lower() or "owner" in r.lower():
                    return r

        # 5. Business Analyst / Systems Analyst / Scrum Master
        if "analyst" in title_lower or "ba" in title_lower or "scrum" in title_lower:
            for keyword in ["ba", "analyst", "scrum"]:
                for r in resumes:
                    if keyword in r.lower():
                        return r

        # 6. Senior Product Manager / Senior
        if "senior" in title_lower or "sr" in title_lower or "staff" in title_lower:
            for r in resumes:
                if "spm" in r.lower() or "senior" in r.lower():
                    return r

        # 7. Default Product Manager / general fallback
        for keyword in ["pm cv", "product manager", "pm.pdf", "general"]:
            for r in resumes:
                if keyword in r.lower():
                    return r

        # Ultimate fallback
        return settings.base_resume_path

    async def score_with_ai(self, title: str, description: str, company_name: str = "") -> Dict:
        """Use LLM to get a more nuanced relevance score against the best pre-selected resume."""
        if not self.llm:
            return self.score(title, description, company_name=company_name)

        resume_path = self.select_best_resume_path(title, description)
        logger.info(f"Pre-selected best resume for '{title}': {resume_path}")

        try:
            # Load the selected resume text
            from ai.resume_tailor import ResumeTailor
            tailor = ResumeTailor(llm_client=self.llm)
            resume_text = tailor._load_resume_text(resume_path)

            prompt = f"""Rate how relevant this job is for a candidate with the following profile:
- Target roles: {settings.target_job_titles}
- Experience level: {settings.experience_level}
- Preferred location: {settings.target_location}
- Preferred industries: {settings.preferred_industries}
- Salary range: {settings.preferred_salary_currency} {settings.preferred_salary_min:,} - {settings.preferred_salary_max:,}

Candidate Resume:
{resume_text[:2000]}

Job Details:
- Title: {title}
- Company: {company_name}
- Description: {description[:2000]}

Return a JSON object with:
- "score": integer 0-100 (ATS score)
- "breakdown": object with scores for title_match (0-30), experience_match (0-15), skills_match (0-15), other (0-40)
- "reasoning": brief explanation 

ONLY return valid JSON, no other text."""

            response = await self.llm.generate(prompt)
            data = json.loads(response)
            current_score = min(100, max(0, data.get("score", 50)))
            
            return {
                "score": current_score,
                "breakdown": data.get("breakdown", {}),
                "reasoning": data.get("reasoning", ""),
                "best_resume": resume_path
            }
        except Exception as e:
            logger.warning(f"AI scoring failed for selected resume {resume_path}: {e}")
            return self.score(title, description, company_name=company_name)

    def _score_title(self, title: str) -> float:
        """Score title match (0-30)."""
        if not title:
            return 0

        title_lower = title.lower()
        target_lower = settings.target_job_title.lower()

        # Exact match
        if target_lower in title_lower:
            return 30

        # Word overlap
        target_words = set(target_lower.split())
        title_words = set(title_lower.split())
        overlap = len(target_words & title_words)
        total = len(target_words)

        if total == 0:
            return 0

        return round((overlap / total) * 25, 1)

    def _score_location(self, location: str) -> float:
        """Score location match (0-15)."""
        if not location:
            return 7.5  # Unknown — give half

        location_lower = location.lower()

        if "dublin" in location_lower:
            return 15
        elif "ireland" in location_lower:
            return 12
        elif "remote" in location_lower:
            return 10
        elif "hybrid" in location_lower:
            return 8

        return 0

    def _score_experience(self, title: str, description: str) -> float:
        """Score experience level match (0-15)."""
        text = f"{title} {description}".lower()
        level = settings.experience_level.lower()
        min_years = settings.min_experience_years

        level_map = {
            "junior": ["junior", "entry level", "graduate", "entry-level", "0-2 years", "1-2 years"],
            "mid": ["mid", "intermediate", "2-5 years", "3-5 years", "2+ years", "3+ years"],
            "senior": ["senior", "lead", "principal", "staff", "5+ years", "7+ years", "8+ years"],
        }

        matching_keywords = level_map.get(level, [])
        opposite_level_keywords = []

        if level == "junior":
            opposite_level_keywords = level_map.get("senior", [])
        elif level == "senior":
            opposite_level_keywords = level_map.get("junior", [])

        # Priority Check: Years of experience mentioned in text
        years_matches = re.findall(r"(\d+)\+?\s*(?:year|yr)s?", text)
        if years_matches:
            max_found_years = max(int(y) for y in years_matches)
            if max_found_years >= min_years:
                return 15
            elif max_found_years < min_years:
                return 0 # Strict penalty for failing year requirement

        # Positive match by keywords
        for kw in matching_keywords:
            if kw in text:
                return 15

        # Negative match (opposite level)
        for kw in opposite_level_keywords:
            if kw in text:
                return 0 # Penalize heavily if "Junior" found for "Senior" role

        return 7.5  # Neutral

    def _score_salary(self, salary_min: float = None, salary_max: float = None) -> float:
        """Score salary match (0-15)."""
        if salary_min is None and salary_max is None:
            return 7.5  # Unknown

        job_min = salary_min or 0
        job_max = salary_max or float("inf")
        pref_min = settings.preferred_salary_min
        pref_max = settings.preferred_salary_max

        # Full overlap
        if job_min >= pref_min and job_max <= pref_max:
            return 15

        # Partial overlap
        overlap_min = max(job_min, pref_min)
        overlap_max = min(job_max, pref_max)

        if overlap_min <= overlap_max:
            range_size = pref_max - pref_min if pref_max > pref_min else 1
            overlap_ratio = (overlap_max - overlap_min) / range_size
            return round(overlap_ratio * 15, 1)

        # No overlap
        return 0

    def _score_skills(self, description: str) -> float:
        """Score skills/keyword match from description (0-15)."""
        if not description:
            return 7.5

        desc_lower = description.lower()

        # Common tech skills (can be customized per user)
        skill_groups = {
            "programming": ["python", "javascript", "typescript", "java", "c#", "go", "rust", "ruby"],
            "frameworks": ["react", "angular", "vue", "django", "flask", "fastapi", "spring", "node.js",
                          "express", "next.js"],
            "data": ["sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch"],
            "cloud": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform"],
            "tools": ["git", "ci/cd", "jenkins", "github actions", "jira", "agile", "scrum"],
        }

        matched_groups = 0
        total_groups = len(skill_groups)

        for group_name, skills in skill_groups.items():
            if any(skill in desc_lower for skill in skills):
                matched_groups += 1

        if total_groups == 0:
            return 7.5

        return round((matched_groups / total_groups) * 15, 1)

    def _score_industry(self, company_name: str, description: str) -> float:
        """Score industry match (0-10)."""
        text = f"{company_name} {description}".lower()
        industries = settings.industries_list

        for industry in industries:
            if industry.lower() in text:
                return 10

        return 5  # Neutral
