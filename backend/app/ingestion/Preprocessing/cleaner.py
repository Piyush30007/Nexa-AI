import re
import logfire


def preprocess_text(text: str | None) -> str:
    """
    Cleans and standardizes raw extracted text before chunking:
    - Normalizes horizontal whitespace (tabs, consecutive spaces)
    - Collapses excessive blank lines (>= 3 newlines -> 2 newlines) while preserving paragraph breaks
    - Preserves headings, bullet points (-, *, •), numbered lists, punctuation, and technical terms
    - Safely handles None or empty input
    """
    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    if not text.strip():
        return ""

    with logfire.span("Text Preprocessing"):
        # 1. Standardize newline representations
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 2. Normalize horizontal whitespace (tabs, non-breaking spaces, multi-spaces) per line
        # preserving line structure, list items, and headings
        lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.split("\n")]
        text = "\n".join(lines)

        # 3. Normalize excessive blank lines (3 or more consecutive newlines become 2)
        # to maintain clear paragraph separation without arbitrary empty space
        text = re.sub(r"\n{3,}", "\n\n", text)

        cleaned_text = text.strip()
        logfire.info(f"Preprocessed text: {len(cleaned_text)} characters.")
        return cleaned_text
