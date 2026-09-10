"""
Keyword rules for the daily job shortlist.

Two stages, in this order:

1. HARD_REJECT  - if any pattern matches, the job is dropped immediately,
                  no matter how good the rest of it looks.
2. BOOST        - every pattern that matches adds its weight. The total is
                  the job's score. Only jobs scoring >= MIN_SCORE survive.

To tune: change MIN_SCORE, or edit the weights / add lines to either dict.
Everything is matched case-insensitively against title + company + description.
"""

import re

# Raise this to get a shorter, stricter list. Lower it to see more.
MIN_SCORE = 6


# --------------------------------------------------------------------------
# BOOST KEYWORDS -- what you are actually good at.
# weight 4 = core strength, 3 = strong adjacent, 2 = supporting, 1 = nice bonus
# --------------------------------------------------------------------------
BOOST_KEYWORDS = {
    # Fund operations / securities ops -- the bullseye
    "fund administration": 4,
    "fund accounting": 4,
    "fund operations": 4,
    "transfer agency": 4,
    "investment operations": 4,
    "corporate actions": 4,
    "trade lifecycle": 4,
    "settlement": 4,
    "reconciliation": 4,
    "custody": 3,
    "unit trust": 3,
    "custodian": 3,

    # Treasury / ALM
    "treasury operations": 4,
    "asset liability": 4,
    "asset-liability": 4,
    "fund transfer pricing": 4,
    "alco": 4,
    "liquidity": 3,
    "cash management": 3,

    # Risk / governance / regulatory
    "enterprise risk": 4,
    "regulatory reporting": 4,
    "bank negara": 3,
    "bnm": 3,
    "governance": 2,
    "secretariat": 2,
    "operational risk": 2,
    "risk management": 1,

    # Transformation / BA skillset
    "business analyst": 4,
    "process improvement": 3,
    "requirements gathering": 3,
    "automation": 3,
    "power automate": 3,
    "power bi": 3,
    "uat": 3,
    "change management": 2,
    "vba": 2,
    "user acceptance testing": 3,

    # AI tooling
    "prompt engineering": 3,
    "copilot": 2,
    "ai tools": 2,

    # Islamic finance
    "islamic finance": 3,
    "shariah": 3,
    "syariah": 3,
}


# --------------------------------------------------------------------------
# HARD REJECTS -- one match and the job is gone.
# Grouped only for readability; every group behaves the same way.
# --------------------------------------------------------------------------
HARD_REJECT = {
    # Record-to-report / general ledger
    "journal entries", "journal entry", "month-end close", "month end close",
    "general ledger", "full set of accounts", "full sets of accounts",
    "statutory reporting", "statutory accounts", "consolidation",
    "ifrs", "us gaap", "mfrs",

    # Tax
    "corporate tax", "withholding tax", "sst", "cbcr", "tax compliance",

    # FP&A
    "budgeting and forecasting", "variance analysis", "financial modelling",
    "financial modeling", "fp&a", "fpna", "financial planning and analysis",

    # AP / AR
    "accounts payable", "accounts receivable", "bookkeeping",
    "invoice processing", "billing clerk",

    # ERP
    "sap", "oracle fusion", "oracle erp", "dynamics 365", "netsuite",
    "peoplesoft",

    # Qualifications you don't hold
    "acca qualified", "cpa qualified", "chartered accountant",
    "qualified accountant",

    # Wrong domain
    "procurement", "supply chain", "sourcing", "actuarial", "actuary",
    "underwriting", "disaster recovery", "cloud operations", "devops",
    "software engineer", "full stack", "fullstack",
    "business development executive", "cmsrl",

    # Seniority mismatch
    "head of", "director of", "vice president",
}

# Rejects that need real regex (punctuation, or an exception carved out).
HARD_REJECT_PATTERNS = {
    # "transfer pricing" is a tax function and a reject -- BUT
    # "fund transfer pricing" is treasury/ALM and is one of your strengths,
    # so only reject it when "fund" is not in front of it.
    r"(?<!fund )transfer pricing",

    # Seniority: 8+ years and above. "5+ years" / "6+" / "7+" stay allowed.
    r"\b(?:[89]|[1-9]\d)\s*\+?\s*(?:years|yrs)",
    r"\b(?:eight|nine|ten)\s*\+?\s*(?:years|yrs)",

    # Language: only reject when Mandarin is genuinely mandatory.
    # Bare "mandarin" / "cantonese" (usually "is an advantage") is NOT a reject.
    r"mandarin\s*(?:speaker\s*)?(?:is\s+)?(?:a\s+)?(?:must|required|mandatory|compulsory)",
    r"(?:must|required|mandatory)\s+(?:to\s+)?(?:speak|be\s+fluent\s+in)\s+mandarin",
    r"fluent\s+in\s+mandarin",
    r"proficien\w*\s+in\s+mandarin\s+is\s+(?:a\s+)?(?:must|required)",
}


# --------------------------------------------------------------------------
# ALIAS GROUPS -- spellings of the SAME idea. A job that mentions both
# "UAT" and "user acceptance testing" should score once, not twice, so each
# group contributes only its highest-weighted member.
# --------------------------------------------------------------------------
ALIAS_GROUPS = [
    {"uat", "user acceptance testing"},
    {"asset liability", "asset-liability"},
    {"shariah", "syariah"},
    {"bank negara", "bnm"},
    {"custody", "custodian"},
]

_ALIAS_OF = {}
for _i, _grp in enumerate(ALIAS_GROUPS):
    for _kw in _grp:
        _ALIAS_OF[_kw] = _i


def _phrase_regex(phrase: str) -> str:
    """Word-boundary regex for a literal phrase, tolerant of extra spacing."""
    parts = [re.escape(p) for p in phrase.split()]
    body = r"\s+".join(parts)
    lead = r"(?<![a-z0-9])"
    trail = r"(?![a-z0-9])"
    return lead + body + trail


_BOOST_RE = {kw: re.compile(_phrase_regex(kw), re.I) for kw in BOOST_KEYWORDS}
_REJECT_RE = {kw: re.compile(_phrase_regex(kw), re.I) for kw in HARD_REJECT}
_REJECT_PAT_RE = {p: re.compile(p, re.I) for p in HARD_REJECT_PATTERNS}


def build_haystack(job: dict) -> str:
    """Flatten the fields we search into one lowercase blob."""
    fields = [
        job.get("title") or "",
        job.get("company") or "",
        job.get("description") or "",
    ]
    return " ".join(str(f) for f in fields).lower()


def find_rejects(text: str) -> list:
    """Return every reject reason found (empty list = job is clean)."""
    hits = []
    for kw, rx in _REJECT_RE.items():
        if rx.search(text):
            hits.append(kw)
    for pat, rx in _REJECT_PAT_RE.items():
        m = rx.search(text)
        if m:
            hits.append(m.group(0).strip())
    return sorted(set(hits))


def score_job(job: dict) -> dict:
    """
    Evaluate one job.

    Returns {"keep": bool, "score": int, "matched": [...], "rejected_by": [...]}
    Hard reject short-circuits: no score is computed at all.
    """
    text = build_haystack(job)

    rejects = find_rejects(text)
    if rejects:
        return {"keep": False, "score": 0, "matched": [],
                "rejected_by": rejects, "reason": "hard reject"}

    hits = [(kw, w) for kw, w in BOOST_KEYWORDS.items()
            if _BOOST_RE[kw].search(text)]

    # Collapse alias groups down to their single best-scoring member.
    best_in_group = {}
    matched = []
    for kw, weight in hits:
        gid = _ALIAS_OF.get(kw)
        if gid is None:
            matched.append((kw, weight))
            continue
        if gid not in best_in_group or weight > best_in_group[gid][1]:
            best_in_group[gid] = (kw, weight)
    matched.extend(best_in_group.values())

    score = sum(w for _, w in matched)
    matched.sort(key=lambda kv: (-kv[1], kv[0]))
    keep = score >= MIN_SCORE
    return {
        "keep": keep,
        "score": score,
        "matched": [k for k, _ in matched],
        "rejected_by": [],
        "reason": "ok" if keep else f"score {score} < MIN_SCORE {MIN_SCORE}",
    }
