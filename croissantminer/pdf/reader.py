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


def extract_text_from_pdf(pdf_path, backend="pypdf2"):
    """
    Extract text from a PDF file using a selectable backend.

    Backends:
      - "pypdf2"     PyPDF2 text layer (default; the canonical paper pipeline).
                     Fast, no structure: table columns are linearized/fused.
      - "pymupdf"    PyMuPDF/fitz text layer. Better reading order than PyPDF2;
                     table cells still linearized but less fused.
      - "docling"    IBM Docling layout model -> Markdown. Table-aware: tables
                     are emitted as Markdown tables with columns preserved.
                     Uses Docling's default export, which keeps only the body
                     text (no page headers/footers, no text inside figures).
      - "docling_full"  Same conversion, full export: body text, page
                     headers/footers and text inside figures.

    PyMuPDF and Docling are optional dependencies (pip install pymupdf docling);
    they are only needed for the PDF parser ablation (scripts/parser_ablation/).

    All backends return plain text with "[PAGE_BREAK]" markers between pages
    (Docling returns a single Markdown document with no page markers).

    Args:
        pdf_path (Path): Path to the PDF file
        backend (str): One of PARSER_BACKENDS.

    Returns:
        str: Extracted text.
    """
    if backend not in PARSER_BACKENDS:
        raise ValueError(
            f"Unknown parser backend {backend!r}. "
            f"Available: {sorted(PARSER_BACKENDS)}"
        )
    print(f"Extracting text from PDF ({backend}): {pdf_path}")
    try:
        return PARSER_BACKENDS[backend](pdf_path)
    except Exception as e:
        print(f"✗ Error reading PDF with {backend}: {type(e).__name__}: {e}")
        return ""


def _extract_pypdf2(pdf_path):
    """PyPDF2 text layer — the canonical paper pipeline (unchanged behavior)."""
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


def _extract_pymupdf(pdf_path):
    """PyMuPDF/fitz text layer — better reading order than PyPDF2."""
    import fitz  # PyMuPDF
    pages = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            page_text = page.get_text("text")
            if page_text:
                pages.append(page_text)
    text = "\n\n[PAGE_BREAK]\n\n".join(pages)
    print(f"✓ Extracted {len(pages)} pages")
    return text


def _extract_docling(pdf_path):
    """IBM Docling layout model -> Markdown (tables preserved as Markdown)."""
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    text = result.document.export_to_markdown()
    print(f"✓ Extracted {len(text)} chars (Docling Markdown)")
    return text


def _extract_docling_full(pdf_path):
    """Docling with a COMPLETE Markdown export.

    Docling's default ``export_to_markdown()`` emits only the BODY content layer
    and skips text nested inside pictures. That silently drops running headers,
    footers and the arXiv margin stamp (FURNITURE layer, where the release date
    and venue usually live) and all text inside figures. This variant keeps
    both; conversion itself is unchanged (default DocumentConverter).
    """
    from docling.document_converter import DocumentConverter
    from docling_core.types.doc.document import ContentLayer
    converter = DocumentConverter()
    doc = converter.convert(str(pdf_path)).document
    text = doc.export_to_markdown(
        included_content_layers={ContentLayer.BODY, ContentLayer.FURNITURE},
        traverse_pictures=True,
    )
    print(f"✓ Extracted {len(text)} chars (Docling Markdown, body+furniture+figure text)")
    return text


PARSER_BACKENDS = {
    "pypdf2": _extract_pypdf2,
    "pymupdf": _extract_pymupdf,
    "docling": _extract_docling,
    "docling_full": _extract_docling_full,
}
