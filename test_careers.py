"""
Career-family gating tests.

    python test_careers.py

Loads the real local embedding model for the cases the rules defer on.
No strong LLM is involved at any point.
"""

import sys

import careers
import config
import ranking

_results = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    _results.append((status, name, detail))
    print(f"{status:<4} {name}" + (f"\n       {detail}" if detail else ""))
    return condition


JOBS = {
    "reconciliation": {
        "title": "Reconciliation Analyst",
        "company": "Krypton Fund Services",
        "description": ("Daily cash and stock reconciliation for hedge fund "
                        "clients. Investigate and clear breaks against "
                        "custodian and prime broker records."),
        "expect_status": careers.CORE,
    },
    "middle_office": {
        "title": "Assistant Manager, Middle Office, Investment Management",
        "company": "CACEIS",
        "description": ("Trade capture, settlement monitoring and corporate "
                        "actions for investment management clients. Liaise "
                        "with custodians and depositary teams."),
        "expect_status": careers.CORE,
    },
    "treasury": {
        "title": "Treasury Operations Executive, ALM",
        "company": "Malaysian Bank",
        "description": ("Support ALCO reporting, asset liability management "
                        "and fund transfer pricing. Liquidity risk metrics "
                        "and Bank Negara submissions."),
        "expect_status": careers.CORE,
    },
    "settlement": {
        "title": "Settlement Operations Executive",
        "company": "Regional Bank",
        "description": ("Trade settlement instruction matching, failed trade "
                        "follow up and corporate actions processing."),
        "expect_status": careers.CORE,
    },
    "finance_ai": {
        "title": "Finance Automation Specialist",
        "company": "Shared Services Centre",
        "description": ("Build Power Automate and Power BI automations for "
                        "finance operations. Drive Microsoft Copilot adoption "
                        "and prompt engineering across finance teams."),
        "expect_status": careers.SECONDARY,
    },
    "process_improvement": {
        "title": "Process Improvement Executive",
        "company": "Bank Operations",
        "description": ("Review finance and operations workflows to remove "
                        "manual effort and strengthen controls. Continuous "
                        "improvement programme delivery."),
        "expect_status": careers.SECONDARY,
    },
    # ---- must be OUT_OF_SCOPE ----
    "fcc_compliance": {
        "title": "Assistant Manager, Compliance (Financial Crime Compliance STR)",
        "company": "Hong Leong Bank Berhad",
        "description": ("Review suspicious transaction reports, conduct AML "
                        "investigations, support financial crime compliance "
                        "monitoring and regulatory reporting obligations. "
                        "Work with operations and risk stakeholders on "
                        "controls and escalation."),
        "expect_status": careers.OUT_OF_SCOPE,
    },
    "systems_support": {
        "title": "Systems Support Specialist, FCM M&E",
        "company": "FCM",
        "description": ("Provide application and systems support to internal "
                        "users. Troubleshoot incidents, manage change "
                        "requests, coordinate UAT and liaise with vendors and "
                        "operations stakeholders."),
        "expect_status": careers.OUT_OF_SCOPE,
    },
    "warehouse": {
        "title": "Assistant Manager, Warehouse Fulfillment",
        "company": "Arche Digital",
        "description": ("Oversee warehouse fulfilment, inventory accuracy and "
                        "stock reconciliation. Manage packing teams, delivery "
                        "scheduling and last mile partners."),
        "expect_status": careers.OUT_OF_SCOPE,
    },
    "retail": {
        "title": "Retail Executive",
        "company": "Bakez Grocer",
        "description": ("Manage store operations and staff rostering. Daily "
                        "cash management, float handling and reconciliation "
                        "of till takings."),
        "expect_status": careers.OUT_OF_SCOPE,
    },
    "insurance": {
        "title": "Policy Servicing Manager (Policy Changes & Conservation)",
        "company": "Zurich Insurance",
        "description": ("Handle policy alterations, surrenders and "
                        "conservation activity for life policyholders."),
        "expect_status": careers.OUT_OF_SCOPE,
    },
}


def test_classification():
    jobs = [dict(v, key=k) for k, v in JOBS.items()]
    verdicts = careers.classify(jobs)

    for job, verdict in zip(jobs, verdicts):
        expected = job["expect_status"]
        actual = verdict["career_family_status"]
        check(f"{job['key']}: {job['title'][:44]} -> {expected}",
              actual == expected,
              f"got {actual} / family '{verdict['career_family']}' "
              f"via {verdict['career_family_method']} "
              f"-- {verdict['career_family_reason'][:70]}")


def test_semantic_cannot_override():
    """The headline rule: a high semantic score must not rescue an
    out-of-scope family."""
    rows = [
        {"title": "Assistant Manager, Compliance (Financial Crime Compliance)",
         "company": "HLB", "final_score": 99.0, "semantic_score": 99.0,
         "career_family": "compliance_aml_fcc",
         "career_family_status": careers.OUT_OF_SCOPE,
         "career_family_reason": "title matches out-of-scope family",
         "history_status": "new"},
        {"title": "Reconciliation Analyst", "company": "Krypton",
         "final_score": 62.0, "semantic_score": 62.0,
         "career_family": "reconciliation",
         "career_family_status": careers.CORE,
         "history_status": "new"},
    ]
    selected = ranking.select_final(rows)
    check("A 99-score OUT_OF_SCOPE job is never selected",
          len(selected) == 1 and selected[0]["title"] == "Reconciliation Analyst"
          and rows[0]["selection_status"] == "out_of_scope",
          f"selected: {[s['title'][:30] for s in selected]}; "
          f"blocked reason: {rows[0]['selection_reason'][:60]}")


def test_rescue_term():
    """'Compliance' is out of scope, but fund-domain compliance is not."""
    verdict = careers.classify_by_rules({
        "title": "Fund Services Compliance Officer",
        "company": "Custodian Bank",
        "description": "Oversight of fund administration and transfer agency.",
    })
    ok = verdict is None or verdict["career_family_status"] != careers.OUT_OF_SCOPE
    check("Fund-domain compliance is rescued from the out-of-scope rule",
          ok,
          f"verdict: {verdict['career_family_status'] if verdict else 'deferred to embedding'}")


def test_unknown_not_actionable():
    check("UNKNOWN family is not actionable by default",
          not careers.is_actionable(careers.UNKNOWN)
          and not config.CAREER_ALLOW_UNKNOWN)
    for status in (careers.CORE, careers.SECONDARY, careers.ADJACENT):
        check(f"{status} is actionable", careers.is_actionable(status))
    check("OUT_OF_SCOPE is never actionable",
          not careers.is_actionable(careers.OUT_OF_SCOPE))


def test_no_llm():
    check("Career gating does not import the strong LLM module",
          "llm" not in sys.modules,
          "classification used rules + the local embedding model only")


def main():
    print("=" * 70)
    print("CAREER-FAMILY GATING TESTS")
    print("=" * 70)
    test_classification()
    print()
    test_semantic_cannot_override()
    test_rescue_term()
    test_unknown_not_actionable()
    test_no_llm()

    print("\n" + "=" * 70)
    failed = [r for r in _results if r[0] == "FAIL"]
    print(f"{len(_results) - len(failed)} passed, {len(failed)} failed")
    for _, name, detail in failed:
        print(f"  FAILED: {name} -- {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
