"""
Career Page Crawler — periodically checks company career pages for new job openings.
"""

import re
import asyncio
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from loguru import logger

from config import settings
from database.db import get_session, get_companies_to_check, upsert_job
from database.models import Company
from scrapers import RawJob


class CareerPageCrawler:
    """Crawls company career pages and extracts job listings."""

    def __init__(self):
        self.ua = UserAgent()
        self.client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": self.ua.random},
            proxy=settings.proxy_url if settings.use_proxy else None,
        )
        self.job_title = settings.target_job_title
        self.location = settings.target_location

    async def crawl_all_due(self):
        """Crawl all company career pages that are due for checking."""
        session = get_session()
        try:
            companies = get_companies_to_check(session, settings.career_page_check_hours)
            logger.info(f"Career page crawler: {len(companies)} companies due for checking")

            total_new = 0
            for company in companies:
                if company.career_page_url:
                    new_jobs = await self.crawl_career_page(company)
                    total_new += new_jobs

                    # Update last_checked timestamp
                    company.last_checked = datetime.utcnow()
                    session.commit()

                    await asyncio.sleep(settings.request_delay_min)

            logger.info(f"Career page crawler complete: {total_new} new jobs found")
            return total_new
        finally:
            session.close()

    async def crawl_career_page(self, company: Company) -> int:
        """Crawl a single company's career page for matching jobs."""
        logger.info(f"Crawling career page for: {company.name} — {company.career_page_url}")
        new_jobs = 0

        try:
            self.client.headers["User-Agent"] = self.ua.random
            response = await self.client.get(company.career_page_url)
            soup = BeautifulSoup(response.text, "lxml")

            # Try multiple extraction strategies
            jobs = []
            jobs.extend(self._extract_structured_jobs(soup, company))
            jobs.extend(self._extract_link_based_jobs(soup, company))
            jobs.extend(self._extract_api_jobs(soup, company))

            # Filter for relevant jobs
            relevant = [j for j in jobs if self._is_relevant(j.title)]

            # Save to database
            session = get_session()
            try:
                for job in relevant:
                    result = upsert_job(
                        session,
                        url=job.url,
                        title=job.title,
                        source="career_page",
                        company_name=company.name,
                        company_id=company.id,
                        location=job.location,
                        description=job.description,
                    )
                    if result:
                        new_jobs += 1
            finally:
                session.close()

            logger.info(f"{company.name}: found {len(relevant)} relevant jobs, {new_jobs} new")

        except Exception as e:
            logger.error(f"Failed to crawl {company.name}: {e}")

        return new_jobs

    def _extract_structured_jobs(self, soup: BeautifulSoup, company: Company) -> List[RawJob]:
        """Extract jobs from structured job listing elements."""
        jobs = []

        # Common career page patterns
        selectors = [
            # Greenhouse
            ("div", {"class": re.compile("opening")}),
            # Lever
            ("div", {"class": re.compile("posting")}),
            # Workday
            ("li", {"class": re.compile("job")}),
            # Generic patterns
            ("div", {"class": re.compile("job-listing|job-card|vacancy|position")}),
            ("li", {"class": re.compile("job|position|opening|vacancy")}),
            ("article", {"class": re.compile("job|position")}),
            ("tr", {"class": re.compile("job|position")}),
        ]

        for tag, attrs in selectors:
            cards = soup.find_all(tag, attrs)
            for card in cards:
                title_el = card.find(["a", "h2", "h3", "h4", "span"], class_=re.compile("title|name|position"))
                if not title_el:
                    title_el = card.find(["a", "h2", "h3", "h4"])

                location_el = card.find(["span", "div", "p"], class_=re.compile("location|place|city"))

                if title_el:
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "") if title_el.name == "a" else ""
                    if not href:
                        a = card.find("a", href=True)
                        href = a.get("href", "") if a else ""

                    url = urljoin(company.career_page_url, href) if href else company.career_page_url
                    location = location_el.get_text(strip=True) if location_el else ""

                    jobs.append(RawJob(
                        title=title,
                        company_name=company.name,
                        url=url,
                        location=location,
                        source="career_page",
                    ))

        return jobs

    def _extract_link_based_jobs(self, soup: BeautifulSoup, company: Company) -> List[RawJob]:
        """Extract jobs by finding links that look like job postings."""
        jobs = []
        seen_urls = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = a.get_text(strip=True)

            # Check if the link looks like a job posting
            is_job_link = any(kw in href.lower() for kw in [
                "/jobs/", "/position/", "/opening/", "/vacancy/",
                "/career/", "/apply/", "jobid=", "requisition",
            ])

            if is_job_link and text and len(text) > 5 and len(text) < 200:
                url = urljoin(company.career_page_url, href)
                if url not in seen_urls:
                    seen_urls.add(url)
                    jobs.append(RawJob(
                        title=text,
                        company_name=company.name,
                        url=url,
                        source="career_page",
                    ))

        return jobs

    def _extract_api_jobs(self, soup: BeautifulSoup, company: Company) -> List[RawJob]:
        """Look for embedded JSON/API data with job listings."""
        jobs = []

        # Some career pages embed job data in script tags (JSON-LD, etc.)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    jobs.append(RawJob(
                        title=data.get("title", ""),
                        company_name=company.name,
                        url=data.get("url", company.career_page_url),
                        description=data.get("description", ""),
                        location=str(data.get("jobLocation", {}).get("address", {}).get("addressLocality", "")),
                        source="career_page",
                    ))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") == "JobPosting":
                            jobs.append(RawJob(
                                title=item.get("title", ""),
                                company_name=company.name,
                                url=item.get("url", company.career_page_url),
                                description=item.get("description", ""),
                                source="career_page",
                            ))
            except Exception:
                pass

        return jobs

    def _is_relevant(self, title: str) -> bool:
        """Check if a job title is relevant to the target job title."""
        if not title:
            return False

        target_words = set(self.job_title.lower().split())
        title_words = set(title.lower().split())

        # At least one keyword overlap
        overlap = target_words & title_words
        if overlap:
            return True

        # Also match common variations
        title_lower = title.lower()
        target_lower = self.job_title.lower()

        # Fuzzy matching for related titles
        related_patterns = [
            target_lower,
            target_lower.replace(" ", ""),
        ]

        for pattern in related_patterns:
            if pattern in title_lower:
                return True

        return False

    async def close(self):
        await self.client.aclose()
