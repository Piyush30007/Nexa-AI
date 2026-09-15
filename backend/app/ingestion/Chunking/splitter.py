from typing import List
import logfire


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """
    Splits the input text into chunks of specified size with a given overlap.
    
    Args:
        text (str): The input text to be chunked.
        chunk_size (int): The maximum size of each chunk. Default is 1500 characters.
        overlap (int): The number of overlapping characters between consecutive chunks. Default is 200 characters.
        
    Returns:
        List[str]: A list of text chunks.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")
    if overlap < 0:
        raise ValueError("overlap must be a non-negative integer.")
    
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end]
        chunks.append(chunk)
        
        # Move the start index forward by chunk_size - overlap
        start += chunk_size - overlap
    
    return chunks