"""
Google Jobs scraper — uses SerpAPI or direct scraping.
"""

import json
import re
from typing import List, Optional
from urllib.parse import urlencode, quote_plus

from loguru import logger

from config import settings
from scrapers import BaseScraper, RawJob


class GoogleJobsScraper(BaseScraper):
    """Scrape Google Jobs results via SerpAPI or direct search."""

    SOURCE_NAME = "google_jobs"
    SERPAPI_URL = "https://serpapi.com/search.json"

    async def scrape(self, job_title: str, location: str = "Dublin, Ireland") -> List[RawJob]:
        """Scrape Google Jobs — uses SerpAPI if key is available, else direct Google."""
        if settings.serpapi_key:
            return await self._scrape_serpapi(job_title, location)
        else:
            return await self._scrape_direct(job_title, location)

    async def _scrape_serpapi(self, job_title: str, location: str) -> List[RawJob]:
        """Scrape via SerpAPI Google Jobs endpoint."""
        jobs = []
        params = {
            "engine": "google_jobs",
            "q": f"{job_title} {location}",
            "hl": "en",
            "api_key": settings.serpapi_key,
        }

        try:
            response = await self._get(self.SERPAPI_URL, params=params)
            data = response.json()

            for result in data.get("jobs_results", []):
                title = result.get("title", "")
                company = result.get("company_name", "Unknown")
                loc = result.get("location", location)
                description = result.get("description", "")
                link = result.get("share_link") or result.get("related_links", [{}])[0].get("link", "")

                # Extract apply options
                apply_options = result.get("apply_options", [])
                best_link = link
                is_easy = False
                for opt in apply_options:
                    if opt.get("link"):
                        best_link = opt["link"]
                        if "linkedin" in opt.get("title", "").lower():
                            is_easy = True
                        break

                jobs.append(RawJob(
                    title=title,
                    company_name=company,
                    url=best_link,
                    description=description,
                    location=loc,
                    source=self.SOURCE_NAME,
                    is_easy_apply=is_easy,
                ))

            logger.info(f"Google Jobs (SerpAPI): found {len(jobs)} jobs")

        except Exception as e:
            logger.error(f"Google Jobs SerpAPI error: {e}")

        return jobs

    async def _scrape_direct(self, job_title: str, location: str) -> List[RawJob]:
        """Scrape Google search results for job listings directly."""
        jobs = []
        query = f"{job_title} jobs in {location}"
        url = f"https://www.google.com/search?q={quote_plus(query)}&ibp=htl;jobs"

        try:
            response = await self._get(url)
            soup = self._parse_html(response.text)

            # Google Jobs renders via JS, so HTML scraping is limited
            # Try to extract any visible job cards
            cards = soup.find_all("div", class_=re.compile("job|g-card"))

            for card in cards:
                title_el = card.find(["h2", "h3", "div"], class_=re.compile("title|BjJfJf"))
                company_el = card.find("div", class_=re.compile("company|vNEEBe"))

                if title_el:
                    jobs.append(RawJob(
                        title=title_el.get_text(strip=True),
                        company_name=company_el.get_text(strip=True) if company_el else "Unknown",
                        url=url,
                        location=location,
                        source=self.SOURCE_NAME,
                    ))

            logger.info(f"Google Jobs (direct): found {len(jobs)} jobs (limited without SerpAPI)")

        except Exception as e:
            logger.error(f"Google Jobs direct scraper error: {e}")

        return jobs
