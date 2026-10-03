"""Parse the 30 sampled papers of the PDF parser ablation with each parser and cache the text.

    pip install pymupdf docling          # only needed here
    python scripts/parser_ablation/parse.py
    python scripts/parser_ablation/parse.py --parsers docling_full --overwrite

Writes data/parsed_cache/<parser>/<paper_id>.txt (Markdown .md for Docling). Resumable: papers already cached are
skipped. Docling runs its layout model on the CPU and takes a few minutes for the 30 papers.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from croissantminer.pdf.reader import extract_text_from_pdf  # noqa: E402

SAMPLE = ROOT / "data" / "extractions" / "parser_ablation" / "sample30.json"
CACHE = ROOT / "data" / "parsed_cache"
SUFFIX = {"pypdf2": "txt", "pymupdf": "txt", "docling": "md", "docling_full": "md"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--parsers", default=",".join(SUFFIX), help=f"comma-separated, from: {', '.join(SUFFIX)}")
    ap.add_argument("--overwrite", action="store_true", help="parse again even if cached")
    args = ap.parse_args()
    papers = json.loads(SAMPLE.read_text())["papers"]
    for parser in args.parsers.split(","):
        out = CACHE / parser
        out.mkdir(parents=True, exist_ok=True)
        done = failed = 0
        for pid in papers:
            fp = out / f"{pid}.{SUFFIX[parser]}"
            if fp.exists() and not args.overwrite:
                continue
            text = extract_text_from_pdf(ROOT / "data" / "raw" / f"{pid}.pdf", backend=parser)
            if text:
                fp.write_text(text, encoding="utf-8")
                done += 1
            else:
                failed += 1
        print(f"{parser}: parsed {done}, failed {failed}, cached in {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
