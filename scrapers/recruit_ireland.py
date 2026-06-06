"""
Recruit Ireland job scraper.
"""

import re
from typing import List, Optional
from urllib.parse import urlencode

from loguru import logger

from scrapers import BaseScraper, RawJob


class RecruitIrelandScraper(BaseScraper):
    """Scrape Recruit Ireland job listings."""

    SOURCE_NAME = "recruit_ireland"
    BASE_URL = "https://www.recruitireland.com/jobs"

    async def scrape(self, job_title: str, location: str = "Dublin") -> List[RawJob]:
        """Scrape Recruit Ireland job listings."""
        jobs = []

        for page in range(1, 4):
            params = {
                "keywords": job_title,
                "location": location,
                "page": page,
            }
            url = f"{self.BASE_URL}?{urlencode(params)}"

            try:
                response = await self._get(url)
                soup = self._parse_html(response.text)

                cards = soup.find_all("div", class_=re.compile("job-listing|job-card|search-result"))
                if not cards:
                    cards = soup.find_all("article", class_=re.compile("job"))

                if not cards:
                    break

                for card in cards:
                    job = self._parse_card(card)
                    if job:
                        jobs.append(job)

                logger.info(f"Recruit Ireland: scraped page {page}, {len(jobs)} jobs so far")

            except Exception as e:
                logger.error(f"Recruit Ireland scraper error page {page}: {e}")
                break

        logger.info(f"Recruit Ireland: found {len(jobs)} total jobs for '{job_title}'")
        return jobs

    def _parse_card(self, card) -> Optional[RawJob]:
        """Parse a Recruit Ireland job card."""
        try:
            title_el = card.find("a", class_=re.compile("title|job-title"))
            if not title_el:
                title_el = card.find("h2")
                if title_el:
                    title_el = title_el.find("a") or title_el

            company_el = card.find("span", class_=re.compile("company|employer"))
            location_el = card.find("span", class_=re.compile("location"))
            salary_el = card.find("span", class_=re.compile("salary"))

            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "") if title_el.name == "a" else ""
            url = href if href.startswith("http") else f"https://www.recruitireland.com{href}"
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            location = location_el.get_text(strip=True) if location_el else "Dublin"

            salary_min, salary_max = None, None
            if salary_el:
                numbers = re.findall(r"[\d,]+", salary_el.get_text(strip=True).replace(",", ""))
                if len(numbers) >= 2:
                    salary_min, salary_max = float(numbers[0]), float(numbers[1])

            return RawJob(
                title=title,
                company_name=company,
                url=url,
                location=location,
                source=self.SOURCE_NAME,
                salary_min=salary_min,
                salary_max=salary_max,
            )
        except Exception as e:
            logger.warning(f"Recruit Ireland: failed to parse card: {e}")
            return None
