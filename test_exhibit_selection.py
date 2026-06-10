"""Unit tests for earnings-release exhibit classification and ranking.

Synthetic inputs only — no network, no Supabase, no AI calls. Covers the
AVGO EX-99.1 case, the NVDA pr.htm case, the AMD 99.1-without-separator
case, and the rule that a smaller press release beats a larger slide deck.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.filing_exhibits import _classify_exhibit, select_earnings_release_exhibit


def _exhibit(filename: str, size_bytes: int, exhibit_type: str = "earnings_release") -> dict:
    return {
        "filename": filename,
        "url": f"https://www.sec.gov/fake/{filename}",
        "description": filename,
        "size_bytes": size_bytes,
        "likely_exhibit_type": exhibit_type,
    }


def main() -> None:
    # --- Classification ------------------------------------------------------
    assert _classify_exhibit("avgo-05032026x8kxex99.htm", "avgo-05032026x8k.htm") == "earnings_release"
    assert _classify_exhibit("q1fy27pr.htm", "nvda-20260520.htm") == "earnings_release"
    # AMD's 99.1 naming without a separator (the file the old pattern missed)
    assert _classify_exhibit("q12026991.htm", "amd-20260505.htm") == "earnings_release"
    assert _classify_exhibit("amdq126earningsslidesfin.htm", "amd-20260505.htm") == "earnings_release"
    # Non-candidates stay excluded
    assert _classify_exhibit("q1fy27cfocommentary.htm", "nvda-20260520.htm") == "other"
    assert _classify_exhibit("nvda-20260520.htm", "nvda-20260520.htm") == "primary_document"
    assert _classify_exhibit("R1.htm", "x.htm") == "xbrl_viewer"
    print("Classification: AVGO/NVDA/AMD earnings exhibits recognized; non-candidates excluded.")

    # --- AVGO: single EX-99.1 candidate is selected ---------------------------
    avgo = [
        _exhibit("avgo-05032026x8k.htm", 33_000, "primary_document"),
        _exhibit("avgo-05032026x8kxex99.htm", 518_000),
        _exhibit("R1.htm", 5_000, "xbrl_viewer"),
    ]
    selected = select_earnings_release_exhibit(avgo)
    assert selected and selected["filename"] == "avgo-05032026x8kxex99.htm"
    print("AVGO: EX-99.1 exhibit selected.")

    # --- NVDA: pr.htm press release is selected -------------------------------
    nvda = [
        _exhibit("nvda-20260520.htm", 30_000, "primary_document"),
        _exhibit("q1fy27pr.htm", 200_000),
        _exhibit("q1fy27cfocommentary.htm", 400_000, "other"),
    ]
    selected = select_earnings_release_exhibit(nvda)
    assert selected and selected["filename"] == "q1fy27pr.htm"
    print("NVDA: pr.htm press release selected.")

    # --- A smaller press release must beat a larger slide deck ----------------
    mixed = [
        _exhibit("q1pressrelease.htm", 50_000),
        _exhibit("q1earningsslides.htm", 900_000),
    ]
    selected = select_earnings_release_exhibit(mixed)
    assert selected and selected["filename"] == "q1pressrelease.htm", (
        f"Slide deck beat the press release: {selected}."
    )
    print("Ranking: smaller press release beats larger slide deck.")

    # --- AMD real-world shape: 99.1 press release beats earnings slides -------
    amd = [
        _exhibit("amdq126earningsslidesfin.htm", 800_000),
        _exhibit("q12026991.htm", 120_000),
    ]
    selected = select_earnings_release_exhibit(amd)
    assert selected and selected["filename"] == "q12026991.htm", (
        f"Expected the 99.1 press release, got {selected}."
    )
    print("AMD shape: 99.1 press release beats slide deck.")

    # --- Size still breaks ties within the same quality tier ------------------
    tie = [
        _exhibit("small-pressrelease.htm", 10_000),
        _exhibit("big-pressrelease.htm", 90_000),
    ]
    selected = select_earnings_release_exhibit(tie)
    assert selected and selected["filename"] == "big-pressrelease.htm"
    print("Tie-break: larger file wins within the same tier.")

    assert select_earnings_release_exhibit([]) is None
    assert select_earnings_release_exhibit(
        [_exhibit("only-primary.htm", 1, "primary_document")]
    ) is None
    print("Empty and no-candidate inputs return None.")

    print()
    print("PASS: exhibit classification and press-release-first ranking behave correctly.")


if __name__ == "__main__":
    main()
