"""
Sanity check for the filter rules. No test framework needed:

    python test_filters.py

Each case says what SHOULD happen. Any line printed as FAIL means a rule
needs tuning in filters.py.
"""

from filters import MIN_SCORE, score_job

CASES = [
    # ---------------- should PASS ----------------
    ("PASS", {
        "title": "Fund Operations Analyst",
        "company": "Global Custody Bank",
        "description": ("Daily reconciliation of fund positions, trade settlement "
                        "and corporate actions processing. Support fund "
                        "administration and transfer agency teams. 3-5 years "
                        "experience in investment operations."),
    }),
    ("PASS", {
        "title": "Treasury Operations Executive",
        "company": "Malaysian Bank",
        "description": ("Support ALCO reporting, asset liability management and "
                        "fund transfer pricing. Liaise with Bank Negara on "
                        "regulatory reporting and liquidity submissions."),
    }),
    ("PASS", {
        "title": "Business Analyst - Operations Transformation",
        "company": "Regional Bank",
        "description": ("Requirements gathering, UAT coordination and process "
                        "improvement across settlement and reconciliation "
                        "workflows. Power BI and Power Automate experience "
                        "preferred. Mandarin is an advantage."),
    }),
    ("PASS", {
        "title": "Shariah Governance Officer",
        "company": "Islamic Bank Berhad",
        "description": ("Support the Shariah secretariat and enterprise risk "
                        "governance framework. Islamic finance background with "
                        "regulatory reporting exposure to BNM."),
    }),

    # ---------------- should REJECT ----------------
    ("REJECT", {
        "title": "Senior Finance Executive",
        "company": "Manufacturing Sdn Bhd",
        "description": ("Handle full set of accounts, month-end close, journal "
                        "entries and general ledger reconciliation. MFRS "
                        "reporting and consolidation."),
    }),
    ("REJECT", {
        "title": "Transfer Pricing Consultant",
        "company": "Big Four",
        "description": "Corporate tax and transfer pricing documentation, CbCR filings.",
    }),
    ("REJECT", {
        "title": "FP&A Analyst",
        "company": "Retail Group",
        "description": ("Budgeting and forecasting, variance analysis and "
                        "financial modelling for the regional business."),
    }),
    ("REJECT", {
        "title": "Fund Accountant",
        "company": "Fund House",
        "description": ("Fund accounting and reconciliation duties. Must be ACCA "
                        "qualified chartered accountant with SAP experience."),
    }),
    ("REJECT", {
        "title": "Operations Manager",
        "company": "Logistics Co",
        "description": "Procurement and supply chain sourcing across the region.",
    }),
    ("REJECT", {
        "title": "Head of Fund Services",
        "company": "Custodian Bank",
        "description": ("Lead fund administration, custody and settlement. "
                        "12+ years of experience required."),
    }),
    ("REJECT", {
        "title": "Client Services Officer - Unit Trust",
        "company": "Asset Manager",
        "description": ("Transfer agency and unit trust servicing. Fluent in "
                        "Mandarin is a must for this role."),
    }),

    # ---------------- clean, but too thin to shortlist ----------------
    ("LOWSCORE", {
        "title": "Admin Assistant",
        "company": "Small Firm",
        "description": "General office administration and filing. Governance support.",
    }),
]


def main() -> int:
    failures = 0
    print(f"MIN_SCORE = {MIN_SCORE}\n")

    for expected, job in CASES:
        v = score_job(job)
        if v["rejected_by"]:
            actual = "REJECT"
            detail = "hard reject on: " + ", ".join(v["rejected_by"])
        elif v["keep"]:
            actual = "PASS"
            detail = f"score {v['score']} | matched: " + ", ".join(v["matched"])
        else:
            actual = "LOWSCORE"
            detail = f"score {v['score']} < {MIN_SCORE}"

        ok = actual == expected
        failures += 0 if ok else 1
        mark = "OK  " if ok else "FAIL"
        print(f"{mark} [{actual:<8}] {job['title']}")
        print(f"       {detail}\n")

    print("-" * 60)
    if failures:
        print(f"{failures} case(s) did not behave as expected.")
    else:
        print(f"All {len(CASES)} cases behaved as expected.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
