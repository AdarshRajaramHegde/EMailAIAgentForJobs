"""
AI Job Application Agent — Main Entry Point

Usage:
    python main.py              # Start the full agent (scheduler)
    python main.py --dry-run    # Run once in dry-run mode (no submissions)
    python main.py --discover   # Run discovery only
    python main.py --pipeline   # Run the processing pipeline once
"""

import sys
import asyncio
import argparse
import signal

from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>",
    level="INFO",
)
logger.add(
    "data/logs/agent_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG",
)


def parse_args():
    parser = argparse.ArgumentParser(description="AI Job Application Agent")
    parser.add_argument("--dry-run", action="store_true", help="Run without submitting applications")
    parser.add_argument("--discover", action="store_true", help="Run job discovery only")
    parser.add_argument("--pipeline", action="store_true", help="Run processing pipeline once")
    parser.add_argument("--login", type=str, choices=["linkedin"], help="Manual login to save session")
    parser.add_argument("--report", action="store_true", help="Send a daily summary report")
    parser.add_argument("--init-db", action="store_true", help="Initialize database only")
    return parser.parse_args()


async def run_manual_login(platform: str):
    """Open a browser for manual login and save session."""
    from applier.browser_manager import BrowserManager
    import os

    logger.info("━" * 60)
    logger.info(f"🚀 MANUAL LOGIN: {platform.upper()}")
    logger.info("1. A browser window will open now (non-headless).")
    logger.info("2. Log in to your account manually.")
    logger.info("3. Navigate to your feed/home page.")
    logger.info("4. Come back here and press ENTER to save the session.")
    logger.info("━" * 60)

    browser = BrowserManager()
    # Launch in non-headless mode so user can see it
    await browser.launch(headless=False)
    page = await browser.new_page()

    if platform == "linkedin":
        await page.goto("https://www.linkedin.com/login")
    elif platform == "workday":
        logger.info("Navigate to a Workday job portal to log in.")

    # Wait for user input
    input(f"\n👉 Press Enter AFTER you have successfully logged in to {platform.capitalize()}... ")

    # Save state using the new helper
    state_path = await browser.save_state(platform)

    logger.info(f"✅ SUCCESS: {platform.capitalize()} session saved.")
    logger.info(f"   Path: {state_path}")
    logger.info("   The agent will now use this session for future applications.")
    
    await browser.close()


async def run_once():
    """Run a single cycle: discover → crawl → process."""
    from scheduler import run_job_discovery, run_career_page_crawl, run_processing_pipeline

    logger.info("🚀 Running single cycle...")
    await run_job_discovery()
    await run_career_page_crawl()
    await run_processing_pipeline()
    logger.info("✅ Single cycle complete")


async def run_discovery_only():
    """Run discovery without applying."""
    from scheduler import run_job_discovery, run_career_page_crawl, run_company_discovery

    logger.info("🔍 Running discovery only...")
    await run_company_discovery()
    await run_job_discovery()
    await run_career_page_crawl()
    logger.info("✅ Discovery complete")


async def run_scheduler():
    """Start the continuous scheduler."""
    from scheduler import create_scheduler

    scheduler = create_scheduler()
    scheduler.start()

    logger.info("━" * 60)
    logger.info("🤖 AI Job Application Agent — Running 24/7")
    logger.info(f"   Target: {settings.target_job_title}")
    logger.info(f"   Location: {settings.target_location}")
    logger.info(f"   Experience: {settings.experience_level}")
    logger.info(f"   Salary: {settings.preferred_salary_currency} {settings.preferred_salary_min:,} - {settings.preferred_salary_max:,}")
    logger.info(f"   DRY RUN: {'YES ⚠️' if settings.dry_run else 'NO — LIVE MODE'}")
    logger.info(f"   Scrape interval: every {settings.scrape_interval_hours} hours")
    logger.info(f"   Min relevance score: {settings.min_relevance_score}")
    logger.info(f"   Max daily applications: {settings.max_daily_applications}")
    logger.info("━" * 60)

    # Run initial discovery immediately
    from scheduler import run_job_discovery, run_processing_pipeline
    await run_job_discovery()
    await run_processing_pipeline()

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()


def main():
    import os
    os.makedirs("data/logs", exist_ok=True)
    os.makedirs("data/tailored", exist_ok=True)
    os.makedirs("data/screenshots", exist_ok=True)

    args = parse_args()

    # Import config and initialize DB
    global settings
    from config import settings as app_settings
    settings = app_settings

    if args.dry_run:
        settings.dry_run = True
        logger.info("⚠️ DRY RUN mode enabled — no applications will be submitted")

    from database.db import init_db
    init_db()
    logger.info("Database initialized")

    if args.init_db:
        logger.info("Database initialization complete. Exiting.")
        return

    if args.login:
        asyncio.run(run_manual_login(args.login))
    elif args.discover:
        asyncio.run(run_discovery_only())
    elif args.pipeline:
        asyncio.run(run_once())
    elif args.report:
        from notifications.email_notifier import EmailNotifier
        notifier = EmailNotifier()
        notifier.send_daily_summary()
        logger.info("Daily summary sent")
    else:
        asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
