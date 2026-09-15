import logfire

def parse_office(file_path: str) -> str:
    """
    Parses Office documents (.docx, .pptx) using the Unstructured library.
    Unlike PDFs, these formats are structured and lightweight, so they are processed locally.
    """
    with logfire.span("📄 Office Document Parsing", filename=file_path):
        try:
            # Unstructured automatically detects if it's docx or pptx
            try:
                from unstructured.partition.auto import partition
                elements = partition(filename=file_path)
                full_text = "\n".join([str(el) for el in elements])
            except ImportError:
                # Fallback parser for PPTX if unstructured is not installed in the environment
                import zipfile
                import xml.etree.ElementTree as ET
                text_parts = []
                with zipfile.ZipFile(file_path, 'r') as z:
                    slide_files = sorted([f for f in z.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')])
                    for slide_file in slide_files:
                        tree = ET.fromstring(z.read(slide_file))
                        for elem in tree.iter():
                            if elem.tag.endswith('}t') and elem.text and elem.text.strip():
                                text_parts.append(elem.text.strip())
                full_text = "\n".join(text_parts)
            
            if not full_text.strip():
                logfire.warning(f"⚠️ Unstructured returned empty text for {file_path}")
            else:
                logfire.info(f"✅ Successfully parsed {len(full_text)} characters")

            return full_text
        except Exception as e:
            logfire.error(f"❌ Office Parse Failed: {e}")
            return ""

# Alias for loader consistency
parse_pptx = parse_office