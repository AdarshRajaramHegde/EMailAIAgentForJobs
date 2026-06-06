# 🤖 AI Job Application Agent (100% FREE Stack)

An automated Python system that discovers jobs across job boards and company career pages, scores them for relevance, tailors your resume and cover letter with AI, auto-applies, and sends you daily reports — running 24/7 on GitHub Actions **completely free**.

## 💰 Cost: $0/month

| Service | Free Tier | What We Use |
|---------|-----------|-------------|
| **Google Gemini API** | 15 req/min, 1,500/day | AI resume tailoring + scoring |
| **Supabase** | 500MB, 50k rows | Job database (or local SQLite) |
| **GitHub Actions** | 2,000 min/month | 24/7 scheduling (~360 min used) |
| **Gmail SMTP** | 500 emails/day | Notifications & reports |
| **Python + Playwright** | Open source | Scraping + auto-apply |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd "Apply Jobs"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Get Free API Keys

| Service | Where to Get | Time |
|---------|-------------|------|
| **Gemini API Key** | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | 30 seconds |
| **Resend API Key** | [resend.com](https://resend.com) (Recommended Free Email) | 1 minute |
| **Gmail App Password** | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) | 1 minute |
| **Supabase** | [supabase.com](https://supabase.com) | 2 minutes |

### 4. Database Setup (Supabase)

From your Supabase dashboard (as seen in your screenshot):
- **Project URL**: Copy the "Project URL" into `SUPABASE_URL` in `.env`.
- **API Key**: Copy the "Publishable Key" (starts with `sb_publishable_`) into `SUPABASE_KEY` in `.env`.
- **Database URL**: Use the "Direct connection string" but replace `[YOUR-PASSWORD]` with the password you chose during setup.
  - Example: `postgresql://postgres:MySecurePassword123@db.hnegtcfbxpggikaigtke.supabase.co:5432/postgres`

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your API keys and details
```

### 4. Run Locally (Test First)

```bash
# Initialize database
python main.py --init-db

# Dry run — discovers and scores jobs, NO applications submitted
python main.py --dry-run

# Discovery only
python main.py --discover

# Full pipeline (filter → score → tailor → apply)
python main.py --pipeline

# Send a test report
python main.py --report
```

### 5. Deploy to GitHub Actions (FREE 24/7)

```bash
# Push to GitHub
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USER/job-agent.git
git push -u origin main
```

Then add your secrets in GitHub → Settings → Secrets:

| Secret Name | Value |
|-------------|-------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `SMTP_USER` | your.email@gmail.com |
| `SMTP_PASSWORD` | Gmail app password |
| `NOTIFICATION_EMAIL` | your.email@gmail.com |
| `LINKEDIN_EMAIL` | LinkedIn login email |
| `LINKEDIN_PASSWORD` | LinkedIn password |
| `DRY_RUN` | `true` (set `false` when ready) |

The agent will automatically:
- ✅ Discover jobs every 2 hours
- ✅ Send daily summary at 8 PM
- ✅ Send weekly report on Sundays at 9 AM
- ✅ Auto-retry on failure
- ✅ Cache data between runs

---

## 📊 How It Works

```
┌─────────────────────────────────────────────────────────┐
│              DISCOVERY (every 2h via GitHub Actions)     │
│  LinkedIn · Indeed · Glassdoor · IrishJobs · Jobs.ie    │
│  Monster · Recruit Ireland · Google Jobs                │
│  + 25 known Dublin tech companies' career pages         │
│  + Google search for new career pages                   │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  FILTER & SCORE                         │
│  Title match · Location · Salary · Experience level     │
│  Deduplication · Gemini AI Relevance Score (0-100)      │
│  High-score alert (90+) → instant email notification    │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│            AI TAILORING (Google Gemini — FREE)           │
│  Resume tailored per job · ATS keyword optimization     │
│  Personalized cover letter · Skills matching            │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                 AUTO-APPLY                               │
│  LinkedIn Easy Apply · Indeed Easy Apply                │
│  Generic form fill (any career page)                    │
│  Email application (resume + cover letter attached)     │
│  ⚠️ Manual flags: video interviews, assessments        │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│          NOTIFICATIONS (Gmail SMTP — FREE)              │
│  📧 Daily summary email (8 PM)                          │
│  🔥 Instant alerts for 90+ score jobs                   │
│  📊 Weekly analytics (Sundays 9 AM)                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🏗 Project Structure

```
Apply Jobs/
├── main.py                          # Entry point + CLI
├── config.py                        # Settings from .env
├── scheduler.py                     # APScheduler + pipeline orchestration
├── .github/workflows/job-agent.yml  # GitHub Actions (FREE 24/7)
│
├── scrapers/                        # 7 job board scrapers
│   ├── linkedin.py, indeed.py, glassdoor.py
│   ├── irishjobs.py, monster.py, recruit_ireland.py
│   └── google_jobs.py
│
├── discovery/                       # Career page discovery
│   ├── career_page_finder.py        # Google search + IDA Ireland
│   ├── career_page_crawler.py       # Crawl known career pages
│   └── linkedin_company_monitor.py
│
├── filtering/                       # Filter + Score
│   ├── filter_engine.py             # Title/location/salary filter
│   ├── dedup.py                     # URL hash + fuzzy dedup
│   └── scorer.py                    # Rule-based + Gemini AI scoring
│
├── ai/                              # AI Tailoring (Gemini FREE)
│   ├── llm_client.py                # Google Gemini API client
│   ├── resume_tailor.py             # AI resume tailoring
│   ├── cover_letter_generator.py    # AI cover letter
│   └── ats_optimizer.py             # ATS keyword extraction
│
├── applier/                         # Auto-Apply
│   ├── browser_manager.py           # Playwright + anti-detection
│   ├── linkedin_applier.py          # LinkedIn Easy Apply
│   ├── indeed_applier.py            # Indeed Easy Apply
│   ├── generic_form_filler.py       # Any career page form
│   ├── email_applier.py             # SMTP email applications
│   └── manual_flag.py               # Flag manual-only jobs
│
├── notifications/                   # Notifications (Gmail FREE)
│   ├── email_notifier.py            # Daily/weekly/alert emails
│   └── report_generator.py          # Analytics data
│
├── database/                        # Storage (SQLite FREE / Supabase FREE)
│   ├── models.py                    # Company, Job, Application tables
│   └── db.py                        # CRUD helpers
│
└── data/                            # Local data
    ├── base_resume.pdf
    ├── tailored/                    # AI-generated resumes
    └── logs/                        # Application logs
```

---

## ⚙️ Configuration

| Variable | Description | Default |
|---|---|---|
| `DRY_RUN` | Preview mode — no submissions | `true` |
| `MIN_RELEVANCE_SCORE` | Minimum score to auto-apply | `60` |
| `HIGH_RELEVANCE_THRESHOLD` | Score for instant email alerts | `90` |
| `MAX_DAILY_APPLICATIONS` | Daily application cap | `50` |
| `SCRAPE_INTERVAL_HOURS` | Job board check frequency | `2` |

---

## 📈 Free Tier Limits

| Service | Limit | Our Usage | Headroom |
|---------|-------|-----------|----------|
| GitHub Actions | 2,000 min/month | ~360 min | 5.5× |
| Gemini API | 1,500 req/day | ~50-100 req/day | 15× |
| Gmail SMTP | 500 emails/day | ~5-10/day | 50× |
| Supabase | 50k rows | ~few thousand | 10× |

---

## ⚠️ Important Notes

1. **Start with `DRY_RUN=true`** — Test before going live
2. **Gemini rate limits** — Free tier is 15 req/min. Built-in handling waits 60s and retries
3. **LinkedIn/Indeed ToS** — Automated applying may violate terms. Use at your own risk
4. **GitHub Actions cron** — May have ±5 min variance in schedule timing
5. **Flagged jobs** — Video interviews, assessments, and coding challenges are auto-flagged for manual review
