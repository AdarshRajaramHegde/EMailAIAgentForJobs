"""
Workday Applier — handles multi-step applications on Workday (myworkdayjobs.com) portals.
Supports account creation, resume upload, and form filling.
"""

import asyncio
import os
from loguru import logger
from applier.browser_manager import BrowserManager, human_like_type, human_like_click
from config import settings

class WorkdayApplier:
    """Specialized applier for Workday portals."""

    def __init__(self, browser_manager: BrowserManager):
        self.browser = browser_manager

    async def apply(self, page, job_url: str, job_id: int, 
                    resume_path: str = None, cover_letter_text: str = None) -> bool:
        """Navigate through the Workday application flow."""
        try:
            logger.info(f"Starting Workday application for: {job_url}")
            await page.goto(job_url, wait_until="networkidle")
            await asyncio.sleep(3)

            # 1. Click "Apply"
            apply_btn = page.locator('button:has-text("Apply"), a:has-text("Apply")').first
            if await apply_btn.is_visible():
                await apply_btn.click()
                await asyncio.sleep(2)

            # 2. Handle Login / Account Creation
            # Workday usually has "Apply Manually", "Use My Last Application", etc.
            manual_apply = page.locator('button:has-text("Apply Manually")').first
            if await manual_apply.is_visible():
                await manual_apply.click()
                await asyncio.sleep(3)

            # Check if we are at the sign-in/create account page
            if "login" in page.url or await page.locator('input[type="email"]').is_visible():
                success = await self._handle_auth(page)
                if not success:
                    return False

            # 3. Follow the multi-step form (usually 5-7 steps)
            # Step 1: My Information
            # Step 2: My Experience
            # Step 3: Application Questions
            # Step 4: Voluntary Disclosures
            # Step 5: Self-Identify
            # Step 6: Review
            
            steps_completed = 0
            max_steps = 10 # Safety limit
            
            while steps_completed < max_steps:
                # Check if we are at the "Review" or final "Submit" stage
                submit_btn = page.locator('button:has-text("Submit")').first
                if await submit_btn.is_visible() and "review" in page.url.lower():
                    if settings.dry_run:
                        logger.info(f"[DRY RUN] Would submit Workday application: {job_url}")
                        await self.browser.screenshot(page, "workday_final_review")
                        return True
                    await submit_btn.click()
                    await asyncio.sleep(5)
                    return True

                # Fill current page
                await self._fill_workday_page(page, resume_path, cover_letter_text)
                
                # Click "Save and Continue" or "Next"
                next_btn = page.locator('button:has-text("Save and Continue"), button:has-text("Next")').first
                if await next_btn.is_visible():
                    await next_btn.click()
                    await asyncio.sleep(4)
                    steps_completed += 1
                else:
                    break

            logger.warning(f"Workday application stalled or finished unexpectedly: {page.url}")
            return False

        except Exception as e:
            logger.error(f"Workday application failed: {e}")
            await self.browser.screenshot(page, "workday_error")
            return False

    async def _handle_auth(self, page) -> bool:
        """Handle Workday sign-in or account creation."""
        email = settings.workday_email
        password = settings.workday_password

        # Check if we need to "Create Account"
        create_account_btn = page.locator('button:has-text("Create Account")').first
        if await create_account_btn.is_visible():
            logger.info("Creating new Workday account...")
            await create_account_btn.click()
            await asyncio.sleep(2)
            
            await page.locator('input[data-automation-id="email"]').fill(email)
            await page.locator('input[data-automation-id="password"]').fill(password)
            await page.locator('input[data-automation-id="confirmPassword"]').fill(password)
            await page.locator('input[type="checkbox"]').check() # Terms
            
            await page.locator('button:has-text("Create Account")').click()
            await asyncio.sleep(5)
            # Note: Might require email verification here
            return True
        
        # Regular Sign In
        elif await page.locator('input[type="email"]').is_visible():
            logger.info("Signing into existing Workday account...")
            await page.locator('input[type="email"]').fill(email)
            await page.locator('input[type="password"]').fill(password)
            await page.locator('button:has-text("Sign In")').click()
            await asyncio.sleep(5)
            return True
            
        return False

    async def _fill_workday_page(self, page, resume_path: str, cover_letter: str):
        """Intelligently fill Workday specific form sections."""
        # 1. Resume Upload
        resume_upload = page.locator('div[data-automation-id="file-upload-drop-zone"], input[type="file"]')
        if await resume_upload.count() > 0 and resume_path:
            try:
                await resume_upload.first.set_input_files(resume_path)
                await asyncio.sleep(2)
            except:
                pass

        # 2. General inputs (Workday uses data-automation-id mostly)
        field_map = {
            "legalNameSection_firstName": settings.user_name.split()[0],
            "legalNameSection_lastName": settings.user_name.split()[-1],
            "addressSection_contactInformation_email": settings.user_email,
            "addressSection_contactInformation_phone": settings.user_phone,
            "addressSection_city": "Dublin",
            "addressSection_country": "Ireland",
        }

        for auto_id, value in field_map.items():
            field = page.locator(f'input[data-automation-id="{auto_id}"]')
            if await field.is_visible() and not await field.input_value():
                await field.fill(value)

        # 3. Handle radio buttons (Workday uses these for "Have you worked here before?", etc.)
        # Defaulting to "No" for most standard questions
        no_radios = page.locator('label:has-text("No")')
        count = await no_radios.count()
        for i in range(count):
            try:
                if await no_radios.nth(i).is_visible():
                    await no_radios.nth(i).click()
            except:
                pass
