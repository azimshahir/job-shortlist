# Daily Job Shortlist

Scrapes LinkedIn and Indeed every morning for jobs posted in the last 24 hours
in Kuala Lumpur and Selangor, filters them with keyword rules, scores what's
left, and emails a shortlist at **8am Malaysia time**.

No LLM calls anywhere — it's pure keyword matching, so running it costs nothing.

## Files

| File | What it does |
|---|---|
| `scraper.py` | Main script: scrape → dedupe → score → email |
| `filters.py` | All the keyword rules and the score threshold |
| `test_filters.py` | Sample jobs to check the rules behave (`python test_filters.py`) |
| `.github/workflows/daily.yml` | The daily schedule + manual run button |
| `requirements.txt` | Python dependencies |

## How the filtering works

Two stages, in this order:

1. **Hard reject.** If a job mentions anything in `HARD_REJECT` (month-end close,
   SAP, ACCA qualified, procurement, "8+ years", etc.) it is dropped
   immediately — the score is never even calculated.
2. **Scoring.** Every `BOOST_KEYWORDS` phrase that appears adds its weight
   (4 = core strength, 1 = minor bonus). Jobs scoring `MIN_SCORE` or higher
   make the email.

`MIN_SCORE` starts at **6** — near the top of `filters.py`. Lower it to see
more jobs, raise it for a stricter list.

### Two deliberate exceptions

- **"transfer pricing"** is a hard reject (tax work), but **"fund transfer
  pricing"** is a boost (treasury/ALM). A negative lookbehind keeps them apart.
- **"mandarin"** on its own is *not* a reject — it usually appears as "is an
  advantage". Only mandatory phrasings ("fluent in Mandarin", "Mandarin is a
  must") reject the job.

## Tuning it

Every run uploads `raw_jobs.csv` — the complete unfiltered scrape — as a
GitHub Actions artifact. Download it from the run page to see exactly what got
filtered out, then adjust the keywords or `MIN_SCORE`.

After any change to `filters.py`, run:

```bash
python test_filters.py
```

## Environment variables

Set as GitHub repository secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASS` | Gmail **app password** (16 characters, not your normal password) |
| `EMAIL_TO` | Where to send the shortlist |

## Running it locally

```bash
pip install -r requirements.txt
python scraper.py
```

The email step will fail without the three environment variables set — that's
fine for testing the scrape itself. The scoring results still print to the
console and `raw_jobs.csv` is still written.

## Schedule

Cron `0 0 * * *` = 00:00 UTC = 08:00 MYT (Malaysia is UTC+8 year-round, no
daylight saving). GitHub's scheduler can run a few minutes late under load;
that's normal.

You always get an email, even when nothing matched, so you know it ran.
