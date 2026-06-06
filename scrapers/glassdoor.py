"""
Glassdoor job scraper.
"""

import re
from typing import List, Optional
from urllib.parse import urlencode

from loguru import logger

from scrapers import BaseScraper, RawJob


class GlassdoorScraper(BaseScraper):
    """Scrape Glassdoor Ireland job listings."""

    SOURCE_NAME = "glassdoor"
    BASE_URL = "https://www.glassdoor.ie/Job/dublin-jobs-SRCH_IL.0,6_IC2382886"

    async def scrape(self, job_title: str, location: str = "Dublin") -> List[RawJob]:
        """Scrape Glassdoor job listings."""
        jobs = []
        keyword_slug = job_title.lower().replace(" ", "-")

        for page in range(1, 4):  # 3 pages max
            url = f"{self.BASE_URL}_KO7,{7 + len(job_title)}_{keyword_slug}_IP{page}.htm"
            # Fallback to search params
            if page == 1:
                url = f"https://www.glassdoor.ie/Job/dublin-{keyword_slug}-jobs-SRCH_IL.0,6_IC2382886_KO7,{7 + len(keyword_slug)}.htm"

            try:
                response = await self._get(url)
                soup = self._parse_html(response.text)

                cards = soup.find_all("li", class_=re.compile("JobsList_jobListItem"))
                if not cards:
                    cards = soup.find_all("li", {"data-test": "jobListing"})

                if not cards:
                    break

                for card in cards:
                    job = self._parse_card(card)
                    if job:
                        jobs.append(job)

                logger.info(f"Glassdoor: scraped page {page}, {len(jobs)} jobs so far")

            except Exception as e:
                logger.error(f"Glassdoor scraper error page {page}: {e}")
                break

        logger.info(f"Glassdoor: found {len(jobs)} total jobs for '{job_title}'")
        return jobs

    def _parse_card(self, card) -> Optional[RawJob]:
        """Parse a single Glassdoor job card."""
        try:
            title_el = card.find("a", {"data-test": "job-title"})
            if not title_el:
                title_el = card.find("a", class_=re.compile("jobTitle"))

            company_el = card.find("span", class_=re.compile("EmployerProfile"))
            if not company_el:
                company_el = card.find("div", {"data-test": "emp-name"})

            location_el = card.find("span", {"data-test": "emp-location"})

            salary_el = card.find("span", {"data-test": "detailSalary"})

            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            url = f"https://www.glassdoor.ie{href}" if href.startswith("/") else href
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            location = location_el.get_text(strip=True) if location_el else "Dublin"

            # Parse salary
            salary_min, salary_max = None, None
            if salary_el:
                salary_text = salary_el.get_text(strip=True)
                numbers = re.findall(r"[\d,]+", salary_text.replace(",", ""))
                if len(numbers) >= 2:
                    salary_min, salary_max = float(numbers[0]), float(numbers[1])

            easy_apply = bool(card.find(string=re.compile("Easy Apply", re.I)))

            return RawJob(
                title=title,
                company_name=company,
                url=url,
                location=location,
                source=self.SOURCE_NAME,
                salary_min=salary_min,
                salary_max=salary_max,
                is_easy_apply=easy_apply,
            )
        except Exception as e:
            logger.warning(f"Glassdoor: failed to parse card: {e}")
            return None
