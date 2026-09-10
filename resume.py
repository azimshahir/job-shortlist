"""
Phase 7 -- tailored ATS-friendly DOCX generation.

A separate, callable stage. It takes the strong LLM's structured output and
renders it; it does not itself call any LLM.

Connecting it later:
    1. Fill in the TODO_ placeholders in candidate_profile.yaml.
    2. Set LLM_PROVIDER + the API key (see llm.py).
    3. pipeline.py already calls llm.analyse_jobs() then this module -- when a
       provider is configured, resumes start generating with no code change.

ATS-friendliness here means: single column, no tables, no text boxes, no
headers/footers, no images, black Calibri, real bullet paragraphs, standard
section headings. Nothing an ATS parser chokes on.
"""

import os
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

import config

_SAFE_RE = re.compile(r"[^A-Za-z0-9]+")


def safe_filename(company: str, role: str, name: str = None) -> str:
    """Azim_Shahir_<Company>_<Role>.docx, safe on every filesystem."""
    name = name or config.RESUME_CANDIDATE_NAME

    def slug(value, limit):
        value = _SAFE_RE.sub("_", str(value or "")).strip("_")
        return value[:limit].strip("_") or "Unknown"

    stem = f"{slug(name, 40)}_{slug(company, 40)}_{slug(role, 60)}"
    return f"{stem}.docx"[:180]


def _style_document(doc):
    style = doc.styles["Normal"]
    style.font.name = config.RESUME_FONT
    style.font.size = Pt(config.RESUME_BODY_PT)
    style.font.color.rgb = RGBColor(0, 0, 0)
    fmt = style.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(2)

    for section in doc.sections:
        section.top_margin = section.bottom_margin = Pt(36)
        section.left_margin = section.right_margin = Pt(40)


def _para(doc, text, size=None, bold=False, space_before=0, space_after=2,
          style=None):
    p = doc.add_paragraph(style=style)
    run = p.add_run(str(text))
    run.bold = bold
    run.font.name = config.RESUME_FONT
    run.font.size = Pt(size or config.RESUME_BODY_PT)
    run.font.color.rgb = RGBColor(0, 0, 0)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    return p


def _heading(doc, text):
    p = _para(doc, text.upper(), size=config.RESUME_HEADING_PT, bold=True,
              space_before=8, space_after=3)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    return p


def build_resume(analysis: dict, job: dict, candidate_profile: dict,
                 out_path: str) -> str:
    """
    Render one tailored resume.

    `analysis` is the strong LLM's structured output (see llm.RESPONSE_SCHEMA).
    Falls back to the untailored profile for any section the LLM omitted, so a
    partial response still produces a usable document.
    """
    analysis = analysis or {}
    meta = candidate_profile.get("meta", {})

    doc = Document()
    _style_document(doc)

    # --- Header: name and contact. No photo, no text boxes. ---
    _para(doc, meta.get("name") or config.RESUME_CANDIDATE_NAME,
          size=config.RESUME_NAME_PT, bold=True, space_after=1)
    contact = " | ".join(
        str(v) for v in (meta.get("location_preference"),
                         meta.get("email"), meta.get("phone"),
                         meta.get("linkedin"))
        if v and not str(v).startswith("TODO_")
    )
    if contact:
        _para(doc, contact, space_after=4)

    # --- Professional summary ---
    summary = analysis.get("tailored_summary")
    if summary:
        _heading(doc, "Professional Summary")
        _para(doc, summary)

    # --- Skills ---
    skills = analysis.get("tailored_skills") or []
    if not skills:
        tools = candidate_profile.get("tools", {}) or {}
        skills = list(tools.get("confident") or [])
    if skills:
        _heading(doc, "Key Skills")
        _para(doc, " | ".join(str(s) for s in skills))

    # --- Experience: latest first unless the LLM reordered for relevance ---
    roles = analysis.get("tailored_bullets") or []
    if not roles:
        roles = [
            {"employer": r.get("employer"), "title": r.get("title"),
             "dates": r.get("dates"), "bullets": r.get("bullets") or []}
            for r in (candidate_profile.get("experience") or [])
        ]
    if roles:
        _heading(doc, "Professional Experience")
        for role in roles:
            header = " — ".join(
                str(v) for v in (role.get("title"), role.get("employer"))
                if v and not str(v).startswith("TODO_")
            )
            if header:
                _para(doc, header, bold=True, space_before=5, space_after=0)
            dates = role.get("dates")
            if dates and not str(dates).startswith("TODO_"):
                _para(doc, dates, space_after=2)
            for bullet in role.get("bullets") or []:
                if str(bullet).startswith("TODO_"):
                    continue
                _para(doc, bullet, style="List Bullet", space_after=1)

    # --- Education ---
    education = [e for e in (candidate_profile.get("education") or [])
                 if not str(e.get("qualification", "")).startswith("TODO_")]
    if education:
        _heading(doc, "Education")
        for edu in education:
            line = " — ".join(str(v) for v in (edu.get("qualification"),
                                               edu.get("institution"),
                                               edu.get("year")) if v)
            _para(doc, line)

    # --- Certifications. The Copilot facilitator role must always appear. ---
    certs = list(candidate_profile.get("certifications") or [])
    copilot = "Microsoft Copilot Training Facilitator"
    if not any(copilot.lower() in str(c).lower() for c in certs):
        certs.append(copilot)
    _heading(doc, "Certifications & Training")
    for cert in certs:
        _para(doc, cert, style="List Bullet", space_after=1)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    doc.save(out_path)
    return out_path


def generate_resumes(analysed: list, candidate_profile: dict,
                     out_dir: str = None) -> list:
    """
    Build one resume per successfully analysed job.

    Jobs with status != "ok" are skipped -- without LLM output there is nothing
    to tailor, and generating a generic resume would be worse than none.
    Returns [{job, path, status, error}, ...].
    """
    out_dir = out_dir or config.RESUME_DIR
    results = []

    for item in analysed:
        job = item.get("job", {})
        if item.get("status") != "ok" or not item.get("analysis"):
            results.append({"job": job, "path": None, "status": "skipped",
                            "error": item.get("error") or "no LLM analysis"})
            continue
        try:
            path = os.path.join(
                out_dir,
                safe_filename(job.get("company"), job.get("title")),
            )
            build_resume(item["analysis"], job, candidate_profile, path)
            results.append({"job": job, "path": path, "status": "ok",
                            "error": None})
        except Exception as exc:  # noqa: BLE001
            results.append({"job": job, "path": None, "status": "error",
                            "error": f"{type(exc).__name__}: {exc}"})
    return results
