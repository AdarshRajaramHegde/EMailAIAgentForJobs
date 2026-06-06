"""
Deduplication Engine — prevents duplicate applications.
"""

import hashlib
from typing import Set

from fuzzywuzzy import fuzz
from loguru import logger

from database.db import get_session, hash_url, is_already_applied
from database.models import Job


class DeduplicationEngine:
    """Prevents duplicate job listings and applications."""

    def __init__(self):
        self._seen_hashes: Set[str] = set()
        self._load_existing()

    def _load_existing(self):
        """Load existing job URL hashes from database."""
        session = get_session()
        try:
            existing = session.query(Job.url_hash).all()
            self._seen_hashes = {h[0] for h in existing}
            logger.info(f"Dedup: loaded {len(self._seen_hashes)} existing job hashes")
        finally:
            session.close()

    def is_duplicate(self, url: str, title: str = "", company: str = "") -> bool:
        """Check if a job is a duplicate."""
        # 1. Exact URL match
        url_h = hash_url(url)
        if url_h in self._seen_hashes:
            return True

        # 2. Check if already applied
        if is_already_applied(get_session(), url):
            return True

        return False

    def is_fuzzy_duplicate(self, title: str, company: str, existing_jobs: list) -> bool:
        """Check for fuzzy duplicates (similar title + same company)."""
        for existing in existing_jobs:
            if not existing.get("company"):
                continue

            # Same company name (fuzzy)
            company_match = fuzz.ratio(
                company.lower(),
                existing.get("company", "").lower()
            ) > 85

            # Similar title (fuzzy)
            title_match = fuzz.ratio(
                title.lower(),
                existing.get("title", "").lower()
            ) > 80

            if company_match and title_match:
                return True

        return False

    def mark_seen(self, url: str):
        """Mark a URL as seen (after saving to database)."""
        url_h = hash_url(url)
        self._seen_hashes.add(url_h)

    def refresh(self):
        """Reload hashes from database."""
        self._load_existing()
