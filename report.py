"""
Chat-friendly report. Replaces the email.

Renders the run as Markdown so it reads cleanly when pasted into a chat and
is also saved to shortlist.md for the record.
"""

from datetime import datetime, timedelta, timezone

import config

MYT = timezone(timedelta(hours=config.MYT_UTC_OFFSET_HOURS))


def _url(job: dict) -> str:
    for key in ("job_url_direct", "job_url"):
        val = job.get(key)
        if val and str(val).strip().lower() not in ("nan", "none", ""):
            return str(val)
    return ""


def _link(job: dict, limit: int = 60) -> str:
    title = str(job.get("title") or "(no title)").replace("|", "/")[:limit]
    url = _url(job)
    return f"[{title}]({url})" if url else title


def _family(job: dict) -> str:
    fam = str(job.get("career_family") or "-").replace("_", " ")
    status = str(job.get("career_family_status") or "-")
    short = {"OUT_OF_SCOPE": "OUT", "SECONDARY": "SEC", "ADJACENT": "ADJ"}.get(status, status)
    return f"{fam} ({short})"


def _reason(job: dict) -> str:
    status = str(job.get("selection_status") or "")
    reason = str(job.get("selection_reason") or "")
    if status == "out_of_scope":
        return "out of scope"
    if status == "disqualified":
        # "level mismatch: title contains 'intern', ..." -> "intern"
        if "contains '" in reason:
            return reason.split("contains '")[1].split("'")[0]
        return "level mismatch"
    if status.startswith("history_"):
        return status.replace("history_", "").replace("_", " ")
    if status == "not_selected":
        if "below threshold" in reason:
            return f"bawah {config.FINAL_SCORE_THRESHOLD:.0f}"
        return "luar top 5"
    return status or "-"


def _loc(job: dict) -> str:
    loc = str(job.get("location") or "-")
    for noise in (", Malaysia", "Federal Territory of ", "WP. ", ", MY"):
        loc = loc.replace(noise, "")
    return loc.strip(", ")[:28]


def funnel_line(stats: dict) -> str:
    return (f"{stats.get('raw', 0)} scraped → {stats.get('hard_rejected', 0)} hard-reject → "
            f"{stats.get('keyword_passed', 0)} lepas keyword → {stats.get('ranked', 0)} ranked → "
            f"{stats.get('career_rejected', 0)} out-of-scope → "
            f"{stats.get('history_excluded', 0)} pernah nampak → "
            f"**{stats.get('selected', 0)} disyorkan**")


def build_markdown(selected: list, others: list, stats: dict) -> str:
    stamp = datetime.now(MYT).strftime("%d %b %Y, %H:%M")
    out = [f"## Job shortlist — {stamp}", "", funnel_line(stats), ""]

    if selected:
        out += ["### Disyorkan", "",
                "| # | Job | Company | Lokasi | Source | Family | KW | Sem | Final |",
                "|---|---|---|---|---|---|---|---|---|"]
        for j in selected:
            out.append(
                f"| {j.get('final_rank_display') or j.get('final_rank')} | {_link(j)} | "
                f"{str(j.get('company') or '-')[:24]} | {_loc(j)} | "
                f"{j.get('source') or j.get('site') or '-'} | {_family(j)} | "
                f"{j.get('keyword_score', '-')} | {j.get('semantic_raw', '-')} | "
                f"**{j.get('final_score', '-')}** |")
        out.append("")
    else:
        out += ["**Tiada job cukup kuat hari ini.** Standard tidak diturunkan "
                "untuk penuhkan senarai.", ""]

    if others:
        out += [f"### Ranked, tak disyorkan ({len(others)})", "",
                "| # | Job | Company | Source | Family | Final | Sebab |",
                "|---|---|---|---|---|---|---|"]
        for j in others:
            out.append(
                f"| {j.get('final_rank')} | {_link(j, 48)} | "
                f"{str(j.get('company') or '-')[:22]} | "
                f"{j.get('source') or j.get('site') or '-'} | {_family(j)} | "
                f"{j.get('final_score', '-')} | {_reason(j)} |")
        out.append("")

    out += ["_Semantic = raw cosine ke profil; ranking aid, bukan kebarangkalian "
            "dapat kerja. Tune di `config.py`._"]
    return "\n".join(out)


def write_report(markdown: str, path: str = None) -> str:
    path = path or config.REPORT_MD
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(markdown + "\n")
    return path
