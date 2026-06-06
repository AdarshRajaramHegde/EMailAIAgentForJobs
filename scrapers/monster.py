"""
Monster Ireland job scraper.
"""

import re
from typing import List, Optional
from urllib.parse import urlencode

from loguru import logger

from scrapers import BaseScraper, RawJob


class MonsterScraper(BaseScraper):
    """Scrape Monster Ireland job listings."""

    SOURCE_NAME = "monster"
    BASE_URL = "https://www.monster.ie/jobs/search"

    async def scrape(self, job_title: str, location: str = "Dublin") -> List[RawJob]:
        """Scrape Monster Ireland job listings."""
        jobs = []

        for page in range(1, 4):
            params = {
                "q": job_title,
                "where": location,
                "page": page,
                "so": "m",  # sort by most recent
            }
            url = f"{self.BASE_URL}?{urlencode(params)}"

            try:
                response = await self._get(url)
                soup = self._parse_html(response.text)

                cards = soup.find_all("div", class_=re.compile("job-cardstyle|card-content|job-search-card"))
                if not cards:
                    cards = soup.find_all("section", class_=re.compile("card-content"))

                if not cards:
                    break

                for card in cards:
                    job = self._parse_card(card)
                    if job:
                        jobs.append(job)

                logger.info(f"Monster: scraped page {page}, {len(jobs)} jobs so far")

            except Exception as e:
                logger.error(f"Monster scraper error page {page}: {e}")
                break

        logger.info(f"Monster: found {len(jobs)} total jobs for '{job_title}' in '{location}'")
        return jobs

    def _parse_card(self, card) -> Optional[RawJob]:
        """Parse a Monster job card."""
        try:
            title_el = card.find("h3", class_=re.compile("title"))
            if not title_el:
                title_el = card.find("a", class_=re.compile("job-cardstyle__joblinktext"))

            company_el = card.find("span", class_=re.compile("company"))
            location_el = card.find("span", class_=re.compile("location"))
            link_el = card.find("a", href=True)

            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            location = location_el.get_text(strip=True) if location_el else "Dublin"

            href = link_el.get("href", "") if link_el else ""
            url = href if href.startswith("http") else f"https://www.monster.ie{href}"

            return RawJob(
                title=title,
                company_name=company,
                url=url,
                location=location,
                source=self.SOURCE_NAME,
            )
        except Exception as e:
            logger.warning(f"Monster: failed to parse card: {e}")
            return None
