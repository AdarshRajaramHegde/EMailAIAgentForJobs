"""
JobsIreland.ie scraper — Government-run job site.
"""

from typing import List
from urllib.parse import urlencode

from loguru import logger

from scrapers import BaseScraper, RawJob


class JobsIrelandScraper(BaseScraper):
    """Scrape JobsIreland.ie job listings."""

    SOURCE_NAME = "jobsireland"
    BASE_URL = "https://www.jobsireland.ie/en/index.php"

    async def scrape(self, job_title: str, location: str = "Dublin") -> List[RawJob]:
        """Scrape JobsIreland.ie."""
        jobs = []
        
        # JobsIreland search often uses a complex interface, 
        # but we'll try a basic keyword search if available.
        params = {
            "keywords": job_title,
            "location": location,
        }
        url = f"https://www.jobsireland.ie/en/job-search?{urlencode(params)}"

        try:
            response = await self._get(url)
            soup = self._parse_html(response.text)

            # This is a simplified parser; real JobsIreland might need Playwright
            cards = soup.find_all("div", class_="job-card")
            
            for card in cards:
                title_el = card.find("h2") or card.find("h3")
                link_el = card.find("a")
                
                if title_el and link_el:
                    title = title_el.get_text(strip=True)
                    href = link_el.get("href", "")
                    full_url = f"https://www.jobsireland.ie{href}" if href.startswith("/") else href
                    
                    jobs.append(RawJob(
                        title=title,
                        company_name="Various",
                        url=full_url,
                        location=location,
                        source=self.SOURCE_NAME,
                    ))

            logger.info(f"JobsIreland: found {len(jobs)} jobs (basic scrape)")

        except Exception as e:
            logger.error(f"JobsIreland scraper error: {e}")

        return jobs
