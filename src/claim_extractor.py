import json
import re

from google.genai import types

from src.database import get_supabase_client
from src.llm_client import get_gemini_client

_MODEL = "gemini-2.5-flash"

_ALLOWED_CLAIM_TYPES = {"factual", "interpretive"}


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
_ALLOWED_CONFIDENCE = {"high", "medium", "low"}

_CLAIM_SCHEMA = types.Schema(
    type=types.Type.ARRAY,
    items=types.Schema(
        type=types.Type.OBJECT,
        required=["theme", "claim_text", "supporting_excerpt",
                  "source_chunk_index", "claim_type", "confidence"],
        properties={
            "theme": types.Schema(type=types.Type.STRING),
            "claim_text": types.Schema(type=types.Type.STRING),
            "supporting_excerpt": types.Schema(type=types.Type.STRING),
            "source_chunk_index": types.Schema(type=types.Type.INTEGER),
            "claim_type": types.Schema(
                type=types.Type.STRING,
                enum=["factual", "interpretive"],
            ),
            "confidence": types.Schema(
                type=types.Type.STRING,
                enum=["high", "medium", "low"],
            ),
        },
    ),
)


def _build_prompt(chunks: list[dict], max_claims: int) -> str:
    chunk_lines = []
    for chunk in chunks:
        chunk_lines.append(
            f"[CHUNK {chunk['chunk_index']}]\n{chunk['chunk_text']}"
        )
    chunks_text = "\n\n".join(chunk_lines)

    return f"""You are a financial analyst. Read the filing excerpts below and extract up to {max_claims} proposed claims.

Rules:
- Use ONLY information explicitly stated in the supplied chunks. Do not use outside knowledge.
- Prefer financially material claims (earnings, dividends, guidance, revenue, etc.).
- supporting_excerpt must be an EXACT quote copied verbatim from one of the chunks.
- source_chunk_index must be the integer index of the chunk containing that exact quote.
- Keep each excerpt short (one or two sentences at most).
- claim_type must be "factual" or "interpretive".
- confidence must be "high", "medium", or "low".
- If the filing does not contain enough material information, return fewer than {max_claims} claims.

Filing chunks:

{chunks_text}

Return a JSON array of claim objects. Each object must have:
  theme, claim_text, supporting_excerpt, source_chunk_index, claim_type, confidence"""


def extract_and_store_claims(
    accession_number: str,
    max_claims: int = 3,
    document_key: str | None = None,
) -> dict:
    """Extract structured claims from a chunked filing and store them for review.

    Args:
        accession_number: The filing's unique accession number.
        max_claims: Maximum number of claims to request from Gemini.
        document_key: Filter chunks to this document_key (e.g.
            ``"primary"`` or ``"exhibit:avgo-05032026x8kxex99.htm"``).
            Defaults to ``"primary"`` when omitted.

    Returns:
        A dict with ticker, accession_number, document_key,
        proposed_claim_count, skipped_invalid_count, and proposed_claims.

    Raises:
        ValueError: If the filing is not found, not chunked, or all claims are invalid.
    """
    if document_key is None:
        document_key = "primary"

    supabase = get_supabase_client()

    filing_response = (
        supabase.table("filings")
        .select("id, ticker, accession_number, processing_status")
        .eq("accession_number", accession_number)
        .execute()
    )
    if not filing_response.data:
        raise ValueError(f"No filing found with accession_number={accession_number!r}.")

    filing = filing_response.data[0]
    if filing["processing_status"] != "chunked":
        raise ValueError(
            f"Filing {accession_number} has status {filing['processing_status']!r}. "
            "Only 'chunked' filings can have claims extracted."
        )

    filing_id = filing["id"]
    ticker = filing["ticker"]

    chunks_response = (
        supabase.table("filing_chunks")
        .select("chunk_index, chunk_text")
        .eq("accession_number", accession_number)
        .eq("document_key", document_key)
        .order("chunk_index")
        .execute()
    )
    chunks = chunks_response.data
    if not chunks:
        raise ValueError(
            f"No chunks found for accession_number={accession_number!r} "
            f"with document_key={document_key!r}."
        )
    chunk_map = {row["chunk_index"]: row["chunk_text"] for row in chunks}

    # Call Gemini with structured output
    client = get_gemini_client()
    prompt = _build_prompt(chunks, max_claims)

    response = client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_CLAIM_SCHEMA,
        ),
    )

    raw_claims = json.loads(response.text)

    # Validate each claim
    valid_claims = []
    skipped = 0
    for claim in raw_claims[:max_claims]:
        chunk_idx = claim.get("source_chunk_index")
        excerpt = claim.get("supporting_excerpt", "")
        claim_type = claim.get("claim_type", "")
        confidence = claim.get("confidence", "")

        if chunk_idx not in chunk_map:
            skipped += 1
            continue
        if _normalize_ws(excerpt) not in _normalize_ws(chunk_map[chunk_idx]):
            skipped += 1
            continue
        if claim_type not in _ALLOWED_CLAIM_TYPES:
            skipped += 1
            continue
        if confidence not in _ALLOWED_CONFIDENCE:
            skipped += 1
            continue

        valid_claims.append(claim)

    if not valid_claims:
        raise ValueError(
            f"All {len(raw_claims)} claims returned by Gemini failed validation. "
            "No claims were saved."
        )

    # Delete existing pending claims for this accession+document_key (safe to rerun)
    supabase.table("proposed_claims").delete().eq(
        "accession_number", accession_number
    ).eq("document_key", document_key).eq("review_status", "pending").execute()

    # Insert valid claims
    rows = [
        {
            "filing_id": filing_id,
            "ticker": ticker,
            "accession_number": accession_number,
            "document_key": document_key,
            "theme": c["theme"],
            "claim_text": c["claim_text"],
            "supporting_excerpt": _normalize_ws(c["supporting_excerpt"]),
            "source_chunk_index": c["source_chunk_index"],
            "claim_type": c["claim_type"],
            "confidence": c["confidence"],
            "review_status": "pending",
        }
        for c in valid_claims
    ]
    supabase.table("proposed_claims").insert(rows).execute()

    return {
        "ticker": ticker,
        "accession_number": accession_number,
        "document_key": document_key,
        "proposed_claim_count": len(valid_claims),
        "skipped_invalid_count": skipped,
        "proposed_claims": valid_claims,
    }
