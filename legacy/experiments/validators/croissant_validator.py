"""Croissant JSON-LD validator — checks structural validity of the output.

Note: Full mlcroissant validation requires the package to be installed.
This provides a lightweight structural check as fallback.
"""

import json
from typing import Dict, List

# Required Croissant JSON-LD structure
REQUIRED_CONTEXT_KEYS = {"@language", "@vocab"}
REQUIRED_TOP_LEVEL = {"@context", "@type", "name"}


def validate_croissant_jsonld(jsonld: dict) -> dict:
    """Validate a Croissant JSON-LD document.

    Args:
        jsonld: The JSON-LD dict

    Returns:
        {valid: bool, errors: list[str], warnings: list[str]}
    """
    errors = []
    warnings = []

    if not isinstance(jsonld, dict):
        return {"valid": False, "errors": ["Not a JSON object"], "warnings": []}

    # Check @context
    ctx = jsonld.get("@context")
    if not ctx:
        errors.append("Missing @context")
    elif isinstance(ctx, dict):
        for key in REQUIRED_CONTEXT_KEYS:
            if key not in ctx:
                warnings.append(f"@context missing '{key}'")

    # Check @type
    dtype = jsonld.get("@type")
    if not dtype:
        errors.append("Missing @type")
    elif "Dataset" not in str(dtype):
        warnings.append(f"@type is '{dtype}', expected '*Dataset*'")

    # Check name
    if not jsonld.get("name"):
        errors.append("Missing 'name' field")

    # Check for RAI metadata block
    rai = jsonld.get("rai:responsibleAIMetadata")
    if rai and isinstance(rai, dict):
        if "@type" not in rai:
            warnings.append("rai:responsibleAIMetadata missing @type")
    else:
        warnings.append("No rai:responsibleAIMetadata block")

    # Try mlcroissant if available
    try:
        import mlcroissant
        # mlcroissant expects a file; write to temp
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(jsonld, f)
            tmp_path = f.name
        try:
            ds = mlcroissant.Dataset(tmp_path)
            # If we get here without exception, it's valid
        except Exception as e:
            errors.append(f"mlcroissant: {str(e)[:200]}")
        finally:
            import os
            os.unlink(tmp_path)
    except ImportError:
        warnings.append("mlcroissant not installed, using structural check only")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
