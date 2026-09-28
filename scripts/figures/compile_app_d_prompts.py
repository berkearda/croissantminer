#!/usr/bin/env python3
"""Extract every prompt template into a single App D markdown file.

Imports each module and pulls the prompt string constants. Runs once,
no test-time side effects.

Output: docs/app_d_prompt_templates.md
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

OUT = ROOT / 'docs' / 'app_d_prompt_templates.md'


def section(title: str, body: str, lang: str = 'text') -> str:
    return f"\n## {title}\n\n```{lang}\n{body.strip()}\n```\n"


def main():
    parts = ["# App D — Prompt Templates\n",
             "Compiled 2026-05-02. All prompts used by the systems benchmarked in §5.\n"]

    # -- Canonical extraction prompt (single-pass, ReAct system message) --
    try:
        from croissantminer.config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
        parts.append(section('D.1 Canonical extraction prompt (single-pass + ReAct)', SYSTEM_PROMPT))
        parts.append(section('D.1b User prompt template (single-pass)', USER_PROMPT_TEMPLATE))
    except Exception as e:
        parts.append(f'\n## D.1 (failed to import: {e})\n')

    # -- V2 multi-agent prompts (5 specialists + critique) --
    try:
        import importlib
        v2_mod = importlib.import_module('scripts.agentic_v2')
        added = False
        for attr in dir(v2_mod):
            if 'PROMPT' in attr.upper() or 'SYSTEM' in attr.upper():
                val = getattr(v2_mod, attr)
                if isinstance(val, str) and len(val) > 200:
                    parts.append(section(f'D.2 V2 — {attr}', val))
                    added = True
        if not added:
            parts.append('\n## D.2 V2 — (no prompt constants found at module level; see scripts/agentic_v2.py for inline prompts)\n')
    except Exception as e:
        parts.append(f'\n## D.2 V2 (failed to import: {e})\n')

    # -- LEV prompts (locator + extractor) --
    try:
        import importlib
        lev_mod = importlib.import_module('scripts.agentic_lev')
        added = False
        for attr in dir(lev_mod):
            if 'PROMPT' in attr.upper() or 'SYSTEM' in attr.upper():
                val = getattr(lev_mod, attr)
                if isinstance(val, str) and len(val) > 200:
                    parts.append(section(f'D.3 LEV — {attr}', val))
                    added = True
        if not added:
            parts.append('\n## D.3 LEV — (no prompt constants found at module level; inline)\n')
    except Exception as e:
        parts.append(f'\n## D.3 LEV (failed to import: {e})\n')

    # -- Paul Specialist (5 specialists + ANTI_NULL_PREFIX) --
    try:
        from scripts.multi_agents import prompts as ma_prompts
        added = False
        for attr in dir(ma_prompts):
            if attr.startswith('_'):
                continue
            val = getattr(ma_prompts, attr)
            if isinstance(val, str) and len(val) > 100:
                parts.append(section(f'D.4 Multi-agent specialist (Paul) — {attr}', val))
                added = True
        if not added:
            parts.append('\n## D.4 Multi-agent specialist — (no string constants found)\n')
    except Exception as e:
        parts.append(f'\n## D.4 Multi-agent specialist (failed to import: {e})\n')

    # -- ReAct agent prompts (system, tool defs, ANTI_NULL_PREFIX_FOR_REACT, VERIFY_CORRECT_TURN) --
    try:
        from croissantminer.react_agent import agent as react_mod
        for attr in [
            'SYSTEM_TEMPLATE', 'SYSTEM_PROMPT', 'USER_TEMPLATE',
            'PHASE_1_TEMPLATE', 'PHASE_2_TEMPLATE', 'PHASE_3_TEMPLATE',
            'ANTI_NULL_PREFIX_FOR_REACT', 'VERIFY_CORRECT_TURN',
        ]:
            if hasattr(react_mod, attr):
                val = getattr(react_mod, attr)
                if isinstance(val, str) and len(val) > 100:
                    parts.append(section(f'D.5 ReAct — {attr}', val))
    except Exception as e:
        parts.append(f'\n## D.5 ReAct (failed to import: {e})\n')

    # -- ReAct tool definitions --
    try:
        from croissantminer.react_agent import tools as react_tools
        for attr in dir(react_tools):
            if attr.upper() == attr and not attr.startswith('_'):
                val = getattr(react_tools, attr)
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    import json as _json
                    parts.append(section(f'D.5b ReAct tool schema — {attr}', _json.dumps(val, indent=2), lang='json'))
    except Exception as e:
        parts.append(f'\n## D.5b ReAct tools (failed to import: {e})\n')

    # -- Judge prompt (GLM-5) --
    try:
        from evaluation import run_judge_ensemble as judge_mod
        for attr in ['JUDGE_SYSTEM_PROMPT', 'SYSTEM_PROMPT', 'JUDGE_USER_TEMPLATE',
                     'USER_TEMPLATE', 'RUBRIC', 'JUDGE_RUBRIC']:
            if hasattr(judge_mod, attr):
                val = getattr(judge_mod, attr)
                if isinstance(val, str) and len(val) > 100:
                    parts.append(section(f'D.6 GLM-5 judge — {attr}', val))
    except Exception as e:
        parts.append(f'\n## D.6 Judge (failed to import: {e})\n')

    out_text = '\n'.join(parts)
    OUT.write_text(out_text)
    n_sections = out_text.count('\n## ')
    print(f'wrote {OUT.relative_to(ROOT)} ({len(out_text)//1024} KB, {n_sections} sections)')


if __name__ == '__main__':
    main()
