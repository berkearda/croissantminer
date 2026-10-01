"""Moved to croissantminer/systems/specialist_prompts.py. This file keeps the old import path
working for the paper's scripts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # the repository root
from croissantminer.systems import specialist_prompts as _module  # noqa: E402

sys.modules[__name__] = _module
