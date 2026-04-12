"""License validator — checks against SPDX license list with fuzzy matching."""

import json
import re
from pathlib import Path

import httpx

CACHE_PATH = Path(__file__).parent / "_spdx_cache.json"
SPDX_URL = "https://raw.githubusercontent.com/spdx/license-list-data/main/json/licenses.json"

# Common aliases not in SPDX but frequently seen in papers
ALIASES = {
    "mit license": "MIT",
    "the mit license": "MIT",
    "mit": "MIT",
    "apache 2.0": "Apache-2.0",
    "apache-2.0 license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "gpl": "GPL-3.0-only",
    "gpl-3.0": "GPL-3.0-only",
    "gplv3": "GPL-3.0-only",
    "gpl-2.0": "GPL-2.0-only",
    "bsd": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "cc0": "CC0-1.0",
    "cc0 1.0": "CC0-1.0",
    "public domain": "CC0-1.0",
    "cc by 4.0": "CC-BY-4.0",
    "cc-by-4.0": "CC-BY-4.0",
    "cc by-4.0": "CC-BY-4.0",
    "creative commons 4.0": "CC-BY-4.0",
    "creative commons attribution 4.0": "CC-BY-4.0",
    "creative commons attribution 4.0 international": "CC-BY-4.0",
    "cc by-sa 4.0": "CC-BY-SA-4.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0",
    "creative commons attribution-sharealike 4.0": "CC-BY-SA-4.0",
    "cc by-nc 4.0": "CC-BY-NC-4.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0",
    "creative commons attribution-noncommercial 4.0": "CC-BY-NC-4.0",
    "cc by-nc-sa 4.0": "CC-BY-NC-SA-4.0",
    "cc-by-nc-sa-4.0": "CC-BY-NC-SA-4.0",
    "cc by 3.0": "CC-BY-3.0",
    "cc-by-3.0": "CC-BY-3.0",
}


def _load_spdx() -> dict:
    """Load SPDX license list, caching locally."""
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)

    try:
        resp = httpx.get(SPDX_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Build lookup: lowercased name/id → spdx_id
        lookup = {}
        for lic in data.get("licenses", []):
            lid = lic["licenseId"]
            lookup[lid.lower()] = lid
            lookup[lic["name"].lower()] = lid
        with open(CACHE_PATH, "w") as f:
            json.dump(lookup, f)
        return lookup
    except Exception:
        # Fallback: return aliases only
        return {v.lower(): v for v in set(ALIASES.values())}


def validate_license(license_str: str) -> dict:
    """Check if a license string maps to a valid SPDX identifier.

    Returns:
        {valid: bool, spdx_id: str|null, suggestion: str|null}
    """
    if not license_str or not license_str.strip():
        return {"valid": False, "spdx_id": None, "suggestion": None}

    raw = license_str.strip()
    normalized = raw.lower().strip()

    # Strip URLs
    normalized = re.sub(r'https?://\S+', '', normalized).strip()

    # Check aliases first (most common)
    if normalized in ALIASES:
        spdx = ALIASES[normalized]
        return {"valid": True, "spdx_id": spdx, "suggestion": None}

    # Check SPDX list
    spdx_lookup = _load_spdx()
    if normalized in spdx_lookup:
        return {"valid": True, "spdx_id": spdx_lookup[normalized], "suggestion": None}

    # CC URL pattern (check before fuzzy alias matching)
    cc_match = re.search(r'creativecommons\.org/licenses?/([\w-]+)/([\d.]+)', raw.lower())
    if cc_match:
        spdx = f"CC-{cc_match.group(1).upper()}-{cc_match.group(2)}"
        return {"valid": True, "spdx_id": spdx, "suggestion": f"Extracted from URL: {spdx}"}

    # Fuzzy: check if any known key is a substring (only for longer matches)
    for known, spdx_id in sorted(ALIASES.items(), key=lambda x: -len(x[0])):
        if len(known) >= 3 and (known in normalized or normalized in known):
            return {"valid": True, "spdx_id": spdx_id,
                    "suggestion": f'"{raw}" matched as {spdx_id}'}
    if cc_match:
        spdx = f"CC-{cc_match.group(1).upper()}-{cc_match.group(2)}"
        return {"valid": True, "spdx_id": spdx, "suggestion": f"Extracted from URL: {spdx}"}

    return {
        "valid": False,
        "spdx_id": None,
        "suggestion": f'"{raw}" is not a recognized SPDX identifier. '
                      f"Common licenses: MIT, Apache-2.0, CC-BY-4.0, CC-BY-SA-4.0, GPL-3.0-only",
    }
