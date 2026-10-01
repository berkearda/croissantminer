"""Moved to croissantminer/systems/validate.py. This file keeps the old import path
working for the paper's scripts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root
from croissantminer.systems import validate as _module  # noqa: E402

sys.modules[__name__] = _module
