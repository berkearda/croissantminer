"""The extraction systems of the paper and their shared code.

    helpers.py             model calls, output parsing, the canonical 30 fields   (was scripts/_agentic_helpers.py)
    validate.py            checks an extraction has the 30 fields                 (was validation/validate_extraction.py)
    triage_critique.py     Triage + Critique                                      (was scripts/agentic_v2.py)
    locator_extractor.py   Locator-Extractor                                      (was scripts/agentic_lev.py)
    sections.py            section index of a paper ("phase 0")                   (was scripts/agentic_phase0.py)
    specialists.py         Parallel Specialists, with specialist_prompts.py       (was scripts/multi_agents/agents.py)

The old paths keep small files that point here, so the paper's scripts and commands run unchanged.
Benchmark runs (python scripts/agentic_v2.py ...) need a clone of the repository for the data in data/.
"""
