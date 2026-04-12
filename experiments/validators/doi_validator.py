"""DOI validator — resolves DOIs via doi.org content negotiation."""

import re
import httpx


def _extract_doi(text: str) -> str:
    """Extract DOI from a citation string or URL."""
    # DOI URL
    m = re.search(r'doi\.org/(10\.\d{4,}/\S+)', text)
    if m:
        return m.group(1).rstrip(".")
    # Bare DOI
    m = re.search(r'(10\.\d{4,}/\S+)', text)
    if m:
        return m.group(1).rstrip(".")
    return None


def validate_doi(citation: str) -> dict:
    """Resolve a DOI from a citation string.

    Args:
        citation: DOI string, URL, or citation text containing a DOI

    Returns:
        {valid: bool, doi: str|null, resolved_title: str|null,
         resolved_authors: list|null, error: str|null}
    """
    if not citation or not citation.strip():
        return {"valid": False, "doi": None, "resolved_title": None,
                "resolved_authors": None, "error": "empty citation"}

    doi = _extract_doi(citation)
    if not doi:
        return {"valid": False, "doi": None, "resolved_title": None,
                "resolved_authors": None, "error": "no DOI found in citation"}

    try:
        url = f"https://doi.org/{doi}"
        headers = {"Accept": "application/citeproc+json"}
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)

        if resp.status_code == 200:
            data = resp.json()
            authors = []
            for a in data.get("author", []):
                name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                if name:
                    authors.append(name)

            return {
                "valid": True,
                "doi": doi,
                "resolved_title": data.get("title"),
                "resolved_authors": authors if authors else None,
                "error": None,
            }
        else:
            return {"valid": False, "doi": doi, "resolved_title": None,
                    "resolved_authors": None, "error": f"DOI resolution returned {resp.status_code}"}

    except Exception as e:
        return {"valid": False, "doi": doi, "resolved_title": None,
                "resolved_authors": None, "error": str(e)[:200]}
