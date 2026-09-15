import logfire
from docx import Document

def parse_docx(file_path : str) -> str:
    """
    Extract text from a Word (.docx) document using python-docx
    Preserves paragraph separation and returns readable text for the RAG pipeline
    """
    with logfire.span("DOCX Parsing(local)", file_path=file_path):
        try:
            doc = Document(file_path)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
            full_text = "\n".join(paragraphs)

            if not full_text.strip():
                logfire.warning(f"DOCX is completely empty (no text detected): {file_path}")
                return ""
            else:
                logfire.info(f"Successfully extracted {len(paragraphs)} paragraphs from DOCX")
                return full_text
        except Exception as e:
            logfire.error(f"DOCX parsing failed on {file_path} : {str(e)}")
            return ""

# Backward-compatible alias
parse_office = parse_docx
