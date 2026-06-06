"""
LinkedIn job scraper — uses public job search URLs.
"""

import re
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote_plus, urlencode

from loguru import logger

from scrapers import BaseScraper, RawJob


class LinkedInScraper(BaseScraper):
    """Scrape LinkedIn's public job listings."""

    SOURCE_NAME = "linkedin"
    BASE_URL = "https://www.linkedin.com/jobs/search"

    async def scrape(self, job_title: str, location: str = "Dublin, Ireland") -> List[RawJob]:
        """Scrape LinkedIn public job listings."""
        jobs = []
        start = 0
        max_pages = 5  # 25 results per page

        while start < max_pages * 25:
            params = {
                "keywords": job_title,
                "location": location,
                "f_TPR": "r86400",  # past 24 hours
                "position": 1,
                "pageNum": 0,
                "start": start,
            }
            url = f"{self.BASE_URL}?{urlencode(params)}"

            try:
                response = await self._get(url)
                soup = self._parse_html(response.text)
                cards = soup.find_all("div", class_="base-card")

                if not cards:
                    break

                for card in cards:
                    job = self._parse_card(card)
                    if job:
                        jobs.append(job)

                start += 25
                logger.info(f"LinkedIn: scraped page {start // 25}, {len(jobs)} jobs so far")

            except Exception as e:
                logger.error(f"LinkedIn scraper error at start={start}: {e}")
                break

        logger.info(f"LinkedIn: found {len(jobs)} total jobs for '{job_title}' in '{location}'")
        return jobs

    def _parse_card(self, card) -> Optional[RawJob]:
        """Parse a single LinkedIn job card."""
        try:
            title_el = card.find("h3", class_="base-search-card__title")
            company_el = card.find("h4", class_="base-search-card__subtitle")
            location_el = card.find("span", class_="job-search-card__location")
            link_el = card.find("a", class_="base-card__full-link")
            time_el = card.find("time")

            if not title_el or not link_el:
                return None

            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            location = location_el.get_text(strip=True) if location_el else ""
            url = link_el.get("href", "").split("?")[0]  # clean tracking params
            posted_at = None

            if time_el and time_el.get("datetime"):
                try:
                    posted_at = datetime.fromisoformat(time_el["datetime"])
                except (ValueError, TypeError):
                    pass

            # Detect Easy Apply (present on some listings)
            easy_apply = bool(card.find("span", string=re.compile("Easy Apply", re.I)))

            return RawJob(
                title=title,
                company_name=company,
                url=url,
                location=location,
                source=self.SOURCE_NAME,
                is_easy_apply=easy_apply,
                posted_at=posted_at,
            )
        except Exception as e:
            logger.warning(f"LinkedIn: failed to parse card: {e}")
            return None
