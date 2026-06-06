"""
PublicJobs.ie scraper — handles public sector and civil service jobs in Ireland.
"""

import re
from typing import List, Optional
from urllib.parse import urlencode

from loguru import logger

from scrapers import BaseScraper, RawJob


class PublicJobsScraper(BaseScraper):
    """Scrape PublicJobs.ie job listings."""

    SOURCE_NAME = "publicjobs"
    BASE_URL = "https://publicjobs.ie/en/index.php"

    async def scrape(self, job_title: str, location: str = "Dublin") -> List[RawJob]:
        """Scrape PublicJobs.ie."""
        jobs = []
        
        # PublicJobs search parameters
        params = {
            "option": "com_jobsearch",
            "view": "jobsearch",
            "Itemid": 263,
            "search_query": job_title,
        }
        url = f"{self.BASE_URL}?{urlencode(params)}"

        try:
            response = await self._get(url)
            soup = self._parse_html(response.text)

            # Looking for job result items
            cards = soup.find_all("div", class_="job-item")
            
            for card in cards:
                title_el = card.find("h3")
                if not title_el:
                    continue
                
                link_el = title_el.find("a")
                if not link_el:
                    continue
                
                title = link_el.get_text(strip=True)
                href = link_el.get("href", "")
                full_url = f"https://publicjobs.ie{href}" if href.startswith("/") else href
                
                company = "Public Sector" # Usually government bodies
                location_el = card.find("span", class_="location")
                loc = location_el.get_text(strip=True) if location_el else location
                
                jobs.append(RawJob(
                    title=title,
                    company_name=company,
                    url=full_url,
                    location=loc,
                    source=self.SOURCE_NAME,
                ))

            logger.info(f"PublicJobs: found {len(jobs)} jobs for '{job_title}'")

        except Exception as e:
            logger.error(f"PublicJobs scraper error: {e}")

        return jobs
