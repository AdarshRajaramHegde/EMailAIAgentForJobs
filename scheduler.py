"""
Scheduler — APScheduler setup for periodic job discovery, application, and reporting.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config import settings


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 600,
        }
    )

    # ── Job Discovery (every 1-2 hours) ──────────────────────
    scheduler.add_job(
        run_job_discovery,
        trigger=IntervalTrigger(hours=settings.scrape_interval_hours),
        id="job_discovery",
        name="Job Board Discovery",
        replace_existing=True,
    )

    # ── Career Page Crawling (every 6 hours) ─────────────────
    scheduler.add_job(
        run_career_page_crawl,
        trigger=IntervalTrigger(hours=settings.career_page_check_hours),
        id="career_page_crawl",
        name="Career Page Crawling",
        replace_existing=True,
    )

    # ── Company Discovery (daily at 6 AM) ────────────────────
    scheduler.add_job(
        run_company_discovery,
        trigger=CronTrigger(hour=6, minute=0),
        id="company_discovery",
        name="Company Career Page Discovery",
        replace_existing=True,
    )

    # ── Process Pipeline (every 2 hours, offset by 30 min) ───
    scheduler.add_job(
        run_processing_pipeline,
        trigger=IntervalTrigger(hours=settings.scrape_interval_hours, minutes=30),
        id="process_pipeline",
        name="Filter → Score → Tailor → Apply Pipeline",
        replace_existing=True,
    )

    # ── Daily Summary (8 PM Dublin time) ─────────────────────
    scheduler.add_job(
        run_daily_summary,
        trigger=CronTrigger(hour=20, minute=0, timezone="Europe/Dublin"),
        id="daily_summary",
        name="Daily Summary Email",
        replace_existing=True,
    )

    # ── Weekly Report (Sunday 9 AM Dublin time) ──────────────
    scheduler.add_job(
        run_weekly_report,
        trigger=CronTrigger(day_of_week="sun", hour=9, minute=0, timezone="Europe/Dublin"),
        id="weekly_report",
        name="Weekly Analytics Report",
        replace_existing=True,
    )

    logger.info("Scheduler configured with all jobs")
    return scheduler


# ── Scheduled Task Functions ─────────────────────────────────

async def run_job_discovery():
    """Scrape all job boards for new listings."""
    logger.info("━" * 60)
    logger.info("🔍 Starting job board discovery cycle...")

    from scrapers.linkedin import LinkedInScraper
    from scrapers.linkedin import LinkedInScraper
    from scrapers.glassdoor import GlassdoorScraper
    from scrapers.irishjobs import IrishJobsScraper
    from scrapers.monster import MonsterScraper
    from scrapers.recruit_ireland import RecruitIrelandScraper
    from scrapers.google_jobs import GoogleJobsScraper
    from scrapers.publicjobs import PublicJobsScraper
    from scrapers.jobsireland import JobsIrelandScraper
    from database.db import get_session, upsert_job
    from filtering.dedup import DeduplicationEngine

    dedup = DeduplicationEngine()
    titles = settings.titles_list
    location = settings.target_location
    total_new = 0

    scrapers = [
        LinkedInScraper(),
        GlassdoorScraper(),
        IrishJobsScraper(),
        MonsterScraper(),
        RecruitIrelandScraper(),
        GoogleJobsScraper(),
        PublicJobsScraper(),
        JobsIrelandScraper(),
    ]

    session = get_session()
    try:
        for job_title in titles:
            logger.info(f"🔍 Searching for '{job_title}' in '{location}'...")
            for scraper in scrapers:
                try:
                    async with scraper:
                        raw_jobs = await scraper.scrape(job_title, location)

                        for raw in raw_jobs:
                            if not dedup.is_duplicate(raw.url, raw.title, raw.company_name):
                                result = upsert_job(
                                    session,
                                    url=raw.url,
                                    title=raw.title,
                                    source=raw.source,
                                    company_name=raw.company_name,
                                    location=raw.location,
                                    description=raw.description,
                                    salary_min=raw.salary_min,
                                    salary_max=raw.salary_max,
                                    salary_currency=raw.salary_currency,
                                    job_type=raw.job_type,
                                    is_easy_apply=raw.is_easy_apply,
                                    application_email=raw.application_email,
                                    external_id=raw.external_id,
                                    posted_at=raw.posted_at,
                                )
                                if result:
                                    total_new += 1
                                    dedup.mark_seen(raw.url)

                except Exception as e:
                    logger.error(f"Scraper {scraper.SOURCE_NAME} failed: {e}")
    finally:
        session.close()

    logger.info(f"✅ Job discovery complete: {total_new} new jobs found")


async def run_career_page_crawl():
    """Crawl company career pages for new openings."""
    logger.info("🏢 Starting career page crawl...")

    from discovery.career_page_crawler import CareerPageCrawler

    crawler = CareerPageCrawler()
    try:
        new_jobs = await crawler.crawl_all_due()
        logger.info(f"✅ Career page crawl complete: {new_jobs} new jobs")
    finally:
        await crawler.close()


async def run_company_discovery():
    """Discover new company career pages."""
    logger.info("🔎 Starting company discovery...")

    from discovery.career_page_finder import CareerPageFinder

    finder = CareerPageFinder()
    try:
        companies = await finder.discover_all()
        logger.info(f"✅ Company discovery complete: {len(companies)} companies")
    finally:
        await finder.close()


async def run_processing_pipeline():
    """Process new jobs: filter → score → tailor → apply."""
    logger.info("⚙️ Starting processing pipeline...")

    from database.db import get_session, get_unscored_jobs, get_jobs_by_status
    from database.models import Job, JobStatus
    from filtering.filter_engine import FilterEngine
    from filtering.scorer import RelevanceScorer
    from ai.llm_client import LLMClient
    from ai.resume_tailor import ResumeTailor
    from ai.cover_letter_generator import CoverLetterGenerator
    from applier.manual_flag import ManualFlagDetector
    from applier.linkedin_applier import LinkedInApplier
    from applier.generic_form_filler import GenericFormFiller
    from applier.workday_applier import WorkdayApplier
    from applier.greenhouse_applier import GreenhouseApplier
    from applier.email_applier import EmailApplier
    from applier.browser_manager import BrowserManager
    from notifications.email_notifier import EmailNotifier
    from notifications.whatsapp_notifier import WhatsAppNotifier
    import json

    session = get_session()
    llm = LLMClient()
    filter_engine = FilterEngine()
    scorer = RelevanceScorer(llm_client=llm)
    flag_detector = ManualFlagDetector()
    resume_tailor = ResumeTailor(llm_client=llm)
    cover_gen = CoverLetterGenerator(llm_client=llm)
    email_notifier = EmailNotifier()
    whatsapp = WhatsAppNotifier()

    try:
        # 1. Score unscored jobs
        unscored = get_unscored_jobs(session)
        logger.info(f"Scoring {len(unscored)} new jobs...")

        for job in unscored:
            # Filter first
            from scrapers import RawJob
            raw = RawJob(
                title=job.title,
                company_name=job.company_name or "",
                url=job.url,
                source=job.source,
                location=job.location or "",
                salary_min=job.salary_min,
                salary_max=job.salary_max,
            )

            if not filter_engine.passes_all_filters(raw):
                job.status = JobStatus.SKIPPED.value
                session.commit()
                continue

            # Score
            if llm.is_available:
                result = await scorer.score_with_ai(
                    job.title, job.description or "", job.company_name or ""
                )
            else:
                result = scorer.score(
                    job.title, job.description or "", job.location or "",
                    job.salary_min, job.salary_max, job.company_name or ""
                )

            job.relevance_score = result["score"]
            # Store the full result including best_resume in breakdown
            job.score_breakdown = json.dumps({
                "breakdown": result.get("breakdown", {}),
                "best_resume": result.get("best_resume"),
                "reasoning": result.get("reasoning", "")
            })
            job.status = JobStatus.SCORED.value
            session.commit()

            # High relevance alert
            if result["score"] >= settings.high_relevance_threshold:
                try:
                    email_notifier.send_high_relevance_alert(job)
                    whatsapp.send_high_relevance_alert(
                        job.title, job.company_name or "", result["score"], job.url
                    )
                except Exception as e:
                    logger.warning(f"Alert notification failed: {e}")

        # 2. Handle notify/apply logic
        scored = get_jobs_by_status(session, JobStatus.SCORED.value)
        
        # Decide which jobs to notify
        if settings.email_all_listings:
            to_notify = scored
            logger.info(f"📧 Sending summary for all {len(to_notify)} discovered jobs...")
        else:
            to_notify = [j for j in scored if (j.relevance_score or 0) >= settings.min_relevance_score]
            logger.info(f"📧 Email-only mode: Notifying {len(to_notify)} qualified jobs...")
        
        if not settings.apply_automatically:
            if to_notify:
                try:
                    email_notifier.send_new_jobs_email(to_notify)
                    for job in to_notify:
                        job.status = JobStatus.NOTIFIED.value
                    session.commit()
                except Exception as e:
                    logger.error(f"Failed to send job list email: {e}")
            logger.info("✅ Pipeline complete (notification sent)")
            return

        # 3. Process qualified jobs for application
        logger.info(f"Processing {len(qualified)} qualified jobs for application...")
        applied_count = 0
        daily_limit = settings.max_daily_applications

        browser = None

        for job in qualified:
            if applied_count >= daily_limit:
                logger.info(f"Daily application limit ({daily_limit}) reached")
                break

            # Check for manual flags
            should_flag, reasons = flag_detector.check_job(job.title, job.description or "")
            if should_flag:
                flag_detector.flag_job(job.id, reasons)
                continue

            # Tailor resume and cover letter
            try:
                # Load the best resume from score_breakdown
                breakdown_data = json.loads(job.score_breakdown)
                best_resume_path = breakdown_data.get("best_resume") or settings.base_resume_path

                tailored = await resume_tailor.tailor_resume(
                    job.title, job.description or "", job.company_name or "",
                    base_resume_path=best_resume_path
                )
                cover = await cover_gen.generate(
                    job.title, job.description or "",
                    job.company_name or "", tailored.get("text", "")
                )

                job.status = JobStatus.TAILORED.value
                session.commit()
            except Exception as e:
                logger.error(f"Tailoring failed for job {job.id}: {e}")
                continue

            # Apply
            try:
                if job.application_email:
                    # Email application
                    email_applier = EmailApplier()
                    success = email_applier.apply(
                        to_email=job.application_email,
                        job_title=job.title,
                        company_name=job.company_name or "",
                        job_id=job.id,
                        resume_path=tailored.get("file_path"),
                        cover_letter_text=cover.get("text"),
                        cover_letter_path=cover.get("file_path"),
                    )
                elif job.is_easy_apply and "linkedin" in job.source:
                    # LinkedIn Easy Apply
                    if not browser:
                        browser = BrowserManager()
                        await browser.launch(headless=True, session_name="linkedin")
                    page = await browser.new_page()
                    linkedin = LinkedInApplier(browser)
                    await linkedin.login(page)
                    success = await linkedin.apply(
                        page, job.url, job.id,
                        resume_path=tailored.get("file_path"),
                        cover_letter_text=cover.get("text"),
                    )
                    await page.close()
                    await page.close()
                elif "myworkdayjobs.com" in job.url:
                    # Workday specialized flow
                    if not browser:
                        browser = BrowserManager()
                        await browser.launch(headless=True)
                    page = await browser.new_page()
                    workday = WorkdayApplier(browser)
                    success = await workday.apply(
                        page, job.url, job.id,
                        resume_path=tailored.get("file_path"),
                        cover_letter_text=cover.get("text"),
                    )
                    await page.close()
                elif "greenhouse.io" in job.url:
                    # Greenhouse specialized flow
                    if not browser:
                        browser = BrowserManager()
                        await browser.launch(headless=True)
                    page = await browser.new_page()
                    greenhouse = GreenhouseApplier(browser)
                    success = await greenhouse.apply(
                        page, job.url, job.id,
                        resume_path=tailored.get("file_path"),
                        cover_letter_text=cover.get("text"),
                    )
                    await page.close()
                else:
                    # Generic form fill
                    if not browser:
                        browser = BrowserManager()
                        await browser.launch(headless=True)
                    page = await browser.new_page()
                    filler = GenericFormFiller(browser)
                    success = await filler.apply(
                        page, job.url, job.id,
                        resume_path=tailored.get("file_path"),
                        cover_letter_text=cover.get("text"),
                    )
                    await page.close()

                if success:
                    job.status = JobStatus.APPLIED.value
                    applied_count += 1
                    session.commit()

            except Exception as e:
                logger.error(f"Application failed for job {job.id}: {e}")

        if browser:
            await browser.close()

        logger.info(f"✅ Pipeline complete: {applied_count} applications submitted")

    finally:
        session.close()


async def run_daily_summary():
    """Send daily summary notification."""
    logger.info("📧 Sending daily summary...")
    from notifications.email_notifier import EmailNotifier
    from notifications.whatsapp_notifier import WhatsAppNotifier
    from database.db import get_daily_stats, get_session

    notifier = EmailNotifier()
    notifier.send_daily_summary()

    whatsapp = WhatsAppNotifier()
    if whatsapp.is_available:
        session = get_session()
        stats = get_daily_stats(session)
        session.close()
        whatsapp.send_daily_summary(
            stats["jobs_discovered"],
            stats["applications_submitted"],
            stats["flagged_for_review"],
        )


async def run_weekly_report():
    """Send weekly analytics report."""
    logger.info("📊 Sending weekly report...")
    from notifications.email_notifier import EmailNotifier

    notifier = EmailNotifier()
    notifier.send_weekly_report()
