"""Tests for the research-report API (reads + protected generation).

Generates temporary reports under a unique report_type, verifies versioning,
evidence links, PDF persistence, the signed-URL PDF route, and the protected
generation endpoint, then deletes every temporary row and Storage object in a
finally block. Real earnings_update reports and trusted claims are never
touched. No AI is called.
"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from src.database import get_supabase_client
from src.storage import BUCKET_NAME

TEMP_TYPE = f"test_temp_{int(time.time())}"
TICKER = "AVGO"

FORBIDDEN = [
    r"implied share price",
    r"price target of \$",
    r"\bwe rate\b",
    r"\b(buy|sell|hold) rating\b",
]


def _cleanup(report_ids: list[int]) -> None:
    sb = get_supabase_client()
    if report_ids:
        sb.table("report_evidence_links").delete().in_(
            "research_report_id", report_ids
        ).execute()
        sb.table("report_generation_runs").delete().in_("report_id", report_ids).execute()
        sb.table("research_reports").delete().in_("id", report_ids).execute()
    # Remove any temp run rows without a report id, and Storage objects.
    sb.table("report_generation_runs").delete().eq("report_type", TEMP_TYPE).execute()
    paths = [
        f"reports/{TICKER.lower()}/{TEMP_TYPE}/v{v}.{ext}"
        for v in (1, 2)
        for ext in ("md", "html", "pdf")
    ]
    try:
        sb.storage.from_(BUCKET_NAME).remove(paths)
    except Exception:
        pass


def main() -> None:
    # Supply a temporary admin token through the environment (never printed).
    os.environ["ADMIN_API_TOKEN"] = "test-token-reports-" + str(int(time.time()))
    token = os.environ["ADMIN_API_TOKEN"]
    client = TestClient(app)
    report_ids: list[int] = []

    try:
        # Protected: no token -> 401.
        assert (
            client.post("/reports/generate", json={"ticker": TICKER}).status_code
            == 401
        )
        print("POST /reports/generate without token -> 401")

        headers = {"X-Admin-Token": token}

        # v1 then v2 (versioning).
        r1 = client.post(
            "/reports/generate",
            headers=headers,
            json={"ticker": TICKER, "report_type": TEMP_TYPE},
        )
        assert r1.status_code == 200, r1.text
        m1 = r1.json()
        report_ids.append(m1["report_id"])
        assert m1["version_number"] == 1
        assert m1["evidence_link_count"] == m1["source_claim_count"]
        assert m1["pdf_storage_path"].endswith("v1.pdf")
        print(f"Generated v1 (report_id={m1['report_id']}, "
              f"claims={m1['source_claim_count']}, "
              f"links={m1['evidence_link_count']}).")

        r2 = client.post(
            "/reports/generate",
            headers=headers,
            json={"ticker": TICKER, "report_type": TEMP_TYPE},
        )
        assert r2.status_code == 200, r2.text
        m2 = r2.json()
        report_ids.append(m2["report_id"])
        assert m2["version_number"] == 2, "versioning failed"
        print(f"Generated v2 (report_id={m2['report_id']}) — prior version preserved.")

        # List filtered to the temp type -> both versions.
        listing = client.get("/reports", params={"report_type": TEMP_TYPE}).json()
        assert listing["count"] == 2
        assert {r["version_number"] for r in listing["reports"]} == {1, 2}
        assert all(r["pdf_available"] for r in listing["reports"])
        print(f"GET /reports?report_type={TEMP_TYPE} -> 2 versions, PDFs available.")

        # Latest -> v2 with content + evidence links + deterministic status.
        latest = client.get(
            f"/reports/latest/{TICKER}", params={"report_type": TEMP_TYPE}
        ).json()
        assert latest["version_number"] == 2
        assert latest["report_status"] == "human_reviewed_deterministic"
        assert latest["markdown_content"] and latest["html_content"]
        assert len(latest["evidence_links"]) == m2["source_claim_count"]
        print(f"GET /reports/latest/{TICKER} -> v2, "
              f"{len(latest['evidence_links'])} evidence links.")

        # Detail by id.
        detail = client.get(f"/reports/{m1['report_id']}").json()
        assert detail["id"] == m1["report_id"]
        assert detail["markdown_content"]
        # No fabricated valuation / rating / target content; dated snapshot.
        low = detail["markdown_content"].lower()
        for pattern in FORBIDDEN:
            assert not re.search(pattern, low), f"forbidden: {pattern}"
        assert "not a live market feed" in low
        print("Report content: dated valuation snapshot, no fabricated outputs.")

        # PDF route returns a signed-URL redirect, and the object really exists.
        pdf = client.get(
            f"/reports/{m1['report_id']}/pdf", follow_redirects=False
        )
        assert pdf.status_code == 307
        assert "/storage/v1/object/sign" in pdf.headers.get("location", "")
        data = get_supabase_client().storage.from_(BUCKET_NAME).download(
            m1["pdf_storage_path"]
        )
        assert data[:5] == b"%PDF-", "stored PDF is not a valid PDF"
        print(f"PDF route -> 307 signed URL; stored object is a real PDF "
              f"({len(data)} bytes).")

        # Missing report -> 404 (detail, latest, pdf).
        assert client.get("/reports/999999999").status_code == 404
        assert (
            client.get("/reports/latest/ZZZZ", params={"report_type": TEMP_TYPE}).status_code
            == 404
        )
        assert (
            client.get("/reports/999999999/pdf", follow_redirects=False).status_code
            == 404
        )
        print("Missing report / latest / pdf -> 404.")

        print("\nPASS: report generation, versioning, evidence links, PDF, and "
              "auth all verified.")
    finally:
        _cleanup(report_ids)
        print(f"Cleanup: removed temporary {TEMP_TYPE} rows and Storage objects.")


if __name__ == "__main__":
    main()
