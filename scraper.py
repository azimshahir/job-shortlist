"""
Daily job scraper -> filtered, scored shortlist -> email.

Run:  python scraper.py
Env:  SMTP_USER, SMTP_PASS, EMAIL_TO   (see README)

Nothing here calls an LLM. It is pure keyword matching, so it costs nothing
to run beyond GitHub Actions minutes.
"""

import os
import smtplib
import sys
import traceback
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape

import pandas as pd
from jobspy import scrape_jobs

from filters import MIN_SCORE, score_job

# --------------------------------------------------------------------------
# Search configuration
# --------------------------------------------------------------------------
SEARCH_TERMS = [
    "fund operations",
    "fund administration",
    "settlement operations",
    "reconciliation",
    "treasury operations",
    "liquidity risk",
    "business analyst finance",
    "process improvement",
    "operations analyst",
    "risk analyst",
    "investment operations",
    "governance compliance",
]

LOCATIONS = [
    "Kuala Lumpur, Malaysia",
    "Selangor, Malaysia",
]

SITES = ["linkedin", "indeed"]
HOURS_OLD = 24
RESULTS_WANTED = 40
COUNTRY_INDEED = "malaysia"

RAW_CSV = "raw_jobs.csv"

MYT = timezone(timedelta(hours=8))


# --------------------------------------------------------------------------
# Scraping
# --------------------------------------------------------------------------
def scrape_all() -> pd.DataFrame:
    """
    Run every (search term x location) combination.

    One failing combination must not kill the run, so each is wrapped in its
    own try/except and we just carry on with the rest.
    """
    frames = []
    failures = []

    for term in SEARCH_TERMS:
        for loc in LOCATIONS:
            label = f"'{term}' @ {loc}"
            try:
                df = scrape_jobs(
                    site_name=SITES,
                    search_term=term,
                    location=loc,
                    results_wanted=RESULTS_WANTED,
                    hours_old=HOURS_OLD,
                    country_indeed=COUNTRY_INDEED,
                    linkedin_fetch_description=True,
                    verbose=0,
                )
                n = 0 if df is None else len(df)
                print(f"  ok   {label}: {n} rows", flush=True)
                if n:
                    df = df.copy()
                    df["search_term"] = term
                    df["search_location"] = loc
                    frames.append(df)
            except Exception as exc:  # noqa: BLE001 - keep going no matter what
                failures.append(f"{label}: {type(exc).__name__}: {exc}")
                print(f"  FAIL {label}: {exc}", flush=True)

    if failures:
        print(f"\n{len(failures)} search(es) failed:", flush=True)
        for f in failures:
            print(f"  - {f}", flush=True)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Dedupe on job URL first, then on title+company as a fallback."""
    if df.empty:
        return df
    df = df.copy()
    if "job_url" in df.columns:
        df = df.drop_duplicates(subset=["job_url"], keep="first")
    key_cols = [c for c in ("title", "company") if c in df.columns]
    if key_cols:
        df["_k"] = (
            df[key_cols].fillna("").astype(str)
            .apply(lambda r: "|".join(v.strip().lower() for v in r), axis=1)
        )
        df = df.drop_duplicates(subset=["_k"], keep="first").drop(columns=["_k"])
    return df.reset_index(drop=True)


def evaluate(df: pd.DataFrame):
    """Score every row. Returns (kept_sorted, stats_dict)."""
    kept = []
    n_rejected = 0
    n_lowscore = 0

    for row in df.to_dict("records"):
        verdict = score_job(row)
        if verdict["rejected_by"]:
            n_rejected += 1
            continue
        if not verdict["keep"]:
            n_lowscore += 1
            continue
        kept.append({
            "title": row.get("title") or "(no title)",
            "company": row.get("company") or "-",
            "location": row.get("location") or "-",
            "site": row.get("site") or "-",
            "url": row.get("job_url") or "",
            "score": verdict["score"],
            "matched": verdict["matched"],
        })

    kept.sort(key=lambda j: -j["score"])
    stats = {
        "total": len(df),
        "hard_rejected": n_rejected,
        "below_threshold": n_lowscore,
        "kept": len(kept),
    }
    return kept, stats


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
def build_html(jobs: list, stats: dict) -> str:
    stamp = datetime.now(MYT).strftime("%A, %d %B %Y")
    head = (
        '<html><body style="font-family:-apple-system,Segoe UI,Arial,sans-serif;'
        'color:#1a1a1a;line-height:1.5;">'
        f'<h2 style="margin-bottom:4px;">Job shortlist &mdash; {stamp}</h2>'
        '<p style="color:#666;font-size:13px;margin-top:0;">'
        f"{stats['total']} jobs scraped &middot; {stats['hard_rejected']} hard-rejected "
        f"&middot; {stats['below_threshold']} below score {MIN_SCORE} &middot; "
        f"<strong>{stats['kept']} shortlisted</strong></p>"
    )

    if not jobs:
        body = (
            '<p style="padding:14px;background:#f6f6f6;border-radius:6px;">'
            "No jobs cleared the threshold today. The scraper ran fine &mdash; there "
            "just wasn't anything matching. Check the <code>raw_jobs.csv</code> "
            "artifact on the GitHub Actions run to see what got filtered out.</p>"
        )
        return head + body + "</body></html>"

    rows = []
    for j in jobs:
        title = escape(str(j["title"]))
        link = escape(str(j["url"]), quote=True)
        title_html = (
            f'<a href="{link}" style="color:#0b5fff;text-decoration:none;">{title}</a>'
            if link else title
        )
        matched = escape(", ".join(j["matched"])) or "&mdash;"
        rows.append(
            '<tr style="border-bottom:1px solid #e6e6e6;">'
            '<td style="padding:10px 8px;vertical-align:top;">'
            f'<div style="font-weight:600;font-size:15px;">{title_html}</div>'
            f'<div style="color:#444;font-size:13px;">{escape(str(j["company"]))}</div>'
            f'<div style="color:#777;font-size:12px;">{escape(str(j["location"]))}'
            f' &middot; {escape(str(j["site"]))}</div>'
            f'<div style="color:#0a7d33;font-size:12px;margin-top:4px;">'
            f'matched: {matched}</div></td>'
            '<td style="padding:10px 8px;vertical-align:top;text-align:right;'
            'font-weight:700;font-size:18px;color:#0b5fff;white-space:nowrap;">'
            f'{j["score"]}</td></tr>'
        )

    table = ('<table style="width:100%;border-collapse:collapse;margin-top:10px;">'
             + "".join(rows) + "</table>")
    foot = (
        '<p style="color:#888;font-size:12px;margin-top:18px;">'
        "Sorted by score, highest first. Tune <code>MIN_SCORE</code> and the keyword "
        "weights in <code>filters.py</code>.</p>"
    )
    return head + table + foot + "</body></html>"


def send_email(html: str, subject: str) -> None:
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    to = os.environ.get("EMAIL_TO")

    missing = [n for n, v in (("SMTP_USER", user), ("SMTP_PASS", password),
                              ("EMAIL_TO", to)) if not v]
    if missing:
        raise RuntimeError(f"Missing environment variable(s): {', '.join(missing)}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content("This email is HTML. Open it in an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"Email sent to {to}", flush=True)


# --------------------------------------------------------------------------
def main() -> int:
    print(f"Run started {datetime.now(MYT).isoformat()} (MYT)", flush=True)

    raw = scrape_all()
    print(f"\nScraped {len(raw)} raw rows", flush=True)

    # Always write the CSV, even when empty, so the artifact upload never fails.
    if raw.empty:
        pd.DataFrame(columns=["site", "title", "company", "location",
                              "job_url", "date_posted"]).to_csv(RAW_CSV, index=False)
    else:
        raw.to_csv(RAW_CSV, index=False, encoding="utf-8-sig")
    print(f"Wrote {RAW_CSV}", flush=True)

    deduped = dedupe(raw)
    print(f"{len(deduped)} rows after dedupe", flush=True)

    jobs, stats = evaluate(deduped)
    print(f"Stats: {stats}", flush=True)
    for j in jobs:
        print(f"  [{j['score']:>2}] {j['title']} - {j['company']}", flush=True)

    plural = "" if stats["kept"] == 1 else "es"
    subject = (f"Job shortlist: {stats['kept']} match{plural} "
               f"({datetime.now(MYT).strftime('%d %b')})")
    html = build_html(jobs, stats)

    try:
        send_email(html, subject)
    except Exception as exc:  # noqa: BLE001
        print(f"\nEMAIL FAILED: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
