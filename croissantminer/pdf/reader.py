"""
PDF reading and text extraction utilities
"""

import requests
import PyPDF2
from pathlib import Path
from tqdm import tqdm


def download_pdf(url, output_path):
    """
    Download a PDF from a URL
    
    Args:
        url (str): URL of the PDF
        output_path (Path): Where to save the PDF
    
    Returns:
        bool: True if download successful, False otherwise
    """
    try:
        print(f"Downloading PDF from {url}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(output_path, "wb") as f:
            for chunk in tqdm(response.iter_content(chunk_size=8192)):
                f.write(chunk)
                
        print(f"✓ Downloaded to {output_path}")
        return True
        
    except Exception as e:
        print(f"✗ Error downloading PDF: {str(e)}")
        return False


def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file
    
    Args:
        pdf_path (Path): Path to the PDF file
    
    Returns:
        str: Extracted text with page break markers
    """
    print(f"Extracting text from PDF: {pdf_path}")
    
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = []
            
            for page_num in tqdm(range(len(reader.pages)), desc="Reading pages"):
                try:
                    page_text = reader.pages[page_num].extract_text()
                    if page_text:
                        pages.append(page_text)
                except Exception as e:
                    print(f"  Warning: Error on page {page_num}: {str(e)}")
                    
            text = "\n\n[PAGE_BREAK]\n\n".join(pages)
            
            print(f"✓ Extracted {len(pages)} pages")
            return text
            
    except Exception as e:
        print(f"✗ Error reading PDF: {str(e)}")
        return ""