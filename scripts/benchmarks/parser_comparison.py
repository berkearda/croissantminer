#!/usr/bin/env python3
"""
CroissantMiner — PDF parser head-to-head benchmark.

Compares PyMuPDF (fitz), pypdfium2, and pypdf on the 8 CroissantMiner
benchmark papers. Reports: extraction speed, char count, token count,
and pairwise text similarity.

Output: results/parser_comparison_<date>.md + .json
"""

import hashlib
import json
import re
import statistics
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import fitz  # pymupdf
import pypdf
import pypdfium2 as pdfium
import tiktoken

ROOT = Path(__file__).parent.parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "results"

BENCHMARK_8 = {
    "2012.03411v2.pdf": "MLS",
    "2009.03300v3.pdf": "MMLU",
    "2106.03193v1.pdf": "FLORES",
    "2404.00498v2.pdf": "CIFAR",
    "1405.0312v3.pdf": "MSCOCO",
    "2311.16502v4.pdf": "MMMU",
    "1602.07332v1.pdf": "Visual Genome",
    "2310.02255v3.pdf": "MathVista",
}


def normalize(text: str) -> str:
    """Light post-processing shared across all parsers for fairness."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)  # de-hyphenate
    return text.strip()


def extract_pymupdf(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return normalize(text)


def extract_pypdfium2(pdf_path: Path) -> str:
    pdf = pdfium.PdfDocument(str(pdf_path))
    pages = []
    for page in pdf:
        tp = page.get_textpage()
        pages.append(tp.get_text_bounded())
        tp.close()
        page.close()
    pdf.close()
    return normalize("\n".join(pages))


def extract_pypdf(pdf_path: Path) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    return normalize(text)


PARSERS = {
    "pymupdf": extract_pymupdf,
    "pypdfium2": extract_pypdfium2,
    "pypdf": extract_pypdf,
}


def similarity(a: str, b: str, sample_size: int = 50000) -> float:
    """Char-level similarity. For speed, take head + tail samples for long texts."""
    if not a or not b:
        return 0.0
    if len(a) > sample_size * 2 or len(b) > sample_size * 2:
        a = a[:sample_size] + a[-sample_size:]
        b = b[:sample_size] + b[-sample_size:]
    return SequenceMatcher(None, a, b).ratio()


def gibberish_score(text: str) -> float:
    """Heuristic: fraction of non-ASCII, non-standard-punctuation chars.
    Lower = cleaner. Real academic prose should be < 0.02."""
    if not text:
        return 1.0
    bad = sum(1 for c in text if not (c.isalnum() or c.isspace() or c in ".,;:!?'\"()-[]{}/\\@#$%&*+=<>_|~`"))
    return bad / len(text)


def main():
    OUT.mkdir(exist_ok=True)
    enc = tiktoken.get_encoding("cl100k_base")

    results = []
    pairwise_sims = {"pymupdf-pypdfium2": [], "pymupdf-pypdf": [], "pypdfium2-pypdf": []}

    for fname, label in BENCHMARK_8.items():
        pdf_path = RAW / fname
        if not pdf_path.exists():
            print(f"SKIP {label}: {pdf_path} not found")
            continue
        entry = {"paper": label, "file": fname, "size_kb": round(pdf_path.stat().st_size / 1024)}
        texts = {}

        for pname, fn in PARSERS.items():
            t0 = time.perf_counter()
            try:
                text = fn(pdf_path)
                elapsed = time.perf_counter() - t0
                texts[pname] = text
                entry[pname] = {
                    "chars": len(text),
                    "tokens": len(enc.encode(text)),
                    "time_s": round(elapsed, 3),
                    "sha256_first_5k": hashlib.sha256(text[:5000].encode()).hexdigest()[:16],
                    "gibberish": round(gibberish_score(text), 4),
                }
            except Exception as e:
                entry[pname] = {"error": str(e)[:200]}
                texts[pname] = ""

        # Pairwise similarity
        if all(texts.values()):
            s1 = similarity(texts["pymupdf"], texts["pypdfium2"])
            s2 = similarity(texts["pymupdf"], texts["pypdf"])
            s3 = similarity(texts["pypdfium2"], texts["pypdf"])
            entry["sim_pymupdf_pypdfium2"] = round(s1, 4)
            entry["sim_pymupdf_pypdf"] = round(s2, 4)
            entry["sim_pypdfium2_pypdf"] = round(s3, 4)
            pairwise_sims["pymupdf-pypdfium2"].append(s1)
            pairwise_sims["pymupdf-pypdf"].append(s2)
            pairwise_sims["pypdfium2-pypdf"].append(s3)

        results.append(entry)
        print(f"  {label:<15}  "
              f"pymupdf={entry['pymupdf'].get('chars', 'ERR'):>7} ch  "
              f"pdfium={entry['pypdfium2'].get('chars', 'ERR'):>7} ch  "
              f"pypdf={entry['pypdf'].get('chars', 'ERR'):>7} ch  "
              f"sim μ/p2={entry.get('sim_pymupdf_pypdfium2', 0):.3f}")

    # Aggregate
    def mean_safe(vals):
        return round(statistics.mean(vals), 4) if vals else 0.0

    agg = {
        "parsers": {},
        "pairwise_similarity": {k: mean_safe(v) for k, v in pairwise_sims.items()},
    }
    for p in PARSERS:
        chars = [r[p]["chars"] for r in results if "chars" in r.get(p, {})]
        toks = [r[p]["tokens"] for r in results if "tokens" in r.get(p, {})]
        times = [r[p]["time_s"] for r in results if "time_s" in r.get(p, {})]
        gibs = [r[p]["gibberish"] for r in results if "gibberish" in r.get(p, {})]
        agg["parsers"][p] = {
            "mean_chars": int(statistics.mean(chars)) if chars else 0,
            "mean_tokens": int(statistics.mean(toks)) if toks else 0,
            "mean_time_s": round(statistics.mean(times), 3) if times else 0,
            "mean_gibberish": mean_safe(gibs),
        }

    # Save
    stamp = time.strftime("%Y%m%d")
    json_path = OUT / f"parser_comparison_{stamp}.json"
    with open(json_path, "w") as f:
        json.dump({"results": results, "aggregate": agg}, f, indent=2)

    # Markdown report
    lines = [f"# PDF Parser Comparison — {stamp}", "", "## Per-paper results", "",
             "| Paper | size | pymupdf chars/tok/s | pypdfium2 chars/tok/s | pypdf chars/tok/s | sim μ/p2 | sim μ/pp | sim p2/pp |",
             "|---|---:|---|---|---|---:|---:|---:|"]
    for r in results:
        row = f"| {r['paper']} | {r['size_kb']}KB |"
        for p in PARSERS:
            d = r.get(p, {})
            if "chars" in d:
                row += f" {d['chars']}/{d['tokens']}/{d['time_s']}s |"
            else:
                row += " ERR |"
        row += f" {r.get('sim_pymupdf_pypdfium2', 0):.3f} | {r.get('sim_pymupdf_pypdf', 0):.3f} | {r.get('sim_pypdfium2_pypdf', 0):.3f} |"
        lines.append(row)

    lines += ["", "## Aggregate", ""]
    lines.append("| Parser | mean chars | mean tokens | mean time | mean gibberish |")
    lines.append("|---|---:|---:|---:|---:|")
    for p, d in agg["parsers"].items():
        lines.append(f"| **{p}** | {d['mean_chars']:,} | {d['mean_tokens']:,} | {d['mean_time_s']}s | {d['mean_gibberish']:.4f} |")
    lines += ["", "## Mean pairwise similarity", ""]
    for k, v in agg["pairwise_similarity"].items():
        lines.append(f"- **{k}**: {v:.4f}")

    md_path = OUT / f"parser_comparison_{stamp}.md"
    md_path.write_text("\n".join(lines))
    print(f"\nSaved: {json_path}\n       {md_path}")

    return agg


if __name__ == "__main__":
    main()
