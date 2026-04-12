"""arXiv validator — fetches paper metadata to cross-check datePublished and creator."""

import re
import httpx


def _extract_arxiv_id(text: str) -> str:
    """Extract arXiv ID from a string (URL or bare ID)."""
    # Try URL pattern: arxiv.org/abs/XXXX.XXXXX
    m = re.search(r'arxiv\.org/(?:abs|pdf)/([\d.]+(?:v\d+)?)', text)
    if m:
        return m.group(1)
    # Try bare ID: XXXX.XXXXX or old format cs/XXXXXXX
    m = re.search(r'(\d{4}\.\d{4,5}(?:v\d+)?)', text)
    if m:
        return m.group(1)
    m = re.search(r'([a-z-]+/\d{7})', text)
    if m:
        return m.group(1)
    return text.strip()


def validate_arxiv(arxiv_ref: str) -> dict:
    """Fetch arXiv metadata for cross-checking.

    Args:
        arxiv_ref: arXiv ID or URL

    Returns:
        {valid: bool, arxiv_id: str, title: str|null, published: str|null,
         authors: list|null, error: str|null}
    """
    if not arxiv_ref or not arxiv_ref.strip():
        return {"valid": False, "arxiv_id": None, "title": None,
                "published": None, "authors": None, "error": "empty input"}

    arxiv_id = _extract_arxiv_id(arxiv_ref)

    try:
        # Use arXiv API
        url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
        xml = resp.text

        # Parse minimal XML (avoid heavy dependency)
        title_m = re.search(r'<title>(.*?)</title>', xml, re.DOTALL)
        pub_m = re.search(r'<published>(.*?)</published>', xml)
        authors = re.findall(r'<name>(.*?)</name>', xml)

        title = title_m.group(1).strip().replace("\n", " ") if title_m else None
        published = pub_m.group(1).strip()[:10] if pub_m else None  # YYYY-MM-DD

        # Check if it's a valid entry (not "Error")
        if title and "error" in title.lower():
            return {"valid": False, "arxiv_id": arxiv_id, "title": None,
                    "published": None, "authors": None, "error": f"arXiv ID not found: {arxiv_id}"}

        return {
            "valid": True,
            "arxiv_id": arxiv_id,
            "title": title,
            "published": published,
            "authors": authors if authors else None,
            "error": None,
        }

    except Exception as e:
        return {"valid": False, "arxiv_id": arxiv_id, "title": None,
                "published": None, "authors": None, "error": str(e)[:200]}
