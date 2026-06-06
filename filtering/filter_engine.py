"""
Job Filter Engine — filters jobs by title, location, type, salary, and deduplication.
"""

import re
from typing import List, Optional
from loguru import logger

from config import settings
from scrapers import RawJob


class FilterEngine:
    """Filters job listings based on user preferences."""

    def __init__(self):
        self.target_title = settings.target_job_title.lower()
        self.target_location = settings.target_location.lower()
        self.salary_min = settings.preferred_salary_min
        self.salary_max = settings.preferred_salary_max

        # Build title keywords for matching
        self.title_keywords = set(self.target_title.split())

        # Common title variations
        self.title_variations = self._build_title_variations()

    def filter_jobs(self, jobs: List[RawJob]) -> List[RawJob]:
        """Filter a list of jobs based on all criteria."""
        results = []
        for job in jobs:
            if self.passes_all_filters(job):
                results.append(job)

        logger.info(f"Filter: {len(results)}/{len(jobs)} jobs passed all filters")
        return results

    def passes_all_filters(self, job: RawJob) -> bool:
        """Check if a job passes all filters."""
        return (
            self._matches_title(job.title) and
            self._matches_location(job.location) and
            self._matches_salary(job.salary_min, job.salary_max) and
            self._matches_experience(job.description or "")
        )

    def _matches_experience(self, description: str) -> bool:
        """Check if job description matches the minimum experience requirement (3+ years)."""
        if not description:
            return True  # Cannot determine, let it pass to scoring

        desc_lower = description.lower()
        min_years = settings.min_experience_years

        # Look for patterns like "3+ years", "3 years", "at least 3 years"
        # regex: find a number followed by optional plus and "year(s)" or "yr(s)"
        patterns = [
            rf"(\d+)\+?\s*(?:year|yr)s?",
            rf"at least\s*(\d+)\s*(?:year|yr)s?",
            rf"min(?:imum)?\s*(\d+)\s*(?:year|yr)s?",
            rf"(\d+)\s*-\s*\d+\s*(?:year|yr)s?"
        ]

        found_years = []
        for pattern in patterns:
            matches = re.findall(pattern, desc_lower)
            for m in matches:
                try:
                    found_years.append(int(m))
                except ValueError:
                    continue

        if not found_years:
            # Check for "senior" or "lead" in description if target is 3+
            if min_years >= 3 and any(kw in desc_lower for kw in ["senior", "lead", "staff", "principal"]):
                return True
            # Check for "entry level" or "junior" - if found and min_years is high, reject
            if min_years >= 3 and any(kw in desc_lower for kw in ["entry level", "entry-level", "junior", "graduate"]):
                # But only if no higher number was found
                return False
            return True # Neutral

        # If any found year is >= min_years, it passes
        if any(y >= min_years for y in found_years):
            return True

        # If ALL found years are < min_years, it fails
        if all(y < min_years for y in found_years) and found_years:
            return False

        return True

    def _matches_title(self, title: str) -> bool:
        """Check if job title matches the target."""
        if not title:
            return False

        title_lower = title.lower()

        # Direct match
        if self.target_title in title_lower:
            return True

        # Check variations
        for variation in self.title_variations:
            if variation in title_lower:
                return True

        # Keyword overlap — at least 50% of target keywords present
        title_words = set(title_lower.split())
        overlap = self.title_keywords & title_words
        if len(overlap) >= max(1, len(self.title_keywords) * 0.5):
            return True

        return False

    def _matches_location(self, location: str) -> bool:
        """Check if job location matches (Dublin, Ireland)."""
        if not location:
            return True  # Accept if no location specified (will verify later)

        location_lower = location.lower()

        # Accept Dublin, Ireland, Remote (Ireland), Hybrid (Dublin)
        dublin_patterns = ["dublin", "ireland", "remote", "hybrid"]
        return any(p in location_lower for p in dublin_patterns)

    def _matches_salary(self, salary_min: Optional[float], salary_max: Optional[float]) -> bool:
        """Check if salary range overlaps with preferred range."""
        if salary_min is None and salary_max is None:
            return True  # Accept if no salary listed

        # Check overlap
        job_min = salary_min or 0
        job_max = salary_max or float("inf")

        return job_min <= self.salary_max and job_max >= self.salary_min

    def _build_title_variations(self) -> List[str]:
        """Build common variations of the target job title."""
        base = self.target_title
        variations = [base]

        # Common substitutions
        substitutions = {
            "software engineer": ["software developer", "sde", "swe", "backend engineer",
                                 "frontend engineer", "full stack engineer", "fullstack engineer",
                                 "full-stack engineer", "python developer", "java developer",
                                 "web developer"],
            "data analyst": ["data scientist", "analytics engineer", "business analyst",
                            "bi analyst", "data engineer"],
            "qa engineer": ["test engineer", "quality engineer", "sdet", "test automation",
                           "qa analyst", "quality assurance", "software tester",
                           "automation engineer", "test lead", "qa lead",
                           "software quality engineer", "sqa engineer",
                           "quality assurance engineer", "test automation engineer",
                           "automation test engineer", "qa automation",
                           "software test engineer", "performance test engineer",
                           "selenium", "playwright", "qa engineer ii", "qa engineer 2",
                           "manual qa engineer", "functional qa engineer", "qa analyst ii"],
            "software qa engineer": ["qa engineer", "test engineer", "quality engineer",
                                    "sdet", "test automation engineer", "qa analyst",
                                    "quality assurance engineer", "software tester",
                                    "automation engineer", "sqa engineer",
                                    "software test engineer", "qa lead",
                                    "qa automation engineer", "test lead", "senior qa engineer",
                                    "senior sdet", "senior automation engineer", "staff qa engineer"],
            "senior qa engineer": ["senior sdet", "senior test automation engineer", 
                                  "senior software test engineer", "staff qa engineer",
                                  "qa tech lead", "test lead", "senior automation engineer"],
            "devops engineer": ["sre", "site reliability engineer", "platform engineer",
                              "cloud engineer", "infrastructure engineer"],
            "product manager": ["product owner", "pm", "program manager"],
            "ux designer": ["ui designer", "product designer", "interaction designer",
                           "ui/ux designer"],
        }

        for key, subs in substitutions.items():
            if key in base:
                variations.extend(subs)

        # Add with/without "senior", "junior", "lead", "staff"
        prefixes = ["senior", "junior", "lead", "staff", "principal", "mid", "sr", "jr"]
        base_without_prefix = base
        for p in prefixes:
            if base.startswith(p + " "):
                base_without_prefix = base[len(p) + 1:]
                break

        if base_without_prefix != base:
            variations.append(base_without_prefix)

        return variations
