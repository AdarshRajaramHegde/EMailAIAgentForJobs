"""
Generic Form Filler — auto-fills application forms on company career pages.
Uses AI to intelligently map form fields to user data.
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, List

from loguru import logger

from config import settings
from applier.browser_manager import BrowserManager
from database.db import get_session, create_application, log_application_event
from database.models import ApplicationStatus


class GenericFormFiller:
    """AI-assisted generic form filler for company career pages."""

    # Common field patterns and their corresponding user data
    FIELD_MAP = {
        # Name fields
        "first.?name": lambda: settings.user_name.split()[0] if settings.user_name else "",
        "last.?name": lambda: settings.user_name.split()[-1] if len(settings.user_name.split()) > 1 else "",
        "full.?name": lambda: settings.user_name,
        "^name$": lambda: settings.user_name,

        # Contact
        "email": lambda: settings.user_email,
        "phone|mobile|tel": lambda: settings.user_phone,

        # Location
        "city|town": lambda: "Dublin",
        "country": lambda: "Ireland",
        "location|address": lambda: settings.target_location,
        "zip|postal|eircode": lambda: "",

        # Professional
        "linkedin": lambda: settings.linkedin_profile_url,
        "website|portfolio|github": lambda: settings.linkedin_profile_url,
        "salary|compensation": lambda: str(settings.preferred_salary_min),
        "experience|years": lambda: "5" if settings.experience_level == "Senior" else "3" if settings.experience_level == "Mid" else "1",

        # Work authorization
        "authorized|right.to.work|visa": lambda: "Yes",
        "sponsorship": lambda: "No",
        "relocate": lambda: "No",
        "start.?date|availability": lambda: "Immediately",
        "notice.?period": lambda: "2 weeks",
    }

    def __init__(self, browser_manager: BrowserManager = None):
        self.browser = browser_manager or BrowserManager()

    async def apply(self, page, job_url: str, job_id: int,
                    resume_path: str = None, cover_letter_text: str = None) -> bool:
        """Navigate to a career page and fill out the application form."""
        session = get_session()

        try:
            await page.goto(job_url, wait_until="networkidle")
            await asyncio.sleep(3)

            # Look for an apply button first
            apply_selectors = [
                'a:has-text("Apply")',
                'button:has-text("Apply")',
                'a:has-text("Apply Now")',
                'button:has-text("Apply Now")',
                'a:has-text("Submit Application")',
                'input[value*="Apply"]',
            ]

            for selector in apply_selectors:
                btn = page.locator(selector).first
                if await btn.is_visible():
                    if settings.dry_run:
                        logger.info(f"[DRY RUN] Would click apply button: {job_url}")
                        return True
                    await btn.click()
                    await asyncio.sleep(3)
                    break

            # Create application record
            app = create_application(session, job_id=job_id, method="form_fill")
            log_application_event(session, app.id, "form_fill_started", f"URL: {job_url}")

            # Scan and fill the form
            filled = await self._fill_all_fields(page, resume_path, cover_letter_text)
            log_application_event(session, app.id, "fields_filled", f"Filled {filled} fields")

            if settings.dry_run:
                logger.info(f"[DRY RUN] Form filled with {filled} fields for: {job_url}")
                await self.browser.screenshot(page, "form_filled_dryrun")
                return True

            # Try to submit
            submitted = await self._submit_form(page)

            if submitted:
                app.status = ApplicationStatus.APPLIED.value
                app.applied_at = datetime.utcnow()
                session.commit()
                log_application_event(session, app.id, "submitted", "Form submitted successfully")
                logger.info(f"✅ Generic form submitted: {job_url}")
                return True
            else:
                logger.warning(f"Could not find submit button for: {job_url}")
                await self.browser.screenshot(page, "form_no_submit")
                return False

        except Exception as e:
            logger.error(f"Generic form fill failed for {job_url}: {e}")
            await self.browser.screenshot(page, "form_error")
            return False
        finally:
            session.close()

    async def _fill_all_fields(self, page, resume_path: str = None, cover_letter: str = None) -> int:
        """Fill all detectable form fields on the page."""
        import re
        filled_count = 0

        # 1. Text inputs
        inputs = page.locator('input[type="text"]:visible, input[type="email"]:visible, input[type="tel"]:visible, input[type="url"]:visible, input[type="number"]:visible')
        count = await inputs.count()

        for i in range(count):
            inp = inputs.nth(i)
            try:
                value = await inp.input_value()
                if value:  # Skip pre-filled
                    continue

                # Get field identifiers
                field_id = await inp.get_attribute("id") or ""
                field_name = await inp.get_attribute("name") or ""
                field_label = await inp.get_attribute("aria-label") or ""
                field_placeholder = await inp.get_attribute("placeholder") or ""
                identifiers = f"{field_id} {field_name} {field_label} {field_placeholder}".lower()

                # Match against our field map
                fill_value = self._resolve_field(identifiers)
                if fill_value:
                    await inp.fill(fill_value)
                    filled_count += 1

            except Exception as e:
                logger.debug(f"Skip input {i}: {e}")

        # 2. Textareas (cover letter, additional info)
        textareas = page.locator("textarea:visible")
        ta_count = await textareas.count()
        for i in range(ta_count):
            ta = textareas.nth(i)
            try:
                value = await ta.input_value()
                if not value and cover_letter:
                    await ta.fill(cover_letter)
                    filled_count += 1
            except Exception:
                pass

        # 3. File uploads (resume)
        if resume_path:
            file_inputs = page.locator('input[type="file"]')
            fi_count = await file_inputs.count()
            for i in range(fi_count):
                try:
                    await file_inputs.nth(i).set_input_files(resume_path)
                    filled_count += 1
                    await asyncio.sleep(1)
                except Exception:
                    pass

        # 4. Selects — try to pick reasonable options
        selects = page.locator("select:visible")
        sel_count = await selects.count()
        for i in range(sel_count):
            try:
                sel = selects.nth(i)
                options = sel.locator("option")
                opt_count = await options.count()

                # Try to find a "Yes" or relevant option
                for j in range(opt_count):
                    opt_text = await options.nth(j).text_content()
                    if opt_text and opt_text.strip().lower() in ["yes", "full-time", "full time", "immediately"]:
                        await sel.select_option(index=j)
                        filled_count += 1
                        break
                else:
                    # Select first non-empty option
                    if opt_count > 1:
                        await sel.select_option(index=1)
                        filled_count += 1
            except Exception:
                pass

        # 5. Checkboxes (terms & conditions, etc.)
        checkboxes = page.locator('input[type="checkbox"]:visible')
        cb_count = await checkboxes.count()
        for i in range(cb_count):
            try:
                cb = checkboxes.nth(i)
                if not await cb.is_checked():
                    await cb.check()
                    filled_count += 1
            except Exception:
                pass

        return filled_count

    def _resolve_field(self, identifiers: str) -> Optional[str]:
        """Match field identifiers to user data."""
        import re
        for pattern, getter in self.FIELD_MAP.items():
            if re.search(pattern, identifiers, re.I):
                return getter()
        return None

    async def _submit_form(self, page) -> bool:
        """Find and click the submit button."""
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Submit Application")',
            'button:has-text("Apply")',
            'button:has-text("Send Application")',
            'a:has-text("Submit")',
        ]

        for selector in submit_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(3)
                    return True
            except Exception:
                continue

        return False
