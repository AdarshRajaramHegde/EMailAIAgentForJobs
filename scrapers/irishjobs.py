"""
IrishJobs.ie and Jobs.ie scraper — two of Ireland's largest job boards.
"""

import re
from typing import List, Optional
from urllib.parse import urlencode

from loguru import logger

from scrapers import BaseScraper, RawJob


class IrishJobsScraper(BaseScraper):
    """Scrape IrishJobs.ie and Jobs.ie job listings."""

    SOURCE_NAME = "irishjobs"

    SITES = {
        "irishjobs": "https://www.irishjobs.ie/ShowResults.aspx",
        "jobs_ie": "https://www.jobs.ie/ShowResults.aspx",
        "nijobs": "https://www.nijobs.com/ShowResults.aspx",
    }

    async def scrape(self, job_title: str, location: str = "Dublin") -> List[RawJob]:
        """Scrape both IrishJobs.ie and Jobs.ie."""
        all_jobs = []

        for site_name, base_url in self.SITES.items():
            jobs = await self._scrape_site(site_name, base_url, job_title, location)
            all_jobs.extend(jobs)

        logger.info(f"IrishJobs: found {len(all_jobs)} total jobs across both sites")
        return all_jobs

    async def _scrape_site(self, site_name: str, base_url: str, job_title: str, location: str) -> List[RawJob]:
        """Scrape a single Irish job site."""
        jobs = []

        for page in range(1, 4):
            params = {
                "Keywords": job_title,
                "Location": location,
                "Category": "",
                "Recruiter": "",
                "SortBy": "MostRecent",
                "PerPage": 20,
                "Page": page,
            }
            url = f"{base_url}?{urlencode(params)}"

            try:
                response = await self._get(url)
                soup = self._parse_html(response.text)

                cards = soup.find_all("div", class_=re.compile("job-result|job-item|search-result"))
                if not cards:
                    cards = soup.find_all("li", class_=re.compile("result"))

                if not cards:
                    break

                for card in cards:
                    job = self._parse_card(card, site_name)
                    if job:
                        jobs.append(job)

                logger.info(f"{site_name}: scraped page {page}, {len(jobs)} jobs so far")

            except Exception as e:
                logger.error(f"{site_name} scraper error page {page}: {e}")
                break

        return jobs

    def _parse_card(self, card, site_name: str) -> Optional[RawJob]:
        """Parse a job card from IrishJobs or Jobs.ie."""
        try:
            title_el = card.find("a", class_=re.compile("job-title|JobTitle|result-title"))
            if not title_el:
                title_el = card.find("h2")
                if title_el:
                    title_el = title_el.find("a")

            company_el = card.find("span", class_=re.compile("company|employer"))
            if not company_el:
                company_el = card.find("h3")

            location_el = card.find("span", class_=re.compile("location"))
            salary_el = card.find("span", class_=re.compile("salary"))

            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")

            if site_name == "irishjobs":
                base = "https://www.irishjobs.ie"
            else:
                base = "https://www.jobs.ie"

            url = f"{base}{href}" if href.startswith("/") else href
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            location = location_el.get_text(strip=True) if location_el else "Dublin"

            salary_min, salary_max = None, None
            if salary_el:
                salary_text = salary_el.get_text(strip=True)
                numbers = re.findall(r"[\d,]+", salary_text.replace(",", ""))
                if len(numbers) >= 2:
                    salary_min, salary_max = float(numbers[0]), float(numbers[1])

            return RawJob(
                title=title,
                company_name=company,
                url=url,
                location=location,
                source=site_name,
                salary_min=salary_min,
                salary_max=salary_max,
            )
        except Exception as e:
            logger.warning(f"{site_name}: failed to parse card: {e}")
            return None
