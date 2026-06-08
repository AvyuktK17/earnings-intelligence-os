import os
import re
from bs4 import BeautifulSoup


def extract_filing_text(html_path: str, output_path: str) -> str:
    """Parse a filing HTML file and save the cleaned plain text.

    Args:
        html_path: Path to the downloaded filing HTML file.
        output_path: Local file path where the plain text will be saved.

    Returns:
        The output_path where the text file was saved.
    """
    with open(html_path, "rb") as f:
        raw_html = f.read()

    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove script and style tags entirely
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Collapse runs of blank lines down to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines).strip()

    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    return output_path
