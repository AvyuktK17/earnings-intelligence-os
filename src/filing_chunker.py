from src.database import get_supabase_client
from src.storage import download_file


def chunk_text(text: str, max_characters: int = 2000) -> list[str]:
    """Split text into chunks of at most max_characters, breaking on paragraphs.

    Args:
        text: The plain text to split.
        max_characters: Maximum characters per chunk.

    Returns:
        A list of non-empty text chunks in original order.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # If one paragraph alone exceeds the limit, split it by characters
        if len(paragraph) > max_characters:
            # Flush whatever is in the current buffer first
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(paragraph), max_characters):
                piece = paragraph[start : start + max_characters]
                chunks.append(piece)
            continue

        # Would adding this paragraph exceed the limit?
        tentative = (current + "\n\n" + paragraph).strip() if current else paragraph
        if len(tentative) <= max_characters:
            current = tentative
        else:
            if current:
                chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return [c for c in chunks if c]


def chunk_and_store_filing(accession_number: str) -> dict:
    """Download, chunk, and store the parsed text for a filing.

    Args:
        accession_number: The filing's unique accession number.

    Returns:
        A dict with ticker, accession_number, filing_id, chunk_count,
        total_characters, and average_chunk_characters.

    Raises:
        ValueError: If the filing is not found, not parsed, or missing a text path.
    """
    supabase = get_supabase_client()

    response = (
        supabase.table("filings")
        .select("id, ticker, accession_number, processing_status, text_storage_path")
        .eq("accession_number", accession_number)
        .execute()
    )

    if not response.data:
        raise ValueError(f"No filing found with accession_number={accession_number!r}.")

    filing = response.data[0]

    if filing["processing_status"] != "parsed":
        raise ValueError(
            f"Filing {accession_number} has status {filing['processing_status']!r}. "
            "Only 'parsed' filings can be chunked."
        )

    if not filing["text_storage_path"]:
        raise ValueError(
            f"Filing {accession_number} has no text_storage_path. "
            "Run the backfill worker first."
        )

    filing_id = filing["id"]
    ticker = filing["ticker"].lower()
    safe_accession = accession_number.replace("-", "_")
    local_path = f"data/chunking_inputs/{ticker}_{safe_accession}.txt"

    download_file(filing["text_storage_path"], local_path)

    with open(local_path, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = chunk_text(text, max_characters=2000)

    # Delete existing chunks for this filing so rerunning is safe
    supabase.table("filing_chunks").delete().eq(
        "accession_number", accession_number
    ).execute()

    # Insert new chunks
    rows = [
        {
            "filing_id": filing_id,
            "ticker": filing["ticker"],
            "accession_number": accession_number,
            "chunk_index": i,
            "chunk_text": chunk,
            "character_count": len(chunk),
        }
        for i, chunk in enumerate(chunks)
    ]

    supabase.table("filing_chunks").insert(rows).execute()

    total_characters = sum(len(c) for c in chunks)
    average_chunk_characters = round(total_characters / len(chunks)) if chunks else 0

    return {
        "ticker": filing["ticker"],
        "accession_number": accession_number,
        "filing_id": filing_id,
        "chunk_count": len(chunks),
        "total_characters": total_characters,
        "average_chunk_characters": average_chunk_characters,
    }
