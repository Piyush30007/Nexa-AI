import logfire
from bs4 import BeautifulSoup

def parse_html(file_path : str)->str :

    """
    Parse HTML files using BeautifulSoup to extract only the visible text
    clean scripts , styles and exctracts readable text for rag pipeline 
    """
    with logfire.span("HTML Parsing(local)" , file_path=file_path):
        try:
            with open(file_path , 'r' , encoding='utf-8' , errors="ignore") as f :
                text = f.read()
                logfire.info(f"Successfully read HTML file")
            soup = BeautifulSoup(text , "html.parser")
                # remove scripts and styles 
            for script in soup(["script" , "style"]) :
                script.decompose()
            full_text = soup.get_text(separator="\n")
            #cleans whitespace 
            lines = [line.strip() for line in full_text.splitlines() if line.strip()]
            text_clean = "\n".join(lines)
            return text_clean

        except Exception as e :
            logfire.error(f"HTML parsing failed on {file_path} : {str(e)}")
            return ""
