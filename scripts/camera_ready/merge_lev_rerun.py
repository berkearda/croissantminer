"""Build the camera-ready folders for the two Locator-Extractor Gemini systems.

In the original runs, papers whose API calls failed on quota (HTTP 429) were
saved with empty fields: 36 test papers for Locator-Extractor (Gemini 3.1 Pro)
and 30 for the Gemini 3.1 Pro + GPT-5.4 Mini hybrid (decisions.md 2026-09-26 (5), (6)).
Those papers were re-run with the original code in git worktrees under
../croissantminer_rerun_2026-09/ (ede26c8 for Gemini-only; 0d3107b plus the
working-tree agentic_lev.py for the hybrid v3).

This copies every original file into a NEW folder and replaces only the re-run
papers. The original folders are only read.
A _rerun_manifest.json in each new folder lists what was replaced and why.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RERUN = ROOT.parent / "croissantminer_rerun_2026-09"
EXT = ROOT / "data" / "extractions"
SYSTEMS = {
    # original sid: (worktree output folder, new sid)
    "agentic_lev_gemini_3_1_pro": (
        RERUN / "wt_ede26c8/data/extractions/agentic_lev_gemini_3_1_pro",
        "agentic_lev_gemini_3_1_pro_rerun2609"),
    "agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3": (
        RERUN / "wt_0d3107b/data/extractions/agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3",
        "agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3_rerun2609"),
}


API_ERROR_MARKERS = ("429", "quota", "API error", "Error code", "timed out", "timeout", "Connection")


def failed_calls(meta):
    """Group calls that failed at the API, and whether an LLM locator returned nothing.
    Malformed JSON from the model is the model's own output, kept as in the original
    runs (8 such groups on the hybrid's kept papers), so it does not count here."""
    errs = [g for g, v in (meta.get("group_stats") or {}).items()
            if isinstance(v, dict) and any(t in str(v.get("error", "")) for t in API_ERROR_MARKERS)]
    loc = meta.get("locator") or {}
    return errs, ("model_id" in loc and not loc.get("input_tokens"))


def main():
    papers = json.loads((RERUN / "rerun_papers.json").read_text())
    for sid, (rerun_dir, new_sid) in SYSTEMS.items():
        src, dst = EXT / sid, EXT / new_sid
        if dst.exists():
            sys.exit(f"{dst} exists; refusing to overwrite")
        todo = papers[sid]
        missing = [p for p in todo if not (rerun_dir / f"{p}.json").exists()]
        bad = {p: failed_calls(json.load(open(rerun_dir / f"{p}.json"))["_meta"]) for p in todo if p not in missing}
        bad = {p: v for p, v in bad.items() if v[0] or v[1]}
        if missing or bad:
            sys.exit(f"{sid}: re-run incomplete. missing={missing} still failing={bad}")
        dst.mkdir(parents=True)
        originals = sorted(f for f in src.glob("*.json") if not f.name.startswith("_"))
        for f in originals:
            shutil.copy2(f, dst / f.name)
        for p in todo:
            shutil.copy2(rerun_dir / f"{p}.json", dst / f"{p}.json")
        manifest = {
            "system_id": new_sid,
            "based_on": sid,
            "replaced_papers": todo,
            "reason": "original calls failed on API quota (HTTP 429) or the locator returned nothing; "
                      "re-run 2026-09-26 with the original code (see decisions.md 2026-09-26 (6))",
            "rerun_source": str(rerun_dir),
            "n_files": len(originals),
        }
        (dst / "_rerun_manifest.json").write_text(json.dumps(manifest, indent=1))
        print(f"{new_sid}: {len(originals)} files, {len(todo)} replaced")


if __name__ == "__main__":
    main()
