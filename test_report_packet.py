"""Test the deterministic report-packet exporter.

Runs against live Supabase data. Read-only: no AI calls, no row mutations.
Packets are written to a temporary directory and removed in a ``finally`` block,
so nothing is left in ``output/`` and no real artifacts are touched.

Verifies that:

* the AVGO packet exports successfully (both files written);
* the packet contains only trusted, promoted, grounded claims — never pending
  or rejected proposed claims;
* metrics, peer context, the valuation snapshot date, supporting excerpts, and
  chunk ids are all present;
* output is deterministic across reruns (ignoring the generation timestamp);
* missing values are labelled honestly rather than guessed.
"""

import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.report_packet import (
    _MISSING,
    _mult,
    _pct,
    _price,
    _usd,
    export_report_packet,
)

TICKER = "AVGO"


def _strip_timestamp_json(text: str) -> dict:
    """Parse packet JSON and drop the non-deterministic generation timestamp."""
    payload = json.loads(text)
    payload.pop("generated_at", None)
    return payload


def _strip_timestamp_md(text: str) -> str:
    """Remove the generated-at line so Markdown can be compared across reruns."""
    return re.sub(r"^- \*\*Generated at \(UTC\):\*\*.*$", "", text, flags=re.MULTILINE)


def main() -> None:
    supabase = get_supabase_client()

    with tempfile.TemporaryDirectory() as tmp:
        # --- Exports successfully -----------------------------------------
        result = export_report_packet(TICKER, output_dir=tmp)
        assert result["ticker"] == TICKER, result
        assert os.path.exists(result["markdown_path"]), "Markdown packet missing."
        assert os.path.exists(result["json_path"]), "JSON packet missing."
        assert result["trusted_claim_count"] >= 1, (
            "AVGO should have at least one trusted claim in its packet."
        )
        assert result["metric_count"] >= 1, "Expected operating metric series."
        assert result["valuation_snapshot_date"], (
            "AVGO should have a dated valuation snapshot."
        )

        first_json_text = open(result["json_path"], encoding="utf-8").read()
        first_md_text = open(result["markdown_path"], encoding="utf-8").read()
        packet = json.loads(first_json_text)

        # --- Only trusted, promoted, grounded claims ----------------------
        promoted = (
            supabase.table("qualitative_claims")
            .select("proposed_claim_id")
            .eq("ticker", TICKER)
            .not_.is_("proposed_claim_id", "null")
            .execute()
            .data
        )
        promoted_ids = {r["proposed_claim_id"] for r in promoted}
        packet_ids = {c["qualitative_claim_id"] for c in packet["trusted_claims"]}
        assert packet_ids, "Packet should contain trusted claims."
        assert packet_ids <= promoted_ids, (
            "Packet contains a claim id that is not a promoted trusted claim: "
            f"{packet_ids - promoted_ids}"
        )

        # No pending / rejected proposed claims may appear by id.
        non_trusted = (
            supabase.table("proposed_claims")
            .select("id, review_status")
            .eq("ticker", TICKER)
            .in_("review_status", ["pending", "rejected"])
            .execute()
            .data
        )
        non_trusted_ids = {r["id"] for r in non_trusted} - promoted_ids
        assert not (packet_ids & non_trusted_ids), (
            "Packet leaked a pending/rejected claim id: "
            f"{packet_ids & non_trusted_ids}"
        )

        # --- Each trusted claim is grounded (excerpt + chunk id) ----------
        for c in packet["trusted_claims"]:
            assert c["source_chunk_id"] is not None, (
                f"Claim {c['qualitative_claim_id']} is missing a source chunk id."
            )
            assert c["supporting_excerpt"], (
                f"Claim {c['qualitative_claim_id']} is missing a supporting excerpt."
            )

        # --- Metrics, peers, valuation present ----------------------------
        assert packet["financial_metrics"]["latest_quarter"], "Missing latest metrics."
        assert packet["financial_metrics"]["series"], "Missing metric series."
        peer_tickers = {p["ticker"] for p in packet["peer_comparison"]}
        assert TICKER in peer_tickers, "Subject ticker missing from peer comparison."
        assert packet["valuation_snapshot"]["snapshot_date"], "Missing snapshot date."
        assert packet["valuation_snapshot"]["is_live"] is False, (
            "Valuation must be flagged as not live."
        )

        # --- Evidence appendix carries chunk ids --------------------------
        assert packet["evidence_links"], "Expected evidence links."
        for link in packet["evidence_links"]:
            assert link["source_chunk_id"] is not None
            assert link["supporting_excerpt"]

        # --- Deterministic across reruns ----------------------------------
        result2 = export_report_packet(
            TICKER, accession_number=result["accession_number"], output_dir=tmp
        )
        second_json_text = open(result2["json_path"], encoding="utf-8").read()
        second_md_text = open(result2["markdown_path"], encoding="utf-8").read()
        assert _strip_timestamp_json(first_json_text) == _strip_timestamp_json(
            second_json_text
        ), "JSON packet is not deterministic across reruns."
        assert _strip_timestamp_md(first_md_text) == _strip_timestamp_md(
            second_md_text
        ), "Markdown packet is not deterministic across reruns."

    # --- Missing data is labelled honestly --------------------------------
    assert _usd(None) == _MISSING
    assert _pct(None) == _MISSING
    assert _mult(None) == _MISSING
    assert _price(None) == _MISSING

    print(
        f"OK: report packet for {TICKER} "
        f"(trusted_claims={result['trusted_claim_count']}, "
        f"metrics={result['metric_count']}, "
        f"evidence_links={result['evidence_link_count']}, "
        f"valuation_snapshot_date={result['valuation_snapshot_date']}) "
        "exported deterministically with trusted claims only."
    )


if __name__ == "__main__":
    main()
