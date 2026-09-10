"""
Every tunable number for the pipeline lives here. Nothing else should
hardcode a threshold or a weight.

Pipeline:
    JobSpy -> dedupe -> hard reject -> keyword pre-filter
           -> local embedding semantic rank -> combined final rank
           -> top N -> (optional) strong LLM -> tailored DOCX -> email
"""

import os

# --------------------------------------------------------------------------
# Scraping (Phase 1) -- unchanged behaviour from the original scraper
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

# --------------------------------------------------------------------------
# Stage outputs (Phase 5 -- traceability). Each stage writes its own file and
# never overwrites an earlier one.
# --------------------------------------------------------------------------
RAW_CSV = "raw_jobs.csv"
FILTERED_CSV = "filtered_jobs.csv"
RANKED_CSV = "ranked_jobs.csv"
FINAL_CSV = "final_jobs.csv"
RESUME_DIR = "resumes"

# Columns preserved through the stage CSVs, where the data exists.
TRACE_COLUMNS = [
    "source", "title", "company", "location", "date_posted", "salary",
    "job_url", "job_url_direct",
    "keyword_score", "semantic_score", "final_score",
    "strongest_profile_match", "filter_status", "reject_reason",
    "selection_status", "selection_reason", "description_status",
]

# --------------------------------------------------------------------------
# Semantic matching (Phase 3)
# --------------------------------------------------------------------------
# Runs locally via sentence-transformers. No hosted inference, no LLM.
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

# e5 models are trained with these prefixes and score noticeably worse without.
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "

CANDIDATE_PROFILE_PATH = "candidate_profile.yaml"

# Only this much of a JD is embedded. The model truncates at 512 tokens anyway;
# cutting early keeps encoding fast and drops boilerplate footers.
MAX_JD_CHARS = 2000

EMBED_BATCH_SIZE = 32

# A job's semantic score aggregates its similarity to each profile SECTION,
# not to one giant blob. Top-k mean: rewards a job that matches a few sections
# strongly, without demanding it match all of them.
SEMANTIC_TOP_K_SECTIONS = 3

# Raw cosine similarity for e5 clusters in a VERY narrow band, so it is
# rescaled onto 0-100 for readability. This is a RANKING score, not a
# probability of getting hired -- see README.
#
# Calibrated against the real 952-row scrape: across the jobs that clear the
# keyword pre-filter, cosine ran 0.806 (min) to 0.850 (max), median 0.832.
# The original 0.70-0.92 band used only 20% of its range and squashed every
# job into a 48-68 score, which destroyed the ranking's ability to separate
# a genuinely strong match from a mediocre one.
# Recheck these with: python calibrate.py
SIMILARITY_FLOOR = 0.80
SIMILARITY_CEILING = 0.86

# --------------------------------------------------------------------------
# Combined final ranking (Phase 4)
# --------------------------------------------------------------------------
# Weights are applied to components already normalised to 0-100, then summed.
# They should total 1.0.
#
# Chosen after inspecting the real 952-row scrape:
#   - semantic dominates deliberately, so a single keyword like
#     "reconciliation" can no longer float a warehouse role to the top.
#   - keyword is kept as a real but minority signal; it encodes domain
#     vocabulary the embedding model has no reason to prioritise.
#   - recency is weighted low because only Indeed supplies date_posted
#     (232 of 952 rows); LinkedIn rows have none and score neutral.
#   - salary is 0.0 because JobSpy returned salary for 0 of 952 rows in the
#     Malaysian market. The component is implemented and ready -- raise the
#     weight if that ever changes.
WEIGHTS = {
    "semantic": 0.65,
    "keyword": 0.20,
    "seniority": 0.08,
    "location": 0.05,
    "recency": 0.02,
    "salary": 0.00,
}

# Neutral score for a component whose data is missing, so absent data neither
# rewards nor punishes a job.
NEUTRAL_COMPONENT_SCORE = 50.0

# Keyword scores are converted to 0-100 by treating this as the practical top.
KEYWORD_SCORE_CEILING = 30.0

# Phase 4 shortlist sizes.
TOP_N_RANKED = 10          # how many go into the ranked shortlist
MAX_FINAL_SELECTION = 5    # never send more than this to the strong LLM
MIN_FINAL_SELECTION = 0    # never pad the list to hit a quota

# Titles that disqualify a job from FINAL SELECTION regardless of score.
# These are entry-level roles: a 5-year professional applying to an internship
# is a step backwards, and they score deceptively well semantically because the
# JD describes exactly the right work. Handled here rather than as a keyword
# hard-reject so they still appear in ranked_jobs.csv with a visible reason.
DISQUALIFYING_TITLE_TERMS = (
    "intern", "internship", "trainee", "apprentice",
    "graduate programme", "graduate program", "fresh graduate",
    "undergraduate",
)

# A job must clear this combined score to be worth expensive analysis.
# Better to email 2 strong jobs than 5 mediocre ones.
FINAL_SCORE_THRESHOLD = 60.0

# --------------------------------------------------------------------------
# Seniority fit (Phase 4 component)
# --------------------------------------------------------------------------
# ~5 years of experience. Hard seniority rejects still live in filters.py;
# this is the softer preference signal.
CANDIDATE_YEARS_EXPERIENCE = 5
SENIORITY_PREFERRED = ("executive", "senior executive", "analyst",
                       "senior analyst", "assistant manager", "specialist",
                       "senior officer", "associate")
SENIORITY_STRETCH = ("manager", "lead", "supervisor", "officer")

# --------------------------------------------------------------------------
# Location fit (Phase 4 component)
# --------------------------------------------------------------------------
PREFERRED_LOCATIONS = ("kuala lumpur", "selangor", "petaling jaya",
                       "cyberjaya", "shah alam", "subang", "puchong",
                       "damansara", "klang", "putrajaya", "bangsar")
REMOTE_TERMS = ("remote", "work from home", "hybrid")

# --------------------------------------------------------------------------
# Strong LLM (Phase 6) -- interface only unless configured
# --------------------------------------------------------------------------
# Provider is chosen by env var so the scraper never needs editing to switch.
# Supported: "none" (default), "anthropic", "openai".
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "none").strip().lower()
LLM_MODEL = os.environ.get("LLM_MODEL", "").strip()

# Sensible defaults per provider when LLM_MODEL is not set.
LLM_DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    "openai": "gpt-4o",
}

LLM_MAX_TOKENS = 4000
LLM_TIMEOUT_SECONDS = 120

# Hard ceiling. Even a misconfiguration must not fan out to hundreds of calls.
LLM_MAX_CALLS_PER_RUN = MAX_FINAL_SELECTION

# --------------------------------------------------------------------------
# Resume generation (Phase 7)
# --------------------------------------------------------------------------
RESUME_CANDIDATE_NAME = "Azim Shahir"
RESUME_FONT = "Calibri"
RESUME_BODY_PT = 10
RESUME_HEADING_PT = 12
RESUME_NAME_PT = 16
RESUME_MAX_PAGES = 2

# --------------------------------------------------------------------------
# Email (Phase 8)
# --------------------------------------------------------------------------
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_TIMEOUT = 60
MYT_UTC_OFFSET_HOURS = 8

# --------------------------------------------------------------------------
# Playwright fallback (Phase 10) -- interface only, not implemented
# --------------------------------------------------------------------------
# Turning this on does nothing yet; see enrich.py for the seam.
ENABLE_PLAYWRIGHT_FALLBACK = False
# Only ever consider the fallback for jobs already shortlisted, never for the
# full raw scrape.
PLAYWRIGHT_MAX_PAGES = MAX_FINAL_SELECTION
