"""Single-pass extraction for the PDF parser ablation (Appendix C.3): the paper's canonical prompt on each parser's text.

    python scripts/parser_ablation/parse.py            # first: cache each parser's text
    python scripts/parser_ablation/extract.py          # Sonnet 4.6 and GPT-5.4 on all four parser setups
    python scripts/parser_ablation/score.py            # then: score with the paper's scorer

Each parser's text goes through the paper's preprocessing (clean_text, then UTF-8 sanitising), so the parser is the
only thing that changes between runs. Writes data/extractions/parser_ablation/<model>__<parser>/<paper_id>.json.
Resumable: existing outputs are kept unless --overwrite is given.
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE  # noqa: E402
from croissantminer.pdf.processor import clean_text  # noqa: E402
from scripts._agentic_helpers import (  # noqa: E402
    resolve_backbone, call_llm, parse_json_response, fill_canonical,
    normalize_field_names, estimate_cost, sanitize_utf8,
)

CACHE = ROOT / "data" / "parsed_cache"
OUT = ROOT / "data" / "extractions" / "parser_ablation"
SAMPLE = OUT / "sample30.json"
PARSERS = {"pypdf2": "txt", "pymupdf": "txt", "docling": "md", "docling_full": "md"}
MAX_TOKENS = 8192


def read_parsed(parser, pid):
    fp = CACHE / parser / f"{pid}.{PARSERS[parser]}"
    return fp.read_text(encoding="utf-8", errors="replace") if fp.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="sonnet-4-6,gpt-5.4")
    ap.add_argument("--parsers", default="pypdf2,pymupdf,docling,docling_full")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",")]
    parsers = [p.strip() for p in args.parsers.split(",")]
    papers = json.loads(SAMPLE.read_text())["papers"]
    if args.limit:
        papers = papers[: args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{len(papers)} papers x {len(parsers)} parsers x {len(models)} models "
          f"= {len(papers)*len(parsers)*len(models)} extractions (clean_text applied)\n", flush=True)
    from concurrent.futures import ThreadPoolExecutor
    workers = args.workers

    def do_one(cfg, parser, d, pid):
        fp = d / f"{pid}.json"
        if fp.exists() and not args.overwrite:
            return "skip"
        raw = read_parsed(parser, pid)
        if not raw:
            print(f"  {pid}: no parse", flush=True); return "fail"
        text = sanitize_utf8(clean_text(raw))  # PAPER'S EXACT PREPROCESSING
        try:
            r, usage = call_llm(cfg, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE % text, max_tokens=MAX_TOKENS)
            md = fill_canonical(normalize_field_names(parse_json_response(r)))
        except Exception as e:
            print(f"  {pid}: FAIL {type(e).__name__}: {str(e)[:70]}", flush=True); return "fail"
        md["_meta"] = {"model": cfg["model_id"], "parser": parser, "preprocessing": "clean_text",
                       "cost_usd": estimate_cost(cfg, usage)}
        fp.write_text(json.dumps(md, ensure_ascii=False))
        return "ok"

    for model in models:
        cfg = resolve_backbone(model)
        mslug = model.replace("-", "_").replace(".", "_")
        for parser in parsers:
            d = OUT / f"{mslug}__{parser}"; d.mkdir(parents=True, exist_ok=True)
            print(f"=== {model} x {parser} (workers={workers}) ===", flush=True)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                res = list(pool.map(lambda pid: do_one(cfg, parser, d, pid), papers))
            ok = res.count("ok"); skip = res.count("skip"); fail = res.count("fail")
            print(f"--- {model} x {parser}: ok={ok} skip={skip} fail={fail} ---\n", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
