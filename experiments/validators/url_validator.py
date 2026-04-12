"""URL validator — checks reachability via HEAD request."""

import httpx


def validate_url(url: str) -> dict:
    """Check if a URL is reachable.

    Returns:
        {valid: bool, status_code: int|null, final_url: str|null, error: str|null}
    """
    if not url or not url.strip():
        return {"valid": False, "status_code": None, "final_url": None, "error": "empty URL"}

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        with httpx.Client(timeout=10, follow_redirects=True, verify=False) as client:
            resp = client.head(url)
            # Some servers block HEAD, try GET if 405
            if resp.status_code == 405:
                resp = client.get(url, follow_redirects=True)
            return {
                "valid": resp.status_code < 400,
                "status_code": resp.status_code,
                "final_url": str(resp.url),
                "error": None if resp.status_code < 400 else f"HTTP {resp.status_code}",
            }
    except httpx.TimeoutException:
        return {"valid": False, "status_code": None, "final_url": None, "error": "timeout"}
    except httpx.ConnectError as e:
        return {"valid": False, "status_code": None, "final_url": None, "error": f"connection error: {e}"}
    except Exception as e:
        return {"valid": False, "status_code": None, "final_url": None, "error": str(e)[:200]}
