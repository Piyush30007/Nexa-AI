import logfire 
def parse_text(file_path : str):

    """
    Parse Plains  text files 
    """
    with logfire.span("Text Parsing(local)" , file_path=file_path):
        try:
            with open(file_path , 'r' , encoding='utf-8') as f :
                text = f.read()
                logfire.info(f"Successfully read text file")
                return text 
        except Exception as e :
            logfire.error(f"Text parsing failed on {file_path} : {str(e)}")
            return ""
            