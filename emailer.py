"""
Phase 8 -- the daily email.

Shows only the FINAL recommended jobs, not dozens of mediocre ones, and
attaches any tailored resumes. With zero strong matches it says so plainly
rather than padding the list.
"""

import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape

import config

MYT = timezone(timedelta(hours=config.MYT_UTC_OFFSET_HOURS))

DOCX_MIME = ("application", "vnd.openxmlformats-officedocument."
                            "wordprocessingml.document")


def _fmt_salary(job: dict) -> str:
    lo, hi = job.get("min_amount"), job.get("max_amount")

    def num(v):
        try:
            v = float(v)
            return f"{v:,.0f}" if v > 0 else None
        except (TypeError, ValueError):
            return None

    lo, hi = num(lo), num(hi)
    if not lo and not hi:
        return ""
    cur = str(job.get("currency") or "MYR")
    span = f"{lo} - {hi}" if lo and hi else (lo or hi)
    interval = str(job.get("interval") or "").strip()
    return f"{cur} {span}" + (f" / {interval}" if interval and interval != "nan" else "")


def _why(job: dict) -> str:
    bits = []
    match = job.get("strongest_profile_match")
    if match:
        bits.append(f"closest to your <strong>{escape(str(match))}</strong> experience")
    matched = job.get("matched_keywords") or []
    if matched:
        bits.append("matched: " + escape(", ".join(matched[:8])))
    return " &middot; ".join(bits)


def _scores_table(job: dict) -> str:
    """
    Everything needed to validate the ranking by hand -- this is the whole
    point of the pre-LLM production pipeline.
    """
    family = job.get("career_family")
    status = job.get("career_family_status")
    cells = [
        ("Career family",
         f"{escape(str(family or 'n/a')).replace('_', ' ')} "
         f"<em>({escape(str(status or 'ungated'))})</em>"),
        ("Keyword score", escape(str(job.get("keyword_score", "-")))),
        ("Semantic", f"{escape(str(job.get('semantic_score', '-')))}/100 "
                     f"(raw {escape(str(job.get('semantic_raw', '-')))}, "
                     f"rank #{escape(str(job.get('semantic_rank', '-')))})"),
        ("Final score", f"<strong>{escape(str(job.get('final_score', '-')))}</strong>"),
    ]
    rows = "".join(
        f'<tr><td style="padding:1px 10px 1px 0;color:#777;white-space:nowrap;">'
        f'{label}</td><td style="padding:1px 0;">{value}</td></tr>'
        for label, value in cells
    )
    reason = job.get("selection_reason")
    reason_html = (
        f'<div style="font-size:11px;color:#555;margin-top:5px;">'
        f'<strong>Why selected:</strong> {escape(str(reason))}</div>'
        if reason else ""
    )
    return (f'<table style="font-size:12px;margin-top:6px;border-collapse:collapse;">'
            f'{rows}</table>{reason_html}')


def _analysis_block(job: dict) -> str:
    """Render strong-LLM output when present; stay silent when it isn't."""
    analysis = job.get("llm_analysis")
    if not analysis:
        note = job.get("llm_note")
        if note:
            return (f'<div style="color:#8a6d00;font-size:12px;margin-top:5px;">'
                    f'{escape(str(note))}</div>')
        return ""

    rows = []
    verdict = analysis.get("overall_suitability")
    rationale = analysis.get("suitability_rationale")
    if verdict:
        rows.append(f'<div style="font-size:12px;margin-top:5px;">'
                    f'<strong>Suitability:</strong> {escape(str(verdict))}'
                    + (f" &mdash; {escape(str(rationale))}" if rationale else "")
                    + '</div>')
    gaps = analysis.get("gaps") or analysis.get("risks") or []
    if gaps:
        items = "; ".join(escape(str(g)) for g in gaps[:3])
        rows.append(f'<div style="color:#a33;font-size:12px;margin-top:3px;">'
                    f'<strong>Watch:</strong> {items}</div>')
    return "".join(rows)


def build_html(final_jobs: list, stats: dict) -> str:
    stamp = datetime.now(MYT).strftime("%A, %d %B %Y")
    funnel = (
        f"{stats.get('raw', 0)} scraped &rarr; "
        f"{stats.get('hard_rejected', 0)} hard-rejected &rarr; "
        f"{stats.get('keyword_passed', 0)} through keyword filter &rarr; "
        f"{stats.get('ranked', 0)} semantically ranked &rarr; "
        f"{stats.get('career_rejected', 0)} out-of-scope family &rarr; "
        f"{stats.get('history_excluded', 0)} already seen/applied &rarr; "
        f"<strong>{stats.get('selected', 0)} recommended</strong>"
    )

    head = (
        '<html><body style="font-family:-apple-system,Segoe UI,Arial,sans-serif;'
        'color:#1a1a1a;line-height:1.5;max-width:760px;">'
        f'<h2 style="margin-bottom:4px;">Job shortlist &mdash; {stamp}</h2>'
        f'<p style="color:#666;font-size:12px;margin-top:0;">{funnel}</p>'
    )

    if not final_jobs:
        body = (
            '<p style="padding:14px;background:#f6f6f6;border-radius:6px;">'
            "<strong>No sufficiently strong matches today.</strong><br>"
            "The pipeline ran normally &mdash; nothing cleared the quality bar, "
            "and the standard was not lowered to fill the list. "
            "The stage CSVs are attached to the GitHub Actions run if you want "
            "to see what came close.</p>"
        )
        return head + body + "</body></html>"

    cards = []
    for job in final_jobs:
        rank = job.get("final_rank_display") or job.get("final_rank") or "?"
        url = str(job.get("job_url_direct") or job.get("job_url") or "")
        is_direct = bool(job.get("job_url_direct"))
        title = escape(str(job.get("title") or "(no title)"))
        link = (f'<a href="{escape(url, quote=True)}" '
                f'style="color:#0b5fff;text-decoration:none;">{title}</a>'
                if url else title)

        meta_bits = [escape(str(job.get("company") or "-")),
                     escape(str(job.get("location") or "-")),
                     escape(str(job.get("source") or job.get("site") or "-"))]
        salary = _fmt_salary(job)
        if salary:
            meta_bits.insert(2, escape(salary))

        cards.append(
            '<div style="border:1px solid #e2e2e2;border-radius:8px;'
            'padding:12px 14px;margin-bottom:10px;">'
            '<div style="display:block;">'
            f'<span style="font-weight:700;color:#888;font-size:13px;">#{rank}</span> '
            f'<span style="font-weight:600;font-size:16px;">{link}</span>'
            f'<span style="float:right;font-weight:700;color:#0b5fff;'
            f'font-size:17px;">{job.get("final_score", "-")}</span></div>'
            f'<div style="color:#444;font-size:13px;">{" &middot; ".join(meta_bits)}</div>'
            f'<div style="color:#0a7d33;font-size:12px;margin-top:4px;">{_why(job)}</div>'
            + _scores_table(job)
            + _analysis_block(job)
            + (f'<div style="font-size:12px;margin-top:6px;">'
               f'<a href="{escape(url, quote=True)}">'
               f'{"Apply directly" if is_direct else "View posting"}</a></div>'
               if url else "")
            + '</div>'
        )

    foot = (
        '<p style="color:#888;font-size:11px;margin-top:16px;">'
        "Match score ranks how closely a posting resembles your profile. "
        "It is a ranking aid, not a probability of being hired. "
        "Tune weights in <code>config.py</code>.</p>"
    )
    return head + "".join(cards) + foot + "</body></html>"


def send_email(html: str, subject: str, attachments: list = None) -> None:
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

    for path in attachments or []:
        try:
            with open(path, "rb") as fh:
                msg.add_attachment(fh.read(), maintype=DOCX_MIME[0],
                                   subtype=DOCX_MIME[1],
                                   filename=os.path.basename(path))
        except OSError as exc:
            print(f"  could not attach {path}: {exc}", flush=True)

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT,
                      timeout=config.SMTP_TIMEOUT) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"Email sent to {to}", flush=True)


def subject_for(stats: dict) -> str:
    n = stats.get("selected", 0)
    day = datetime.now(MYT).strftime("%d %b")
    if not n:
        return f"Job shortlist: no strong matches ({day})"
    return f"Job shortlist: {n} recommended role{'' if n == 1 else 's'} ({day})"
