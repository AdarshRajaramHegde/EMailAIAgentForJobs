"""
LinkedIn Company Monitor — monitors LinkedIn company pages for new job postings.
"""

import re
from typing import List, Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from loguru import logger

from config import settings
from scrapers import RawJob


class LinkedInCompanyMonitor:
    """Monitor LinkedIn company pages for new job openings."""

    def __init__(self):
        self.ua = UserAgent()
        self.client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": self.ua.random},
        )

    async def monitor_company(self, company_linkedin_url: str, company_name: str) -> List[RawJob]:
        """Check a company's LinkedIn page for job openings."""
        jobs = []

        # LinkedIn company jobs URL pattern
        jobs_url = company_linkedin_url.rstrip("/") + "/jobs/"

        try:
            self.client.headers["User-Agent"] = self.ua.random
            response = await self.client.get(jobs_url)
            soup = BeautifulSoup(response.text, "lxml")

            cards = soup.find_all("div", class_=re.compile("base-card|job-result-card"))

            for card in cards:
                title_el = card.find("h3", class_=re.compile("title"))
                if not title_el:
                    title_el = card.find(["h3", "h4", "a"])

                location_el = card.find("span", class_=re.compile("location"))
                link_el = card.find("a", href=True)

                if title_el:
                    title = title_el.get_text(strip=True)
                    href = link_el.get("href", "") if link_el else ""
                    url = href.split("?")[0] if href else jobs_url
                    location = location_el.get_text(strip=True) if location_el else ""

                    jobs.append(RawJob(
                        title=title,
                        company_name=company_name,
                        url=url if url.startswith("http") else f"https://www.linkedin.com{url}",
                        location=location,
                        source="linkedin_company",
                    ))

            logger.info(f"LinkedIn Monitor: {company_name} — {len(jobs)} jobs found")

        except Exception as e:
            logger.warning(f"LinkedIn Monitor failed for {company_name}: {e}")

        return jobs

    async def monitor_companies_batch(self, companies: List[dict]) -> List[RawJob]:
        """Monitor multiple companies' LinkedIn pages."""
        all_jobs = []

        for company in companies:
            linkedin_url = company.get("linkedin_url")
            name = company.get("name", "Unknown")

            if linkedin_url:
                jobs = await self.monitor_company(linkedin_url, name)
                all_jobs.extend(jobs)

                import asyncio
                await asyncio.sleep(settings.request_delay_min)

        logger.info(f"LinkedIn Company Monitor: {len(all_jobs)} total jobs across {len(companies)} companies")
        return all_jobs

    async def close(self):
        await self.client.aclose()
