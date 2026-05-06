#!/usr/bin/env python3
"""Local Croissant 1.1 + RAI validator for the released metadata file.

Required for NeurIPS 2026 E&D submission. The HF Spaces online
validator times out on large datasets per the official FAQ; the
recommended path is to validate locally using the mlcroissant
package.

Run:
    pip install mlcroissant
    python scripts/submission/validate_croissant_local.py

Exits with status 0 on success, 1 on validation failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CROISSANT = ROOT / "data" / "annotations" / "croissant.json"

# E&D track minimal RAI fields per
# https://neurips.cc/Conferences/2026/EvaluationsDatasetsHosting
REQUIRED_RAI = [
    "rai:dataLimitations",
    "rai:dataBiases",
    "rai:personalSensitiveInformation",
    "rai:dataUseCases",
    "rai:dataSocialImpact",
    "rai:isSyntheticData",
    "rai:sourceDatasets",
    "rai:provenanceActivities",
]


def check_required_rai(metadata: dict) -> list[str]:
    """Return list of missing RAI field names."""
    text = json.dumps(metadata).lower()
    missing = []
    for field in REQUIRED_RAI:
        # check if the bare key (without rai: prefix) appears
        bare = field.split(":", 1)[1].lower()
        if bare not in text:
            missing.append(field)
    return missing


def validate_with_mlcroissant(path: Path) -> tuple[bool, str]:
    """Run the mlcroissant validator. Returns (ok, message)."""
    try:
        from mlcroissant import Dataset  # type: ignore
    except ImportError:
        return False, "mlcroissant not installed; run `pip install mlcroissant`"
    except Exception as exc:  # noqa: BLE001
        # mlcroissant has Python 3.10+ requirements; surface that cleanly
        return False, (
            f"mlcroissant import failed ({type(exc).__name__}: {exc}). "
            "If you are on Python 3.8/3.9, run validation in a Python 3.10+ env "
            "(e.g., `pyenv shell 3.11.x && pip install mlcroissant && python scripts/submission/validate_croissant_local.py`)."
        )

    try:
        ds = Dataset(jsonld=str(path))
        return True, f"OK. {len(ds.metadata.record_sets)} record sets, {len(ds.metadata.distribution)} files."
    except Exception as exc:  # noqa: BLE001
        return False, f"mlcroissant raised: {type(exc).__name__}: {exc}"


def main() -> int:
    if not CROISSANT.exists():
        print(f"FAIL: {CROISSANT} not found. Run `python scripts/annotations/build_croissant.py` first.")
        return 1

    metadata = json.loads(CROISSANT.read_text())
    print(f"Loaded {CROISSANT.relative_to(ROOT)} ({CROISSANT.stat().st_size:,} bytes)")

    # 1) Required RAI fields
    missing = check_required_rai(metadata)
    if missing:
        print("FAIL: missing required RAI fields per NeurIPS E&D 2026:")
        for f in missing:
            print(f"  - {f}")
        return 1
    print(f"OK: all {len(REQUIRED_RAI)} mandatory RAI fields present")

    # 2) mlcroissant validation
    ok, msg = validate_with_mlcroissant(CROISSANT)
    if ok:
        print(f"OK: mlcroissant validates the file. {msg}")
    else:
        print(f"FAIL: {msg}")
        return 1

    # 3) Top-level Croissant 1.1 sanity
    ctx = metadata.get("@context", {})
    if not ctx.get("rai"):
        print("FAIL: @context missing 'rai' namespace declaration")
        return 1
    if metadata.get("@type") != "Dataset":
        print(f"FAIL: @type is {metadata.get('@type')!r}, expected 'Dataset'")
        return 1
    print("OK: top-level Croissant 1.1 structure looks correct")

    print("\nValidation passed. The file is ready for NeurIPS E&D submission.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
