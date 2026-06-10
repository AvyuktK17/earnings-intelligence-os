"""Test the Claude-assisted report review service.

Runs against live Supabase. Creates clearly-marked temporary Claude-assisted
drafts and deletes every row it creates (drafts, superseded originals, reviewed
versions, evidence links, audit runs) in a ``finally`` block. No trusted claims
or deterministic reports are modified. No Claude/Gemini calls.

Verifies:

* approve: draft → reviewed;
* edit-and-approve: original preserved as superseded, new reviewed version made
  with copied evidence links;
* reject: draft → rejected with reason;
* invalid transitions are rejected;
* deterministic reports cannot be reviewed through this workflow.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.claude_narrative_import import insert_claude_draft
from src.research_report_review import (
    approve_research_report,
    edit_and_approve_research_report,
    reject_research_report,
)

TICKER = "AVGO"
LABEL = "Claude-assisted draft for analyst review"
_DRAFT = f"""{LABEL}

# Broadcom (AVGO) — Earnings Update

## 1. Front-page executive summary

Temporary review-service test draft. Deleted immediately after the test.

## 11. Methodology and limitations

Claude-assisted draft for analyst review.
"""


def _new_draft(supabase) -> dict:
    return insert_claude_draft(
        ticker=TICKER, markdown_content=_DRAFT, supabase=supabase
    )


def _cleanup(supabase, report_ids: list[int]) -> None:
    # Break self-referential source_report_id links first so deletes don't hit
    # the FK constraint, then remove evidence links, audit runs, and rows.
    for rid in report_ids:
        supabase.table("research_reports").update(
            {"source_report_id": None}
        ).eq("id", rid).execute()
    for rid in report_ids:
        supabase.table("report_evidence_links").delete().eq(
            "research_report_id", rid
        ).execute()
        supabase.table("report_generation_runs").delete().eq(
            "report_id", rid
        ).execute()
        supabase.table("research_reports").delete().eq("id", rid).execute()


def main() -> None:
    supabase = get_supabase_client()
    created: list[int] = []

    try:
        # --- Approve: draft → reviewed --------------------------------------
        d1 = _new_draft(supabase)
        created.append(d1["report_id"])
        approved = approve_research_report(
            d1["report_id"], reviewer_notes="Checked against evidence."
        )
        assert approved["report_status"] == "reviewed", approved
        assert approved["reviewed_at"], "reviewed_at must be set."
        assert approved["reviewer_notes"] == "Checked against evidence."

        # Approving again is now an invalid transition (not a draft).
        try:
            approve_research_report(d1["report_id"])
            raise AssertionError("Approving a reviewed report should fail.")
        except ValueError:
            pass

        # --- Edit-and-approve: supersede original, create reviewed version --
        d2 = _new_draft(supabase)
        created.append(d2["report_id"])
        d2_links = (
            supabase.table("report_evidence_links")
            .select("id")
            .eq("research_report_id", d2["report_id"])
            .execute()
            .data
        )
        edited = edit_and_approve_research_report(
            d2["report_id"],
            edited_markdown_content=_DRAFT + "\n\nEdited for clarity.\n",
            reviewer_notes="Tightened wording.",
        )
        created.append(edited["id"])
        assert edited["id"] != d2["report_id"], "Must create a new row."
        assert edited["report_status"] == "reviewed"
        assert edited["source_report_id"] == d2["report_id"]
        assert edited["version_number"] == d2["version_number"] + 1
        assert "Edited for clarity." in edited["markdown_content"]

        # Original is now superseded and immutable (content unchanged).
        original = (
            supabase.table("research_reports")
            .select("report_status, markdown_content")
            .eq("id", d2["report_id"])
            .execute()
            .data[0]
        )
        assert original["report_status"] == "superseded"
        assert "Edited for clarity." not in original["markdown_content"]

        # Evidence links were copied to the reviewed version.
        new_links = (
            supabase.table("report_evidence_links")
            .select("id")
            .eq("research_report_id", edited["id"])
            .execute()
            .data
        )
        assert len(new_links) == len(d2_links), (
            "Evidence links must be copied to the reviewed version."
        )

        # Empty edit is rejected.
        d_empty = _new_draft(supabase)
        created.append(d_empty["report_id"])
        try:
            edit_and_approve_research_report(d_empty["report_id"], "   ")
            raise AssertionError("Empty edit should fail.")
        except ValueError:
            pass

        # --- Reject: draft → rejected ---------------------------------------
        d3 = _new_draft(supabase)
        created.append(d3["report_id"])
        rejected = reject_research_report(
            d3["report_id"],
            rejection_reason="Narrative overstates the evidence.",
            reviewer_notes="Regenerate after template refinement.",
        )
        assert rejected["report_status"] == "rejected"
        assert rejected["rejection_reason"] == "Narrative overstates the evidence."
        assert rejected["reviewed_at"]

        # Reject requires a reason.
        d4 = _new_draft(supabase)
        created.append(d4["report_id"])
        try:
            reject_research_report(d4["report_id"], rejection_reason="  ")
            raise AssertionError("Empty rejection reason should fail.")
        except ValueError:
            pass

        # --- Deterministic reports cannot be reviewed here ------------------
        deterministic = (
            supabase.table("research_reports")
            .select("id")
            .eq("generator_type", "deterministic")
            .limit(1)
            .execute()
            .data
        )
        if deterministic:
            det_id = deterministic[0]["id"]
            for action in (
                lambda: approve_research_report(det_id),
                lambda: edit_and_approve_research_report(det_id, "edited"),
                lambda: reject_research_report(det_id, "no"),
            ):
                try:
                    action()
                    raise AssertionError(
                        "Deterministic report must not be reviewable here."
                    )
                except ValueError:
                    pass
            # Confirm the deterministic report was untouched.
            still = (
                supabase.table("research_reports")
                .select("report_status, generator_type")
                .eq("id", det_id)
                .execute()
                .data[0]
            )
            assert still["generator_type"] == "deterministic"
            assert still["report_status"] == "human_reviewed_deterministic"

        print(
            "OK: review service — approve, edit-and-approve (supersede + copy "
            "links), reject, invalid-transition guards, and deterministic "
            "protection all verified."
        )
    finally:
        _cleanup(supabase, created)


if __name__ == "__main__":
    main()
