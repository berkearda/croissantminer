#!/usr/bin/env python3
"""T-058: per-paper n-gram overlap against C4 + Pile samples.

For each of the 102 benchmark papers, compute the fraction of 8/13/25-gram
sequences (drawn from the first ~1500 words of paper text) that also appear
in a streaming sample of two known training corpora:

- allenai/c4 (en validation split) -- representative of GPT, Claude, Gemini
  training data
- NeelNanda/pile-10k (Pile sample) -- representative of Llama and most
  open-weight model training data

Output: data/contamination/ngram_overlap.parquet (one row per paper x
corpus x n-gram size) plus a summary memo at
data/contamination/SUMMARY.md.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts._agentic_helpers import get_paper_text  # noqa: E402

OUT_DIR = ROOT / "data" / "contamination"
OUT_PARQUET = OUT_DIR / "ngram_overlap.parquet"
OUT_SUMMARY = OUT_DIR / "SUMMARY.md"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NGRAM_SIZES = (8, 13, 25)
PAPER_WORD_LIMIT = 1500  # first ~1500 words = abstract + intro proxy
HIGH_RISK_THRESHOLD = 0.50  # 50%+ 8-gram overlap = "high contamination risk"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ngram_overlap")


# ── tokenisation + hashing ─────────────────────────────────────────


_WS = re.compile(r"\s+")
_NORM = re.compile(r"[^a-z0-9 ]+")


def normalize(text: str) -> list[str]:
    """Lowercase, strip non-alphanumerics, split on whitespace."""
    text = text.lower()
    text = _NORM.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text.split()


def hash_ngram(ngram: tuple[str, ...]) -> bytes:
    """Compact 16-byte md5 of a space-joined n-gram. 16 bytes keeps the
    set memory bounded even for 25M n-grams (~400 MB)."""
    return hashlib.md5(" ".join(ngram).encode()).digest()


def ngrams(tokens: list[str], n: int):
    if len(tokens) < n:
        return
    for i in range(len(tokens) - n + 1):
        yield tuple(tokens[i:i + n])


# ── corpus side ────────────────────────────────────────────────────


def build_corpus_ngram_set(corpus_name: str, n_docs: int, n_size: int) -> set:
    """Stream `n_docs` documents from `corpus_name`, return the set of
    hashed n-grams of size `n_size` seen across them."""
    import datasets as ds

    log.info("streaming %d docs from %s for %d-grams",
            n_docs, corpus_name, n_size)
    if corpus_name == "c4":
        stream = ds.load_dataset("allenai/c4", "en",
                                 split="validation", streaming=True)
        text_key = "text"
    elif corpus_name == "pile":
        stream = ds.load_dataset("NeelNanda/pile-10k",
                                 split="train", streaming=True)
        text_key = "text"
    elif corpus_name == "arxiv":
        stream = ds.load_dataset("armanc/scientific_papers", "arxiv",
                                 split="train", streaming=True,
                                 trust_remote_code=True)
        text_key = "article"
    else:
        raise SystemExit(f"unknown corpus: {corpus_name}")

    # Per-doc token cap. Our paper-side text is the first 1500 words
    # (PAPER_WORD_LIMIT). A corpus doc only needs its first ~2000 words
    # to catch any 25-gram match against our paper. Capping prevents
    # memory blowup on long arxiv articles (median ~25K tokens).
    DOC_TOKEN_CAP = 3000

    seen: set = set()
    n_docs_used = 0
    for ex in stream:
        if n_docs_used >= n_docs:
            break
        toks = normalize(ex[text_key])[:DOC_TOKEN_CAP]
        if len(toks) < n_size:
            continue
        for ng in ngrams(toks, n_size):
            seen.add(hash_ngram(ng))
        n_docs_used += 1
        if n_docs_used % 1000 == 0:
            log.info("  %s: %d/%d docs, %d %d-grams in set",
                    corpus_name, n_docs_used, n_docs,
                    len(seen), n_size)

    log.info("  %s: built set of %d %d-grams from %d docs",
            corpus_name, len(seen), n_size, n_docs_used)
    return seen


# ── paper side ─────────────────────────────────────────────────────


def load_papers() -> dict[str, str]:
    """Return {paper_id: first PAPER_WORD_LIMIT words of paper text}.
    Uses the canonical `get_paper_text()` helper so the text we check
    matches what the LLMs saw."""
    gold = pd.read_parquet(ROOT / "data" / "annotations" / "gold.parquet")
    paper_ids = sorted(gold["paper_id"].unique())
    log.info("loading text for %d papers", len(paper_ids))

    out: dict[str, str] = {}
    n_missing = 0
    for pid in paper_ids:
        text = get_paper_text(pid)
        if text is None:
            log.warning("  no PDF found for %s", pid)
            n_missing += 1
            continue
        toks = normalize(text)
        out[pid] = " ".join(toks[:PAPER_WORD_LIMIT])

    log.info("  loaded %d papers (%d missing)", len(out), n_missing)
    return out


def paper_ngrams(paper_text: str, n: int) -> set:
    toks = paper_text.split()
    return {hash_ngram(ng) for ng in ngrams(toks, n)}


# ── core ───────────────────────────────────────────────────────────


def compute_overlap(papers: dict[str, str],
                   corpus_name: str,
                   n_docs: int) -> list[dict]:
    """For each (paper, n-gram-size) pair: build the corpus set once
    per n-size, intersect, record overlap fraction."""
    rows: list[dict] = []

    for n_size in NGRAM_SIZES:
        corpus_set = build_corpus_ngram_set(corpus_name, n_docs, n_size)

        for paper_id, paper_text in papers.items():
            paper_set = paper_ngrams(paper_text, n_size)
            if not paper_set:
                continue
            overlap = paper_set & corpus_set
            rows.append({
                "paper_id": paper_id,
                "corpus": corpus_name,
                "n_gram": n_size,
                "n_paper_ngrams": len(paper_set),
                "n_overlapping": len(overlap),
                "overlap_pct": round(len(overlap) / len(paper_set), 4),
            })

        # Free the corpus set before building the next one for n+1.
        del corpus_set

    return rows


def write_summary(df: pd.DataFrame) -> None:
    lines = [
        "# Contamination overlap summary",
        "",
        f"Generated {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M UTC')}.",
        "",
        f"Per-paper 8/13/25-gram overlap of the first {PAPER_WORD_LIMIT} "
        "words of each benchmark paper (after PyPDF2 text extraction) "
        "against streaming samples of three training corpora.",
        "",
        "Note: this is a *lower bound* on contamination. Non-zero overlap "
        "is strong evidence of training-data leakage; zero overlap does "
        "not prove absence (we are sampling fractions of a percent of each "
        "corpus). 25-gram matches are nearly impossible by chance, so any "
        "non-zero count there is a clear contamination flag.",
        "",
        "## Per-corpus aggregate",
        "",
        "| Corpus | n-gram | papers w/ any match | total matches | "
        "max per paper | mean overlap |",
        "|---|---|---|---|---|---|",
    ]
    for (corpus, n), grp in df.groupby(["corpus", "n_gram"]):
        n_papers_hit = (grp["n_overlapping"] > 0).sum()
        n_total = grp["n_overlapping"].sum()
        n_max = grp["n_overlapping"].max()
        mean_pct = grp["overlap_pct"].mean()
        lines.append(f"| {corpus} | {n}-gram | {n_papers_hit}/102 | "
                    f"{n_total} | {n_max} | {mean_pct:.4%} |")

    lines.append("")
    lines.append("## Papers with any non-zero match")
    lines.append("")
    hit = df[df["n_overlapping"] > 0].sort_values(
        ["n_gram", "n_overlapping"], ascending=[False, False])
    if hit.empty:
        lines.append("None.")
    else:
        lines.append("| paper_id | corpus | n-gram | matches | overlap |")
        lines.append("|---|---|---|---|---|")
        for _, row in hit.iterrows():
            lines.append(f"| {row['paper_id']} | {row['corpus']} | "
                        f"{row['n_gram']}-gram | {row['n_overlapping']} | "
                        f"{row['overlap_pct']:.4%} |")

    lines.append("")
    lines.append("## Reading the numbers")
    lines.append("")
    lines.append("- **8-gram matches** are common-phrase noise. Even uncontaminated "
                 "papers can have a few 8-grams matching a corpus by chance "
                 "(generic phrases like 'in this paper we propose').")
    lines.append("- **13-gram matches** are unlikely by chance. Any non-zero "
                 "count flags possible contamination of that paper's prose.")
    lines.append("- **25-gram matches** are essentially impossible without the "
                 "paper text being verbatim in the corpus. Any non-zero "
                 "count is a strong contamination flag.")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append(f"- Paper text: first {PAPER_WORD_LIMIT} words from PyPDF2 "
                "extraction of each paper's source PDF, lowercased and "
                "alphanumeric-normalised.")
    lines.append("- Corpora: arxiv (`armanc/scientific_papers` arxiv subset), "
                "c4 (`allenai/c4` en validation), pile (`NeelNanda/pile-10k`). "
                "First 3,000 normalised tokens of each corpus document.")
    lines.append("- Hashing: md5 truncated to 16 bytes per n-gram.")
    lines.append("- Per cell: `overlap = |paper_ngrams ∩ corpus_ngrams| / "
                "|paper_ngrams|`.")

    OUT_SUMMARY.write_text("\n".join(lines) + "\n")
    log.info("wrote %s", OUT_SUMMARY)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--c4-docs", type=int, default=20000,
                  help="number of C4 documents to stream")
    p.add_argument("--pile-docs", type=int, default=10000,
                  help="number of Pile documents to stream "
                       "(NeelNanda/pile-10k caps at 10000)")
    p.add_argument("--arxiv-docs", type=int, default=20000,
                  help="number of arxiv documents to stream from "
                       "armanc/scientific_papers")
    p.add_argument("--corpora", default="arxiv,c4,pile",
                  help="comma-separated subset of {arxiv, c4, pile}")
    args = p.parse_args()

    papers = load_papers()
    if not papers:
        raise SystemExit("no papers loaded; check data/raw/*.pdf coverage")

    docs_map = {"c4": args.c4_docs, "pile": args.pile_docs,
                "arxiv": args.arxiv_docs}
    all_rows: list[dict] = []
    for corpus in args.corpora.split(","):
        corpus = corpus.strip()
        n_docs = docs_map.get(corpus)
        if n_docs is None or n_docs <= 0:
            log.warning("skipping %s: no doc count", corpus)
            continue
        all_rows.extend(compute_overlap(papers, corpus, n_docs))

    df = pd.DataFrame(all_rows)
    df.to_parquet(OUT_PARQUET, index=False)
    log.info("wrote %d rows to %s", len(df), OUT_PARQUET)

    write_summary(df)


if __name__ == "__main__":
    main()
