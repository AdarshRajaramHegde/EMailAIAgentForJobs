"""
LinkedIn Easy Apply Automation — automates the LinkedIn Easy Apply process.
"""

import asyncio
import random
from datetime import datetime
from typing import Optional

from loguru import logger

from config import settings
from applier.browser_manager import BrowserManager, human_like_type, human_like_click
from database.db import get_session, create_application, log_application_event
from database.models import ApplicationStatus


class LinkedInApplier:
    """Automates LinkedIn Easy Apply."""

    def __init__(self, browser_manager: BrowserManager = None):
        self.browser = browser_manager or BrowserManager()
        self._logged_in = False

    async def login(self, page):
        """Check if logged into LinkedIn. Automated login is disabled to avoid flags."""
        try:
            await page.goto("https://www.linkedin.com/", wait_until="networkidle")
            await asyncio.sleep(2)

            # Check if signed in by looking for feed or profile icon
            is_logged_in = "feed" in page.url or await page.locator(".global-nav__me").first.is_visible()
            
            if is_logged_in:
                self._logged_in = True
                logger.info("LinkedIn: Successfully authenticated via session")
                # Refresh/update the saved session state
                await self.browser.save_state("linkedin")
                return True

            # If not logged in, we DO NOT attempt automated login with credentials
            # as it's the primary cause of account flags.
            logger.warning("LinkedIn: Session expired or missing.")
            logger.warning("⚠️ To avoid account flags, automated login is disabled.")
            logger.warning("👉 Please run: python main.py --login linkedin")
            
            # Optional insecure fallback (not recommended)
            if getattr(settings, "allow_insecure_login", False) and settings.linkedin_email:
                logger.info("Insecure login fallback enabled. Attempting automated login...")
                await page.goto("https://www.linkedin.com/login", wait_until="networkidle")
                await asyncio.sleep(2)
                await human_like_type(page, "#username", settings.linkedin_email)
                await human_like_type(page, "#password", settings.linkedin_password)
                await human_like_click(page, 'button[type="submit"]')
                await page.wait_for_load_state("networkidle")
                
                if "feed" in page.url:
                    self._logged_in = True
                    await self.browser.save_state("linkedin")
                    return True

            return False

        except Exception as e:
            logger.error(f"LinkedIn session check failed: {e}")
            return False

    async def apply(self, page, job_url: str, job_id: int,
                    resume_path: str = None, cover_letter_text: str = None) -> bool:
        """Apply to a LinkedIn job using Easy Apply."""
        session = get_session()

        try:
            # Navigate to job
            await page.goto(job_url, wait_until="networkidle")
            await asyncio.sleep(2)

            # Find Easy Apply button
            easy_apply_btn = page.locator('button:has-text("Easy Apply")').first
            if not await easy_apply_btn.is_visible():
                logger.warning(f"No Easy Apply button found for {job_url}")
                return False

            if settings.dry_run:
                logger.info(f"[DRY RUN] Would click Easy Apply for: {job_url}")
                return True

            # Click Easy Apply
            await easy_apply_btn.click()
            await asyncio.sleep(2)

            # Create application record
            app = create_application(session, job_id=job_id, method="easy_apply")
            log_application_event(session, app.id, "easy_apply_started", f"URL: {job_url}")

            # Handle multi-step form
            step = 0
            max_steps = 10

            while step < max_steps:
                step += 1
                await asyncio.sleep(1)

                # Check for completion
                if await self._check_submitted(page):
                    app.status = ApplicationStatus.APPLIED.value
                    app.applied_at = datetime.utcnow()
                    session.commit()
                    log_application_event(session, app.id, "submitted", "Application submitted successfully")
                    logger.info(f"✅ LinkedIn Easy Apply submitted: {job_url}")
                    return True

                # Fill current step
                await self._fill_form_step(page, resume_path, cover_letter_text)

                # Try to submit or go to next step
                submit_btn = page.locator('button:has-text("Submit application")').first
                next_btn = page.locator('button:has-text("Next")').first
                review_btn = page.locator('button:has-text("Review")').first

                if await submit_btn.is_visible():
                    await submit_btn.click()
                    await asyncio.sleep(2)
                elif await review_btn.is_visible():
                    await review_btn.click()
                    await asyncio.sleep(2)
                elif await next_btn.is_visible():
                    await next_btn.click()
                    await asyncio.sleep(2)
                else:
                    # No button found — might be stuck
                    logger.warning(f"LinkedIn: no action button found at step {step}")
                    await self.browser.screenshot(page, f"linkedin_stuck_step{step}")
                    break

            logger.warning(f"LinkedIn Easy Apply: reached max steps for {job_url}")
            return False

        except Exception as e:
            logger.error(f"LinkedIn Easy Apply failed for {job_url}: {e}")
            await self.browser.screenshot(page, "linkedin_error")
            return False
        finally:
            session.close()

    async def _fill_form_step(self, page, resume_path: str = None, cover_letter: str = None):
        """Fill out the current step of the Easy Apply form."""
        try:
            # Upload resume if file upload present
            file_input = page.locator('input[type="file"]').first
            if await file_input.is_visible() and resume_path:
                await file_input.set_input_files(resume_path)
                await asyncio.sleep(1)

            # Fill text inputs
            text_inputs = page.locator('input[type="text"]:visible')
            count = await text_inputs.count()
            for i in range(count):
                inp = text_inputs.nth(i)
                label = await inp.get_attribute("aria-label") or ""
                value = await inp.input_value()

                if not value:  # Only fill empty fields
                    fill_value = self._map_field(label)
                    if fill_value:
                        await inp.fill(fill_value)

            # Fill textareas (cover letter, additional info)
            textareas = page.locator("textarea:visible")
            ta_count = await textareas.count()
            for i in range(ta_count):
                ta = textareas.nth(i)
                label = await ta.get_attribute("aria-label") or ""
                value = await ta.input_value()

                if not value and cover_letter:
                    await ta.fill(cover_letter[:500])

            # Handle dropdowns / selects
            selects = page.locator("select:visible")
            sel_count = await selects.count()
            for i in range(sel_count):
                sel = selects.nth(i)
                # Select first non-empty option
                options = sel.locator("option")
                opt_count = await options.count()
                if opt_count > 1:
                    await sel.select_option(index=1)

            # Handle radio buttons (select first option)
            radios = page.locator('input[type="radio"]:visible')
            if await radios.count() > 0:
                await radios.first.click()

        except Exception as e:
            logger.warning(f"Error filling form step: {e}")

    def _map_field(self, label: str) -> Optional[str]:
        """Map field labels to user data."""
        label_lower = label.lower()

        field_map = {
            "phone": settings.user_phone,
            "mobile": settings.user_phone,
            "email": settings.user_email,
            "name": settings.user_name,
            "first name": settings.user_name.split()[0] if settings.user_name else "",
            "last name": settings.user_name.split()[-1] if settings.user_name else "",
            "city": "Dublin",
            "location": settings.target_location,
            "linkedin": settings.linkedin_profile_url,
            "website": settings.linkedin_profile_url,
            "salary": str(settings.preferred_salary_min),
        }

        for key, value in field_map.items():
            if key in label_lower:
                return value

        return None

    async def _check_submitted(self, page) -> bool:
        """Check if application was submitted."""
        success_indicators = [
            'text="Application submitted"',
            'text="Your application was sent"',
            'text="Done"',
            'h2:has-text("Application submitted")',
        ]

        for indicator in success_indicators:
            try:
                element = page.locator(indicator).first
                if await element.is_visible():
                    return True
            except Exception:
                pass

        return False
