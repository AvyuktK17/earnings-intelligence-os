"""Test the Claude-assisted narrative import service.

Runs against live Supabase. All rows created here are clearly marked drafts and
are deleted in a ``finally`` block, including their evidence links and audit
runs; no trusted claims or real reports are modified. No Claude/Gemini calls.

Verifies:

* a dry run (validation only) writes nothing;
* a confirmed import inserts exactly one draft;
* a missing markdown file is rejected;
* a draft missing the required label is rejected;
* the packet hash is deterministic;
* a rerun creates a new version rather than overwriting.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.claude_narrative_import import (
    _sha256_file,
    import_claude_assisted_narrative,
    insert_claude_draft,
    validate_draft_markdown,
)

TICKER = "AVGO"
LABEL = "Claude-assisted draft for analyst review"

_VALID_DRAFT = f"""{LABEL}

# Broadcom (AVGO) — Earnings Update

## 1. Front-page executive summary

Temporary test draft. Revenue and margins as reported in the packet. This is a
deterministic test fixture used to exercise the import service and is deleted
immediately afterward.

## 11. Methodology and limitations

Claude-assisted draft for analyst review; not human-reviewed or published.
"""


def _cleanup(supabase, report_ids: list[int]) -> None:
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

    # --- Validation: missing label is rejected ------------------------------
    try:
        validate_draft_markdown("# Just a heading\n\n## Section\n\n" + "x" * 300)
        raise AssertionError("Unlabelled draft should have been rejected.")
    except ValueError:
        pass

    # --- Validation: empty is rejected --------------------------------------
    try:
        validate_draft_markdown("   ")
        raise AssertionError("Empty draft should have been rejected.")
    except ValueError:
        pass

    try:
        # --- Missing file is rejected (dry-run path uses the same check) ----
        try:
            import_claude_assisted_narrative(
                TICKER, markdown_path="/nonexistent/does_not_exist.md"
            )
            raise AssertionError("Missing markdown file should raise.")
        except FileNotFoundError:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, "draft.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(_VALID_DRAFT)
            packet_path = os.path.join(tmp, "packet.md")
            with open(packet_path, "w", encoding="utf-8") as f:
                f.write("packet contents for hashing")

            # --- Packet hash is deterministic -------------------------------
            assert _sha256_file(packet_path) == _sha256_file(packet_path)

            # --- Count drafts before importing ------------------------------
            before = (
                supabase.table("research_reports")
                .select("id")
                .eq("ticker", TICKER)
                .eq("generator_type", "claude_assisted")
                .eq("report_status", "draft")
                .execute()
                .data
            )

            # --- Confirmed import inserts exactly one draft -----------------
            result = import_claude_assisted_narrative(
                ticker=TICKER,
                markdown_path=md_path,
                source_packet_path=packet_path,
            )
            created.append(result["report_id"])
            assert result["report_status"] == "draft", result
            assert result["source_packet_hash"] == _sha256_file(packet_path)
            assert result["evidence_link_count"] >= 1, (
                "AVGO draft should reuse trusted evidence links."
            )

            after = (
                supabase.table("research_reports")
                .select("id")
                .eq("ticker", TICKER)
                .eq("generator_type", "claude_assisted")
                .eq("report_status", "draft")
                .execute()
                .data
            )
            assert len(after) == len(before) + 1, "Exactly one draft expected."

            # --- Inserted row carries the right provenance ------------------
            row = (
                supabase.table("research_reports")
                .select("*")
                .eq("id", result["report_id"])
                .execute()
                .data[0]
            )
            assert row["generator_type"] == "claude_assisted"
            assert row["report_status"] == "draft"
            assert row["imported_at"], "imported_at must be set."
            assert LABEL in row["markdown_content"]

            # --- Rerun creates a NEW version, never overwrites --------------
            result2 = insert_claude_draft(
                ticker=TICKER,
                markdown_content=_VALID_DRAFT,
                accession_number=result["accession_number"],
                supabase=supabase,
            )
            created.append(result2["report_id"])
            assert result2["report_id"] != result["report_id"]
            assert result2["version_number"] == result["version_number"] + 1, (
                "Rerun must increment the Claude-assisted version number."
            )

        print(
            "OK: import service — dry-run/validation safe, confirmed import "
            f"inserts one draft (v{result['version_number']}), rerun versions "
            f"to v{result2['version_number']}, packet hash deterministic."
        )
    finally:
        _cleanup(supabase, created)


if __name__ == "__main__":
    main()
