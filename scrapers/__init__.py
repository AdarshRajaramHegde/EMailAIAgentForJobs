"""
Base scraper interface and shared utilities for all job board scrapers.
"""

import asyncio
import random
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings


@dataclass
class RawJob:
    """Standardized job data returned by all scrapers."""
    title: str
    company_name: str
    url: str
    source: str
    description: str = ""
    location: str = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "EUR"
    job_type: str = "unknown"
    is_easy_apply: bool = False
    requires_cover_letter: bool = False
    application_email: Optional[str] = None
    external_id: Optional[str] = None
    posted_at: Optional[datetime] = None
    extra: dict = field(default_factory=dict)


class BaseScraper(ABC):
    """Abstract base class for all job scrapers."""

    SOURCE_NAME: str = "unknown"

    def __init__(self):
        self.ua = UserAgent()
        self.client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=self._default_headers(),
            proxy=settings.proxy_url if settings.use_proxy else None,
        )

    def _default_headers(self) -> dict:
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    async def _delay(self):
        """Random delay between requests to avoid rate limiting."""
        delay = random.uniform(settings.request_delay_min, settings.request_delay_max)
        await asyncio.sleep(delay)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, url: str, **kwargs) -> httpx.Response:
        """Make a GET request with retry logic."""
        await self._delay()
        self.client.headers["User-Agent"] = self.ua.random
        response = await self.client.get(url, **kwargs)
        response.raise_for_status()
        return response

    def _parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content."""
        return BeautifulSoup(html, "lxml")

    @abstractmethod
    async def scrape(self, job_title: str, location: str) -> List[RawJob]:
        """
        Scrape jobs matching the given title and location.
        Returns a list of RawJob objects.
        """
        pass

    async def close(self):
        """Clean up resources."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
