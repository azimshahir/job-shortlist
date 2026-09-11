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
REPORT_MD = "shortlist.md"
RESUME_DIR = "resumes"

# Columns preserved through the stage CSVs, where the data exists.
TRACE_COLUMNS = [
    "source", "title", "company", "location", "date_posted", "salary",
    "job_url", "job_url_direct",
    "keyword_score", "semantic_raw", "semantic_score", "final_score",
    "strongest_profile_match", "filter_status", "reject_reason",
    "career_family", "career_family_status", "career_family_score",
    "career_family_reason",
    "job_id", "first_seen", "last_seen", "seen_count",
    "shortlisted_before", "shortlist_count", "resume_generated",
    "applied", "applied_date", "ignored", "ignore_reason",
    "history_status", "history_reason",
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

# ---- FROZEN semantic display transform ----------------------------------
# semantic_raw (the raw cosine) is the source of truth and is preserved on
# every row. These two constants only rescale it to a readable 0-100.
#
# THEY ARE FROZEN ON PURPOSE. DO NOT REFIT THEM TO A DAILY BATCH.
#
# An earlier version fitted this band to each day's candidate pool. That was
# wrong: it made the score mean something different every morning. The same
# job could read 68 on a weak day and 51 on a strong one, purely because of
# what else happened to be scraped, so scores were not comparable across days
# and no fixed threshold could be trusted.
#
# Rescaling is monotonic, so it never changes rank ORDER -- it affects only
# readability and where fixed thresholds bite. The band below is wide enough
# to cover e5's usual range on this corpus without clamping.
#
# Legitimate recalibration needs a persistent LABELLED validation set (jobs
# the candidate has marked strong / acceptable / weak / reject), never the
# batch being ranked. See calibrate.py and validation_labels.csv.
SEMANTIC_TRANSFORM_FLOOR = 0.74
SEMANTIC_TRANSFORM_CEILING = 0.90

# Aliases so nothing importing the old names breaks.
SIMILARITY_FLOOR = SEMANTIC_TRANSFORM_FLOOR
SIMILARITY_CEILING = SEMANTIC_TRANSFORM_CEILING

# Automatic recalibration is OFF. calibrate.py refuses to fit against a daily
# batch and requires a labelled validation file.
ENABLE_AUTO_CALIBRATION = False
VALIDATION_LABELS_CSV = "validation_labels.csv"
VALIDATION_MIN_LABELLED = 30   # too few labels overfit worse than not fitting

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
# Checked against the TITLE ONLY -- unlike filters.HARD_REJECT, which scans
# the whole description and would wrongly drop a good job that merely says
# "reporting to the Senior Manager".
DISQUALIFYING_TITLE_TERMS = (
    # Entry level: a step backwards at 5 years' experience
    "intern", "internship", "trainee", "apprentice",
    "graduate programme", "graduate program", "fresh graduate",
    "undergraduate",
    # Too senior: not a realistic move from executive level
    # (multi-word only: a bare "coo" would match "Coordinator")
    "associate director", "senior manager", "general manager",
    "chief executive", "chief operating", "chief financial",
    "senior vice president", "assistant vice president",
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
# Output (Phase 8) -- Markdown report for chat; email was removed on request
# --------------------------------------------------------------------------
MYT_UTC_OFFSET_HOURS = 8

# --------------------------------------------------------------------------
# Playwright fallback (Phase 10) -- interface only, not implemented
# --------------------------------------------------------------------------
# Turning this on does nothing yet; see enrich.py for the seam.
ENABLE_PLAYWRIGHT_FALLBACK = False
# Only ever consider the fallback for jobs already shortlisted, never for the
# full raw scrape.
PLAYWRIGHT_MAX_PAGES = MAX_FINAL_SELECTION


# --------------------------------------------------------------------------
# Career-family gating (after semantic ranking, before final selection)
# --------------------------------------------------------------------------
# Semantic similarity answers "does this resemble the candidate's background".
# It does NOT answer "is this the candidate's career family". Compliance, IT
# support and fund operations share heavy vocabulary overlap -- controls,
# monitoring, operations, stakeholders -- so the embedding model rates them
# alike. That is the model working correctly; it is answering a different
# question. This stage settles the second question cheaply.
#
# descriptor  -> embedded once, compared against each job
# title_terms -> deterministic, checked against the job TITLE only
CAREER_FAMILIES = {
    # ---------------- CORE ----------------
    "fund_accounting_operations": {
        "status": "CORE",
        "descriptor": (
            "Fund accounting and fund administration operations. Daily fund "
            "valuation support, net asset value production inputs, pricing, "
            "unit trust fund servicing, transfer agency, and fund level "
            "records for collective investment schemes."
        ),
        "title_terms": ("fund accounting", "fund accountant", "fund operations",
                        "fund administration", "fund administrator",
                        "fund services", "transfer agency", "unit trust"),
    },
    "reconciliation": {
        "status": "CORE",
        "descriptor": (
            "Reconciliation of cash and securities positions between internal "
            "records, custodian statements and counterparty records. "
            "Investigating and clearing reconciliation breaks and ageing items."
        ),
        "title_terms": ("reconciliation", "reconciliations"),
    },
    "investment_operations_middle_office": {
        "status": "CORE",
        "descriptor": (
            "Investment operations and middle office for asset management. "
            "Trade capture verification, trade lifecycle monitoring, "
            "post-trade processing, custody and depositary control, trustee "
            "liaison and asset servicing."
        ),
        "title_terms": ("investment operations", "middle office",
                        "securities services", "securities operations",
                        "asset servicing", "depositary", "custody",
                        "custodian"),
    },
    "settlement_corporate_actions": {
        "status": "CORE",
        "descriptor": (
            "Trade settlement and corporate actions processing. Settlement "
            "instruction matching, failed trade follow up, clearing, and "
            "corporate action event processing for equities and fixed income."
        ),
        "title_terms": ("settlement", "settlements", "corporate actions",
                        "clearing"),
    },
    "treasury_alm_liquidity": {
        "status": "CORE",
        "descriptor": (
            "Treasury operations, asset and liability management and "
            "liquidity risk in a bank. Balance sheet and liquidity position "
            "analysis, ALCO reporting, fund transfer pricing, and regulatory "
            "liquidity submissions to the central bank."
        ),
        "title_terms": ("treasury", "asset liability", "asset-liability",
                        "alm", "liquidity", "alco", "balance sheet management"),
    },
    "financial_operations": {
        "status": "CORE",
        "descriptor": (
            "Financial and banking operations. Daily processing controls, "
            "exception handling, payment and cash operations, operational "
            "management information and service level monitoring."
        ),
        "title_terms": ("financial operations", "banking operations",
                        "operations analyst", "operations executive",
                        "payment operations", "cash operations"),
    },

    # ---------------- SECONDARY / STRATEGIC ----------------
    "finance_transformation": {
        "status": "SECONDARY",
        "descriptor": (
            "Finance transformation and change delivery. Business analysis "
            "for finance and operations, requirements gathering, user "
            "acceptance testing, target operating model work and change "
            "management across finance systems and processes."
        ),
        "title_terms": ("finance transformation", "business analyst",
                        "transformation", "change management",
                        "operations transformation"),
    },
    "finance_ai_automation": {
        "status": "SECONDARY",
        "descriptor": (
            "Automation and artificial intelligence applied to finance and "
            "operations. Robotic process automation, Power Automate, Power "
            "BI, Excel VBA automation, Microsoft Copilot adoption and prompt "
            "engineering for finance use cases."
        ),
        "title_terms": ("automation", "finance automation", "rpa",
                        "intelligent automation"),
    },
    "finance_process_improvement": {
        "status": "SECONDARY",
        "descriptor": (
            "Operational process improvement within finance. Reviewing "
            "finance and operations workflows to remove manual effort, "
            "improve controls and increase efficiency, including continuous "
            "improvement and operational excellence programmes."
        ),
        "title_terms": ("process improvement", "continuous improvement",
                        "operational excellence", "process excellence"),
    },

    # ---------------- ADJACENT ----------------
    "banking_operations_adjacent": {
        "status": "ADJACENT",
        "descriptor": (
            "Broader banking operations with transferable relevance: loan "
            "operations, trade finance operations, wholesale banking "
            "operations, client servicing for institutional banking, and "
            "operational risk or governance support within a bank."
        ),
        "title_terms": ("trade finance", "loan operations", "wholesale banking",
                        "operational risk", "enterprise risk",
                        "risk governance"),
    },

    # ---------------- OUT OF SCOPE ----------------
    "compliance_aml_fcc": {
        "status": "OUT_OF_SCOPE",
        "descriptor": (
            "Regulatory compliance, anti money laundering, financial crime "
            "compliance, sanctions screening, know your customer, suspicious "
            "transaction reporting, fraud investigation and compliance "
            "monitoring and testing."
        ),
        "title_terms": ("compliance", "aml", "anti money laundering",
                        "financial crime", "fcc", "kyc", "sanctions",
                        "fraud", "audit", "internal audit"),
    },
    "it_systems_support": {
        "status": "OUT_OF_SCOPE",
        "descriptor": (
            "Information technology roles: systems support, application "
            "support, technical support, infrastructure, software "
            "engineering, development, DevOps, cloud operations, service "
            "desk and IT helpdesk."
        ),
        "title_terms": ("systems support", "system support",
                        "application support", "technical support",
                        "it support", "helpdesk", "service desk",
                        "software", "developer", "engineer",
                        "technical consultant", "technical specialist",
                        "jira", "infrastructure", "administrator"),
    },
    "sales_marketing_retail": {
        "status": "OUT_OF_SCOPE",
        "descriptor": (
            "Sales, business development, account management, marketing, "
            "brand, campaigns, merchandising, retail store operations, "
            "customer acquisition and channel productivity."
        ),
        "title_terms": ("sales", "business development", "marketing", "brand",
                        "retail", "merchandising", "account manager",
                        "channel productivity", "store", "outlet",
                        "telemarketing", "relationship manager"),
    },
    "supply_chain_warehouse": {
        "status": "OUT_OF_SCOPE",
        "descriptor": (
            "Warehouse, fulfilment, logistics, inventory, stock control, "
            "shipping, last mile delivery, procurement, sourcing and supply "
            "chain operations."
        ),
        "title_terms": ("warehouse", "fulfilment", "fulfillment", "logistics",
                        "inventory", "supply chain", "procurement",
                        "sourcing", "shipping", "delivery"),
    },
    "insurance_servicing": {
        "status": "OUT_OF_SCOPE",
        "descriptor": (
            "Insurance policy servicing and administration unrelated to "
            "investment operations: policy changes, claims handling, "
            "underwriting support, policyholder servicing, conservation and "
            "actuarial support."
        ),
        "title_terms": ("policy servicing", "policy administration", "claims",
                        "underwriting", "actuarial", "policyholder",
                        "insurance operations", "policy member"),
    },
    "generic_data_roles": {
        "status": "OUT_OF_SCOPE",
        "descriptor": (
            "General data and analytics roles with no meaningful finance "
            "operations connection: data production, data entry, data "
            "engineering, market research data, business intelligence "
            "development and general reporting analytics."
        ),
        "title_terms": ("data production", "data entry", "data engineer",
                        "data analytics", "business intelligence",
                        "bi developer", "data steward"),
    },
}

# A nominally out-of-scope title is rescued when the TITLE also carries one of
# these, e.g. "Fund Services Compliance Officer" is genuinely in-domain.
CAREER_RESCUE_TERMS = (
    "fund", "funds", "investment", "settlement", "reconciliation",
    "custody", "custodian", "depositary", "treasury", "middle office",
    "asset servicing", "transfer agency", "unit trust",
)

# Below this cosine the family assignment is reported as UNKNOWN, not guessed.
CAREER_MIN_SIMILARITY = 0.78

# Whether UNKNOWN-family jobs may reach final_jobs.csv. False is the
# conservative default: an unclassifiable job is not worth a slot.
CAREER_ALLOW_UNKNOWN = False

# Escape hatch: exact job_url values listed here bypass career gating.
CAREER_FAMILY_OVERRIDES = ()

# --------------------------------------------------------------------------
# Cross-run job history (persistent, survives between runs)
# --------------------------------------------------------------------------
# Storage is behind an interface (history.py) so execution can move from
# GitHub Actions to a VPS without touching pipeline logic.
HISTORY_BACKEND = "sqlite"        # "sqlite" | "memory"
HISTORY_DB_PATH = "job_history.db"

# A job already shortlisted is not re-shown every morning. After this many
# days it becomes eligible again -- postings do get genuinely refreshed.
SHORTLIST_COOLDOWN_DAYS = 14

# A repost is the same company + title + location under a different URL.
# Within this window it is treated as the same job, not a new one.
REPOST_COOLDOWN_DAYS = 14

# Jobs marked applied are never actionable again, but are never deleted.
EXCLUDE_APPLIED = True
EXCLUDE_IGNORED = True
