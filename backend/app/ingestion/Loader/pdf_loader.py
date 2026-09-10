import logfire 
from pypdf import PdfReader
from pathlib import Path

def parse_pdf(file_path : str)->str :
    """
    Extract text from a PDF locally using pypdf 
    Falls back to pdfplumber for pages that yields no text (eg : to image-heavy pages)
    """
    with logfire.span("PDF Parsing(local)" , file_path=file_path):
        try :
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)
            logfire.info(f"PDF has {total_pages} pages")
            text_parts : list[str] = []
            blank_pages :list[int] = []
            # first attempt : PyPDF
            for i , page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip() :
                    text_parts.append(text)
                else :
                    blank_pages.append(i + 1)

                if blank_pages:
                    logfire.info(f"Found {len(blank_pages)} blank pages");
                    try :
                        import pdfplumber
                        with pdfplumber.open(file_path) as pdf :
                            for page_num in blank_pages:
                                page = pdf.pages[page_num - 1]
                                fallback_text = page.extract_text()
                                if fallback_text and fallback_text.strip():
                                    text_parts.append(fallback_text)
                                
                    except Exception as e :
                        logfire.error(f"Fallback PDF parsing failed on page {page_num} : {str(e)}")
                    full_text = "\n".join(text_parts)

                    if not full_text.strip():
                        logfire.warning("PDF is completly empty (no text detected)")
                        
                    else :
                        logfire.info(f"Successfully extracted {total_pages} pages (fallback applied to {len(blank_pages)} pages)")
                        return full_text
        except Exception as e :
            logfire.error(f"PDF parsing failed on {file_path} : {str(e)}")
            return ""