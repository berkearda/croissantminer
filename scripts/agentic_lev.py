"""Moved to croissantminer/systems/locator_extractor.py. This file keeps the old import path
and command line working for the paper's scripts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root
from croissantminer.systems import locator_extractor as _module  # noqa: E402

if __name__ == "__main__":
    _module.main()
else:
    sys.modules[__name__] = _module
