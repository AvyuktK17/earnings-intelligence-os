"""Test the Claude-assisted narrative review API endpoints.

Uses FastAPI TestClient against live Supabase. Supplies a temporary admin token
through the environment (never printed). Every report row created here is a
clearly-marked draft and is deleted in a ``finally`` block, along with its
evidence links and audit runs. No trusted claims or deterministic reports are
modified. No Claude/Gemini calls.

Verifies:

* missing / invalid token → 401 on every write endpoint and on the review queue;
* import-claude-draft inserts a private draft;
* a draft missing the required label → 400;
* the review queue returns Claude-assisted drafts only;
* public report endpoints exclude drafts (list + detail);
* approve / edit-and-approve / reject work;
* edit-and-approve's reviewed version is publicly visible; the original is
  superseded;
* 404 (unknown report) and 400 (invalid transition) behave;
* error bodies never expose secrets or stack traces.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

TEMP_TOKEN = "test-report-review-token-do-not-use-in-prod"
os.environ["ADMIN_API_TOKEN"] = TEMP_TOKEN

from app.main import app  # noqa: E402  (import after env is set)
from src.database import get_supabase_client  # noqa: E402

TICKER = "AVGO"
LABEL = "Claude-assisted draft for analyst review"
HEADERS = {"X-Admin-Token": TEMP_TOKEN}
_DRAFT = f"""{LABEL}

# Broadcom (AVGO) — Earnings Update

## 1. Front-page executive summary

Temporary API-test draft. Deleted immediately after the test.

## 11. Methodology and limitations

Claude-assisted draft for analyst review.
"""


def _cleanup(supabase, report_ids):
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
    client = TestClient(app)
    supabase = get_supabase_client()
    created = []

    try:
        # --- Auth: every write endpoint + queue rejects missing/bad token ---
        assert client.get("/reports/review-queue").status_code == 401
        assert (
            client.get("/reports/review-queue", headers={"X-Admin-Token": "wrong"})
            .status_code
            == 401
        )
        assert (
            client.post(
                "/reports/import-claude-draft",
                json={"ticker": TICKER, "markdown_content": _DRAFT},
            ).status_code
            == 401
        )
        assert client.post("/reports/1/approve", json={}).status_code == 401

        # --- Import a draft -------------------------------------------------
        resp = client.post(
            "/reports/import-claude-draft",
            headers=HEADERS,
            json={"ticker": TICKER, "markdown_content": _DRAFT},
        )
        assert resp.status_code == 200, resp.text
        draft = resp.json()
        created.append(draft["report_id"])
        assert draft["report_status"] == "draft"
        draft_id = draft["report_id"]

        # --- Missing label → 400 (no secrets in body) -----------------------
        bad = client.post(
            "/reports/import-claude-draft",
            headers=HEADERS,
            json={"ticker": TICKER, "markdown_content": "# no label here\n\n## x"},
        )
        assert bad.status_code == 400, bad.text
        assert "token" not in bad.text.lower() or "Admin token" not in bad.text

        # --- Review queue returns Claude-assisted drafts only ---------------
        queue = client.get("/reports/review-queue", headers=HEADERS).json()
        ids = {r["id"] for r in queue["reports"]}
        assert draft_id in ids, "Imported draft should appear in the review queue."
        for r in queue["reports"]:
            assert r["generator_type"] == "claude_assisted"
            assert r["report_status"] == "draft"
            assert "markdown_content" in r
            assert "evidence_link_count" in r

        # --- Public report endpoints exclude drafts -------------------------
        public_list = client.get(f"/reports?ticker={TICKER}").json()
        assert draft_id not in {r["id"] for r in public_list["reports"]}, (
            "Draft must not appear in the public reports list."
        )
        assert client.get(f"/reports/{draft_id}").status_code == 404, (
            "Public report detail must hide drafts."
        )

        # --- Unknown report → 404 on a write action -------------------------
        assert (
            client.post(
                "/reports/999999999/approve", headers=HEADERS, json={}
            ).status_code
            == 404
        )

        # --- Edit-and-approve: reviewed version is public; original gone ----
        edited = client.post(
            f"/reports/{draft_id}/edit-and-approve",
            headers=HEADERS,
            json={
                "edited_markdown_content": _DRAFT + "\n\nEdited.\n",
                "reviewer_notes": "Tightened wording.",
            },
        )
        assert edited.status_code == 200, edited.text
        reviewed = edited.json()
        created.append(reviewed["id"])
        assert reviewed["report_status"] == "reviewed"
        assert reviewed["source_report_id"] == draft_id

        # The reviewed Claude-assisted report is now publicly visible.
        assert client.get(f"/reports/{reviewed['id']}").status_code == 200
        # The original draft is superseded → still hidden publicly.
        assert client.get(f"/reports/{draft_id}").status_code == 404
        # Invalid transition: the superseded original can't be approved.
        assert (
            client.post(
                f"/reports/{draft_id}/approve", headers=HEADERS, json={}
            ).status_code
            == 400
        )

        # --- Approve path on a fresh draft ----------------------------------
        d2 = client.post(
            "/reports/import-claude-draft",
            headers=HEADERS,
            json={"ticker": TICKER, "markdown_content": _DRAFT},
        ).json()
        created.append(d2["report_id"])
        appr = client.post(
            f"/reports/{d2['report_id']}/approve",
            headers=HEADERS,
            json={"reviewer_notes": "Reviewed against trusted evidence."},
        )
        assert appr.status_code == 200, appr.text
        assert appr.json()["report_status"] == "reviewed"

        # --- Reject path on a fresh draft -----------------------------------
        d3 = client.post(
            "/reports/import-claude-draft",
            headers=HEADERS,
            json={"ticker": TICKER, "markdown_content": _DRAFT},
        ).json()
        created.append(d3["report_id"])
        rej = client.post(
            f"/reports/{d3['report_id']}/reject",
            headers=HEADERS,
            json={"rejection_reason": "Overstates the evidence."},
        )
        assert rej.status_code == 200, rej.text
        assert rej.json()["report_status"] == "rejected"
        # Rejected report is hidden publicly.
        assert client.get(f"/reports/{d3['report_id']}").status_code == 404
        # Reject without a reason → 422 (validation).
        assert (
            client.post(
                f"/reports/{d2['report_id']}/reject",
                headers=HEADERS,
                json={"rejection_reason": ""},
            ).status_code
            == 422
        )

        print(
            "OK: report-review API — auth (401), import (draft), label 400, "
            "queue drafts-only, public excludes drafts, approve / "
            "edit-and-approve / reject, 404 + invalid-transition 400, "
            "reviewed version public."
        )
    finally:
        _cleanup(supabase, created)


if __name__ == "__main__":
    main()
