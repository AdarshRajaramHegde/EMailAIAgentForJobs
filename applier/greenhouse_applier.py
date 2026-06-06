"""
Greenhouse Applier — handles specialized form filling for Greenhouse (boards.greenhouse.io).
"""

import asyncio
from loguru import logger
from applier.browser_manager import BrowserManager
from config import settings

class GreenhouseApplier:
    """Specialized applier for Greenhouse portals."""

    def __init__(self, browser_manager: BrowserManager):
        self.browser = browser_manager

    async def apply(self, page, job_url: str, job_id: int, 
                    resume_path: str = None, cover_letter_text: str = None) -> bool:
        """Fill out a Greenhouse application form."""
        try:
            logger.info(f"Starting Greenhouse application for: {job_url}")
            await page.goto(job_url, wait_until="networkidle")
            await asyncio.sleep(3)

            # 1. Upload Resume (Crucial for Greenhouse auto-fill)
            if resume_path:
                resume_input = page.locator('input[type="file"][accept*="pdf"], button:has-text("Attach")').first
                if await resume_input.is_visible():
                    await resume_input.set_input_files(resume_path)
                    await asyncio.sleep(2)

            # 2. Fill standard fields
            field_map = {
                'input[name="first_name"]': settings.user_name.split()[0],
                'input[name="last_name"]': settings.user_name.split()[-1],
                'input[name="email"]': settings.user_email,
                'input[name="phone"]': settings.user_phone,
                'input[name="org"]': "", # Current company
                'input[name="urls[LinkedIn]"]': settings.linkedin_profile_url,
            }

            for selector, value in field_map.items():
                el = page.locator(selector).first
                if await el.is_visible() and not await el.input_value():
                    await el.fill(value)

            # 3. Cover Letter
            cl_area = page.locator('textarea[name="cover_letter_text"], #cover_letter_text').first
            if await cl_area.is_visible() and cover_letter_text:
                await cl_area.fill(cover_letter_text)

            # 4. Handle custom questions (Greenhouse often has many)
            # This part uses a more generic approach similar to GenericFormFiller
            
            if settings.dry_run:
                logger.info(f"[DRY RUN] Would submit Greenhouse application: {job_url}")
                await self.browser.screenshot(page, "greenhouse_filled_dryrun")
                return True

            # 5. Submit
            submit_btn = page.locator('#submit_app, button:has-text("Submit Application")').first
            if await submit_btn.is_visible():
                await submit_btn.click()
                await asyncio.sleep(5)
                return True

            return False

        except Exception as e:
            logger.error(f"Greenhouse application failed: {e}")
            await self.browser.screenshot(page, "greenhouse_error")
            return False
