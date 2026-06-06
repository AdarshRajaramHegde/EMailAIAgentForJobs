"""
Career Page Finder — discovers company career pages through multiple sources:
- Google search queries
- Crunchbase / AngelList / IDA Ireland
- LinkedIn company pages
"""

import re
import asyncio
from typing import List, Dict
from urllib.parse import quote_plus, urlencode

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from fake_useragent import UserAgent

from config import settings
from database.db import get_session, upsert_company


class CareerPageFinder:
    """Discovers company career pages using multiple strategies."""

    def __init__(self):
        self.ua = UserAgent()
        self.client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": self.ua.random},
            proxy=settings.proxy_url if settings.use_proxy else None,
        )

    async def discover_all(self, job_title: str = None, location: str = None):
        """Run all discovery strategies and save results to database."""
        job_title = job_title or settings.target_job_title
        location = location or settings.target_location

        logger.info(f"Starting career page discovery for '{job_title}' in '{location}'")

        # Run all strategies concurrently
        results = await asyncio.gather(
            self._google_career_search(job_title, location),
            self._discover_ida_ireland(),
            self._discover_tech_companies_dublin(),
            return_exceptions=True,
        )

        all_companies = []
        for r in results:
            if isinstance(r, list):
                all_companies.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"Discovery strategy failed: {r}")

        # Save to database
        session = get_session()
        saved = 0
        try:
            for company in all_companies:
                upsert_company(
                    session,
                    name=company.get("name", "Unknown"),
                    career_page_url=company.get("career_url"),
                    website=company.get("website"),
                    linkedin_url=company.get("linkedin_url"),
                    industry=company.get("industry"),
                    source=company.get("source", "discovery"),
                    location=location,
                )
                saved += 1
        finally:
            session.close()

        logger.info(f"Career page discovery complete: {saved} companies saved/updated")
        return all_companies

    async def _google_career_search(self, job_title: str, location: str) -> List[Dict]:
        """Use Google to discover company career pages."""
        companies = []
        queries = [
            f'site:careers.*.com "{job_title}" "{location}"',
            f'site:*.com/careers "{job_title}" Dublin Ireland',
            f'"{job_title}" careers Dublin Ireland apply now',
            f'"{job_title}" "we are hiring" Dublin Ireland',
            f'site:workday.com "{job_title}" Dublin',
            f'site:greenhouse.io "{job_title}" Dublin',
            f'site:lever.co "{job_title}" Dublin',
            f'site:jobs.lever.co "{job_title}" Dublin Ireland',
            f'"{job_title}" jobs in Ireland apply',
            f'"{job_title}" vacancies Ireland',
            f'"{job_title}" career portal Ireland',
            f'site:myworkdayjobs.com "{job_title}" Ireland',
            f'intitle:"{job_title}" "Ireland" apply',
        ]

        for query in queries:
            try:
                await asyncio.sleep(2)  # Respect Google rate limits
                url = f"https://www.google.com/search?q={quote_plus(query)}&num=20"
                self.client.headers["User-Agent"] = self.ua.random

                response = await self.client.get(url)
                soup = BeautifulSoup(response.text, "lxml")

                for result in soup.find_all("div", class_="g"):
                    link_el = result.find("a", href=True)
                    title_el = result.find("h3")

                    if link_el and title_el:
                        href = link_el["href"]
                        title = title_el.get_text(strip=True)

                        # Extract company name from result
                        company_name = self._extract_company_from_url(href, title)

                        if company_name:
                            companies.append({
                                "name": company_name,
                                "career_url": href,
                                "website": self._extract_base_url(href),
                                "source": "google_search",
                                "industry": "Unknown",
                            })

                logger.info(f"Google search found {len(companies)} companies so far")

            except Exception as e:
                logger.warning(f"Google career search failed for query: {e}")

        return companies

    async def _discover_ida_ireland(self) -> List[Dict]:
        """Discover companies from IDA Ireland's company listing."""
        companies = []
        url = "https://www.idaireland.com/explore-ida/the-facts/companies-in-ireland"

        try:
            response = await self.client.get(url)
            soup = BeautifulSoup(response.text, "lxml")

            # Look for company listings
            for el in soup.find_all(["div", "li", "a"], class_=re.compile("company|partner|client")):
                name = el.get_text(strip=True)
                href = el.get("href", "")

                if len(name) > 2 and len(name) < 100:
                    companies.append({
                        "name": name,
                        "career_url": None,
                        "website": href if href.startswith("http") else None,
                        "source": "ida_ireland",
                        "industry": "Tech",
                    })

            logger.info(f"IDA Ireland: found {len(companies)} companies")

        except Exception as e:
            logger.warning(f"IDA Ireland discovery failed: {e}")

        return companies

    async def _discover_tech_companies_dublin(self) -> List[Dict]:
        """Discover tech companies in Dublin from known sources."""
        # Hardcoded list of known major tech employers in Dublin
        # This list is supplemented by the Google search results
        known_companies = [
            {"name": "Google", "career_url": "https://careers.google.com/jobs/results/?location=Dublin,%20Ireland"},
            {"name": "Meta", "career_url": "https://www.metacareers.com/jobs/?offices[0]=Dublin%2C%20Ireland"},
            {"name": "Microsoft", "career_url": "https://careers.microsoft.com/professionals/us/en/l-dublin"},
            {"name": "Amazon", "career_url": "https://www.amazon.jobs/en/locations/dublin-ireland"},
            {"name": "Apple", "career_url": "https://jobs.apple.com/en-ie/search?location=dublin-DUB"},
            {"name": "Salesforce", "career_url": "https://careers.salesforce.com/en/jobs/?search=&location=Dublin%2C+Ireland"},
            {"name": "Stripe", "career_url": "https://stripe.com/jobs/search?office_locations=Europe--Dublin"},
            {"name": "Intercom", "career_url": "https://www.intercom.com/careers#open-positions"},
            {"name": "HubSpot", "career_url": "https://www.hubspot.com/careers/jobs?hubs_signup-url=www.hubspot.com%2Fcareers&page=1#tabpanel-tab3"},
            {"name": "Workday", "career_url": "https://workday.wd5.myworkdayjobs.com/en-US/Workday?locationCountry=29247e57dbaf101bfc7be5fba2837800"},
            {"name": "ServiceNow", "career_url": "https://careers.servicenow.com/jobs?location=Dublin"},
            {"name": "Accenture", "career_url": "https://www.accenture.com/ie-en/careers/jobsearch?jk=&sb=1&vw=0&is_rj=0&pg=1&ct=Dublin"},
            {"name": "Deloitte", "career_url": "https://apply.deloitte.com/careers/SearchJobs/?524=914&524_format=1482&listFilterMode=1"},
            {"name": "KPMG", "career_url": "https://www.kpmgcareers.ie/"},
            {"name": "PwC", "career_url": "https://www.pwc.ie/careers.html"},
            {"name": "Indeed", "career_url": "https://indeed.wd1.myworkdayjobs.com/en-US/IndeedJobs?locationCountry=29247e57dbaf101bfc7be5fba2837800"},
            {"name": "Mastercard", "career_url": "https://careers.mastercard.com/us/en/search-results?keywords=&location=Dublin%2C%20Leinster%2C%20Ireland"},
            {"name": "PayPal", "career_url": "https://careers.pypl.com/home/jobs?keyword=&location=Dublin%2C%20Ireland"},
            {"name": "Fidelity Investments", "career_url": "https://fil.wd3.myworkdayjobs.com/fidelityinternational?locationCountry=29247e57dbaf101bfc7be5fba2837800"},
            {"name": "Squarespace", "career_url": "https://www.squarespace.com/careers/all-openings?location=dublin"},
            {"name": "Zendesk", "career_url": "https://jobs.zendesk.com/us/en/search-results?keywords=&location=Dublin"},
            {"name": "Personio", "career_url": "https://www.personio.com/about-personio/careers/#open-positions"},
            {"name": "Toast", "career_url": "https://careers.toasttab.com/jobs?location=Dublin"},
            {"name": "TikTok", "career_url": "https://careers.tiktok.com/position?keywords=&category=&location=CT_243"},
            {"name": "ByteDance", "career_url": "https://jobs.bytedance.com/en/position?keywords=&category=&location=CT_243"},
        ]

        results = []
        for c in known_companies:
            results.append({
                "name": c["name"],
                "career_url": c["career_url"],
                "website": None,
                "source": "known_employers",
                "industry": "Tech",
            })

        logger.info(f"Known Dublin tech companies: {len(results)} added")
        return results

    @staticmethod
    def _extract_company_from_url(url: str, title: str) -> str:
        """Extract company name from a URL or search result title."""
        # Try common patterns
        patterns = [
            r"careers\.([a-zA-Z0-9]+)\.",
            r"jobs\.([a-zA-Z0-9]+)\.",
            r"([a-zA-Z0-9]+)\.com/careers",
            r"([a-zA-Z0-9]+)\.ie/careers",
        ]
        for p in patterns:
            m = re.search(p, url, re.I)
            if m:
                return m.group(1).capitalize()

        # Fall back to title
        if " - " in title:
            return title.split(" - ")[0].strip()
        if " at " in title:
            parts = title.split(" at ")
            if len(parts) > 1:
                return parts[1].strip()

        return ""

    @staticmethod
    def _extract_base_url(url: str) -> str:
        """Extract base domain from a URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            return url

    async def close(self):
        await self.client.aclose()
