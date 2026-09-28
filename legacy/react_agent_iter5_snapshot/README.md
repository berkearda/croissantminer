# Iter 5 snapshot — best-honest configuration

This is the source code as it was for **iteration 5** of dev-set tuning,
which produced the best honest dev result before later iterations:

| Metric | Value |
|---|---|
| Dev mean (GLM-5 judge) | **0.681** |
| Cells scored | 144 (14 papers × ~10 RAI fields) |
| Correct / Partial / Wrong | 69 / 58 / 17 |
| Cost / paper | $0.44 ($0.42 agent + $0.02 audit) |
| Backbone | claude-sonnet-4-6 (agent + audit) |
| Stopping rule | satisfied — three consecutive sub-0.03 deltas |

## Configuration

- `MAX_PAPER_CHARS_IN_CONTEXT = 200_000` — the agent sees the first 200K chars of the cleaned paper text in the initial user message; `search_paper` indexes the full paper for any content past that.
- **Required `evidence_quote` on every `extract_field` call.** Server validates the quote contains a 5-word run that appears verbatim in the **full** paper (case-insensitive, after tokenization). Fabrications are rejected.
- **Single-turn Phase 3 self-review** in the agent — agent re-reads its own (field, value, evidence_quote) records in context, batches `mark_null` for any value that goes beyond what its evidence supports, plus `verify_url` + `lookup_spdx` normalization.
- **Post-extraction LLM audit pass** in `audit.py` — for each non-null RAI field with evidence, an isolated Sonnet 4.6 call sees only `(field, definition, value, evidence_quote)` and decides keep-or-null with a permissive prompt (default-KEEP, only NULL on obvious off-topic / Guardrail A / direct contradiction).

## What this snapshot does NOT include

The iter 7 changes (still in the working tree under `croissantminer/react_agent/`):

- `parse_dataset_view()` — section parser that filters paper to dataset-relevant sections only
- `ToolState.paper_text_agent_view` — separate filtered view for the agent's primary context
- 800K char cap (iter 5 uses 200K)
- Evidence validator restricted to the agent_view rather than the full paper

If you want to revert the live code to this snapshot:

```bash
cp croissantminer/react_agent/_iter5_snapshot/{agent,runner,tools,audit,schemas,__init__}.py croissantminer/react_agent/
```

(Do not import from this directory directly — it's a code archive, not a running module. The snapshot files are fully self-contained when copied back to the parent dir.)

## Saved extractions

Iter 5's 14 dev-paper extractions live at:
- `data/extractions/_best_iter5_freeze_candidate/` (the labelled "best" copy)
- `data/extractions/_archive_iter5_loose_audit_200k_cap/` (the original archive)
