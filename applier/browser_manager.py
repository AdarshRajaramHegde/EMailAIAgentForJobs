"""
Browser Manager — Playwright browser lifecycle management with anti-detection.
"""

import os
import asyncio
from typing import Optional

from loguru import logger

from config import settings


class BrowserManager:
    """Manages Playwright browser instances with anti-detection measures."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self.screenshot_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "screenshots"
        )
        os.makedirs(self.screenshot_dir, exist_ok=True)

    async def launch(self, headless: bool = True, session_name: str = None):
        """Launch browser with anti-detection and optional session persistence."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        
        # Path for session storage (JSON-based for easy manual injection)
        storage_state = None
        if session_name:
            session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sessions")
            os.makedirs(session_dir, exist_ok=True)
            storage_path = os.path.join(session_dir, f"{session_name}.json")
            if os.path.exists(storage_path):
                storage_state = storage_path
                logger.info(f"Using saved session from: {storage_path}")

        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            channel="chrome",  # Use real Chrome for better anti-detection
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
            ],
        )
        
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-GB",
            timezone_id="Europe/Dublin",
            storage_state=storage_state,
        )

        # Anti-detection JavaScript
        await self._context.add_init_script("""
            // Overwrite the `webdriver` property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-GB', 'en-US', 'en']
            });

            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Internal PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }
                ]
            });

            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Mock WebGL
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Open Source Technology Center';
                if (parameter === 37446) return 'Mesa DRI Intel(R) HD Graphics 520 (Skylake GT2)';
                return getParameter.apply(this, arguments);
            };

            // Avoid hardware concurrency leaks
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });

            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        """)

        logger.info("Browser launched with anti-detection settings")
        return self._context

    async def new_page(self):
        """Create a new page in the browser context."""
        if not self._context:
            await self.launch()
        return await self._context.new_page()

    async def save_state(self, session_name: str):
        """Save current storage state to a JSON file."""
        if not self._context:
            logger.warning("No active context to save state from")
            return

        session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sessions")
        os.makedirs(session_dir, exist_ok=True)
        storage_path = os.path.join(session_dir, f"{session_name}.json")
        
        await self._context.storage_state(path=storage_path)
        logger.info(f"Session state saved to: {storage_path}")
        return storage_path

    async def screenshot(self, page, name: str = "screenshot"):
        """Take a screenshot and save it."""
        from datetime import datetime
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.screenshot_dir, f"{name}_{timestamp}.png")
        await page.screenshot(path=path, full_page=True)
        logger.info(f"Screenshot saved: {path}")
        return path

    async def close(self):
        """Close browser and playwright."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def __aenter__(self):
        await self.launch()
        return self

    async def __aexit__(self, *args):
        await self.close()


async def human_like_type(page, selector: str, text: str, delay: int = 50):
    """Type text with human-like delays."""
    import random
    element = page.locator(selector)
    await element.click()
    await element.fill("")  # Clear first

    for char in text:
        await element.type(char, delay=random.randint(delay - 20, delay + 50))
        if random.random() < 0.05:  # Occasional pause
            await asyncio.sleep(random.uniform(0.1, 0.3))


async def human_like_click(page, selector: str):
    """Click with human-like behavior."""
    import random
    await asyncio.sleep(random.uniform(0.2, 0.8))
    await page.locator(selector).click()
    await asyncio.sleep(random.uniform(0.3, 1.0))
