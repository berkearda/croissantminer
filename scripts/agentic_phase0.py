#!/usr/bin/env python3
"""
Agentic Pipeline Phase 0: Document Parsing and Indexing.
Pure text processing, no API calls.

1. Parse paper text via PyMuPDF
2. Detect sections (numbered, unnumbered, common ML headings)
3. Chunk at paragraph level (256-512 tokens) respecting section boundaries
4. Build keyword index for all 30 Croissant fields
5. Save structured JSON per paper + aggregate summary
"""

import json
import re
from pathlib import Path
from collections import defaultdict

from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
from croissantminer.pdf.processor import clean_text as _canonical_clean_text
ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "data" / "agentic" / "phase0"
OUTPUT.mkdir(parents=True, exist_ok=True)

with open(ROOT / "data" / "paper_links.json") as f:
    paper_links = json.load(f)

DUPES = {"CIFAR", "FLORES", "MLS", "MMLU", "MMMU", "MSCOCO", "MathVista", "Visual Genome"}

# ═══════════════════════════════════════════════════════════════
# KEYWORD DEFINITIONS (all 30 fields)
# ═══════════════════════════════════════════════════════════════

FIELD_KEYWORDS = {
    # General (10)
    "name": [
        "dataset", "benchmark", "corpus", "collection", "we present", "we introduce",
        "we release", "we propose", "called", "named", "entitled",
    ],
    "description": [
        "consists of", "contains", "comprising", "composed of", "totaling",
        "includes", "encompasses", "covers", "spans",
    ],
    "url": [
        "github.com", "huggingface", "zenodo", "available at", "download",
        "http://", "https://", "repository", "hosted at", "accessible",
    ],
    "license": [
        "license", "licence", "cc-by", "cc by", "mit license", "apache",
        "creative commons", "gpl", "open source", "copyright", "bsd",
        "public domain", "proprietary", "non-commercial",
    ],
    "creator": [
        "created by", "developed by", "constructed by", "curated by",
        "compiled by", "authored by", "built by", "prepared by",
    ],
    "publisher": [
        "published", "proceedings", "conference", "journal", "workshop",
        "neurips", "icml", "iclr", "acl", "emnlp", "naacl", "cvpr", "iccv",
        "eccv", "aaai", "ijcai", "arxiv", "ieee", "springer",
    ],
    "datePublished": [
        "released in", "published in", "available since", "introduced in",
        "first released", "made public", "released on",
    ],
    "inLanguage": [
        "english", "multilingual", "monolingual", "bilingual", "language",
        "chinese", "french", "german", "spanish", "arabic", "hindi",
        "translated", "translation", "cross-lingual",
    ],
    "citeAs": [
        "cite", "citation", "bibtex", "@article", "@inproceedings",
        "please cite", "when using", "reference",
    ],
    "isLiveDataset": [
        "live", "continuously updated", "maintained", "growing", "evolving",
        "static", "frozen", "snapshot", "fixed version", "will not change",
    ],

    # RAI (20)
    "rai:dataCollection": [
        "collect", "gathered", "obtained", "sourced", "crawl", "scrape",
        "download", "survey", "interview", "acquisition", "assembled",
        "compiled", "harvested", "mined",
    ],
    "rai:dataCollectionType": [
        "crowdsourc", "web scraping", "web crawl", "manual curation",
        "survey", "api", "web api", "experiment", "measurement",
        "secondary data", "document analysis", "user-generated",
        "self-report", "focus group", "passive collection",
    ],
    "rai:dataCollectionMissingData": [
        "missing data", "missing value", "incomplete", "absent", "gap",
        "unavailable", "n/a", "null", "empty field", "not available",
        "data loss", "dropout", "attrition",
    ],
    "rai:dataCollectionRawData": [
        "raw data", "source data", "original data", "underlying data",
        "unprocessed", "original source", "primary source", "obtained from",
    ],
    "rai:dataCollectionTimeframe": [
        "timeframe", "time frame", "period", "duration", "between.*and",
        "from.*to", "start date", "end date", "collected during",
        "months", "years", "weeks", "2018", "2019", "2020", "2021",
        "2022", "2023", "2024", "2025",
    ],
    "rai:dataImputationProtocol": [
        "imput", "filled", "replaced missing", "interpolat", "mean substitut",
        "median substitut", "knn imputation", "mice",
    ],
    "rai:dataManipulationProtocol": [
        "augment", "transform", "manipulat", "modification", "synthetic",
        "oversample", "undersample", "smote", "rotation", "flip",
        "crop", "noise injection", "data augmentation",
    ],
    "rai:dataPreprocessingProtocol": [
        "preprocess", "cleaning", "filtering", "normaliz", "tokeniz",
        "removed", "excluded", "dedup", "deduplication", "lowercas",
        "stemm", "lemmatiz", "stopword", "outlier removal",
    ],
    "rai:dataAnnotationProtocol": [
        "annotat", "label", "tagged", "crowdwork", "crowdsourc",
        "mechanical turk", "mturk", "amt", "prolific", "rater",
        "judge", "assessor", "gold standard", "ground truth",
        "annotation guideline", "codebook", "inter-annotator",
    ],
    "rai:dataAnnotationPlatform": [
        "mechanical turk", "mturk", "amazon", "scale ai", "surge",
        "prolific", "labelbox", "appen", "figure eight", "crowdflower",
        "toloka", "platform", "annotation tool", "labeling tool",
    ],
    "rai:dataAnnotationAnalysis": [
        "inter-annotator", "agreement", "kappa", "fleiss", "cohen",
        "krippendorff", "iaa", "reliability", "consensus", "adjudicat",
        "disagreement", "conflict resolution", "majority vote",
    ],
    "rai:annotationsPerItem": [
        "per item", "per example", "per instance", "per sample",
        "annotations each", "labels each", "redundan", "multiple annotator",
        "three annotator", "two annotator", "five annotator",
    ],
    "rai:annotatorDemographics": [
        "demographic", "annotator background", "worker", "native speaker",
        "qualification", "undergraduate", "graduate", "expert",
        "age", "gender", "location", "education", "experience",
    ],
    "rai:machineAnnotationTools": [
        "automatic", "automated", "model-generated", "gpt", "bert",
        "classifier", "detector", "ocr", "ner", "named entity",
        "sentiment analysis", "machine label", "auto-label",
        "pre-trained", "spacy", "stanza", "nltk",
    ],
    "rai:dataReleaseMaintenancePlan": [
        "maintenance", "version", "update", "deprecat", "roadmap",
        "release plan", "quarterly", "annually", "long-term",
        "will be updated", "future version", "maintained by",
    ],
    "rai:personalSensitiveInformation": [
        "personal", "sensitive", "pii", "personally identifiable",
        "identif", "anonymous", "de-identif", "pseudonym", "consent",
        "gdpr", "privacy", "confidential", "protected", "hipaa",
        "age", "gender", "race", "ethnicity", "religion", "income",
    ],
    "rai:dataSocialImpact": [
        "social impact", "societal", "broader impact", "harmful",
        "benefit", "dual use", "misuse", "ethical implication",
        "consequence", "responsibility", "accountability",
        "downstream effect", "unintended",
    ],
    "rai:dataBiases": [
        "bias", "biased", "fairness", "fair", "demographic", "representation",
        "skew", "imbalance", "underrepresent", "overrepresent",
        "disparity", "equity", "discriminat", "stereotype",
        "systematic error", "sampling bias", "selection bias",
    ],
    "rai:dataLimitations": [
        "limitation", "caveat", "shortcoming", "drawback", "weakness",
        "constrain", "not suitable", "does not", "cannot", "restrict",
        "scope", "out of scope", "future work",
    ],
    "rai:dataUseCases": [
        "use case", "intended use", "application", "training", "evaluation",
        "benchmark", "fine-tun", "testing", "research purpose",
        "not intended for", "suitable for", "designed for",
    ],
}

# ═══════════════════════════════════════════════════════════════
# SECTION DETECTION
# ═══════════════════════════════════════════════════════════════

# Common ML paper section names (case-insensitive matching)
KNOWN_SECTIONS = {
    "abstract", "introduction", "background", "related work", "prior work",
    "motivation", "overview", "problem", "formulation", "task",
    "method", "methodology", "approach", "system", "model", "architecture",
    "pipeline", "framework", "algorithm",
    "dataset", "data", "corpus", "benchmark", "collection", "annotation",
    "experiment", "experimental", "setup", "evaluation", "result",
    "analysis", "ablation", "comparison",
    "discussion", "finding", "insight",
    "limitation", "future work", "conclusion", "summary",
    "ethic", "broader impact", "social impact", "responsible",
    "acknowledgment", "reference", "appendix", "supplement",
}


def detect_sections(text):
    """Detect section headings and return list of {name, char_start, char_end}."""
    lines = text.split("\n")
    sections = []
    char_pos = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        line_start = char_pos
        char_pos += len(line) + 1  # +1 for newline

        if not stripped or len(stripped) > 120:
            continue

        is_section = False
        section_name = stripped

        # Pattern 1: Numbered section "1. Introduction" or "1 Introduction" or "3.2 Dataset"
        m = re.match(r'^(\d+\.?\d*\.?\s+)(.+)$', stripped)
        if m and len(m.group(2)) < 80:
            candidate = m.group(2).strip()
            # Verify it looks like a heading (not a sentence)
            if not candidate.endswith('.') and not candidate.endswith(','):
                is_section = True
                section_name = candidate

        # Pattern 2: ALL CAPS line (common for some formats)
        if not is_section and stripped.isupper() and 3 < len(stripped) < 60:
            is_section = True
            section_name = stripped.title()

        # Pattern 3: Known section name — must be a standalone short line (not a sentence)
        if not is_section and len(stripped) < 60:
            lower = stripped.lower()
            clean = re.sub(r'^\d+[\.\d]*\s*', '', lower).strip()
            # Must START with a known section name (not just contain it mid-sentence)
            for known in KNOWN_SECTIONS:
                if clean == known or clean.startswith(known + " ") or clean.startswith(known + ":"):
                    # Extra check: line should not end with sentence punctuation
                    if not stripped.endswith('.') and not stripped.endswith(',') and not stripped.endswith(';'):
                        is_section = True
                        section_name = stripped
                        break

        # Pattern 4 removed — too aggressive, catches figure captions, equations, etc.

        if is_section:
            # Clean section name
            section_name = re.sub(r'^\d+[\.\d]*\s*', '', section_name).strip()
            if section_name:
                sections.append({
                    "name": section_name,
                    "char_start": line_start,
                })

    # Set char_end for each section
    for i in range(len(sections) - 1):
        sections[i]["char_end"] = sections[i + 1]["char_start"]
    if sections:
        sections[-1]["char_end"] = len(text)

    # Deduplicate consecutive sections with same name
    deduped = []
    for s in sections:
        if not deduped or s["name"].lower() != deduped[-1]["name"].lower():
            deduped.append(s)
        else:
            deduped[-1]["char_end"] = s["char_end"]

    return deduped


# ═══════════════════════════════════════════════════════════════
# CHUNKING
# ═══════════════════════════════════════════════════════════════

def estimate_tokens(text):
    return len(text) // 4


def chunk_text(text, sections, min_tokens=128, max_tokens=512):
    """Split text into chunks respecting section boundaries."""
    if not sections:
        sections = [{"name": "Untitled", "char_start": 0, "char_end": len(text)}]

    chunks = []
    chunk_idx = 0

    for section in sections:
        section_text = text[section["char_start"]:section["char_end"]]
        paragraphs = re.split(r'\n\s*\n|\n(?=[A-Z])', section_text)

        current_chunk = []
        current_tokens = 0
        current_start = section["char_start"]

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_tokens = estimate_tokens(para)

            # If adding this paragraph exceeds max, flush
            if current_tokens + para_tokens > max_tokens and current_tokens >= min_tokens:
                chunk_text_joined = "\n".join(current_chunk)
                chunks.append({
                    "text": chunk_text_joined,
                    "section": section["name"],
                    "chunk_index": chunk_idx,
                    "token_count": current_tokens,
                    "char_start": current_start,
                    "char_end": current_start + len(chunk_text_joined),
                })
                chunk_idx += 1
                current_chunk = []
                current_tokens = 0
                current_start = current_start + len(chunk_text_joined)

            current_chunk.append(para)
            current_tokens += para_tokens

        # Flush remaining
        if current_chunk:
            chunk_text_joined = "\n".join(current_chunk)
            chunks.append({
                "text": chunk_text_joined,
                "section": section["name"],
                "chunk_index": chunk_idx,
                "token_count": current_tokens,
                "char_start": current_start,
                "char_end": current_start + len(chunk_text_joined),
            })
            chunk_idx += 1

    return chunks


# ═══════════════════════════════════════════════════════════════
# KEYWORD INDEX
# ═══════════════════════════════════════════════════════════════

def build_keyword_index(text, sections):
    """Find keyword hits per field, including which sections they appear in."""
    text_lower = text.lower()
    index = {}

    for field, keywords in FIELD_KEYWORDS.items():
        found_keywords = []
        total_hits = 0
        sections_with_hits = set()

        for kw in keywords:
            kw_lower = kw.lower()
            count = text_lower.count(kw_lower)
            if count > 0:
                found_keywords.append(kw)
                total_hits += count
                # Find which sections contain this keyword
                for sec in sections:
                    sec_text = text[sec["char_start"]:sec["char_end"]].lower()
                    if kw_lower in sec_text:
                        sections_with_hits.add(sec["name"])

        index[field] = {
            "keywords_found": found_keywords,
            "total_hits": total_hits,
            "sections_found_in": sorted(sections_with_hits),
        }

    return index


# ═══════════════════════════════════════════════════════════════
# PAPER TEXT LOADING
# ═══════════════════════════════════════════════════════════════

def get_paper_text(ds_id):
    """Load paper text from PDF."""
    # Try direct name
    for name in [f"{ds_id}.pdf"]:
        p = RAW / name
        if p.exists():
            text = _canonical_clean_text(_canonical_extract_text(str(p)))
            return text

    # Try arxiv ID from paper_links
    url = paper_links.get(ds_id, "")
    m = re.search(r'(\d{4}\.\d{4,5})', url)
    if m:
        arxiv = m.group(1)
        for suffix in ["", "v1", "v2", "v3", "v4", "v5"]:
            p = RAW / f"{arxiv}{suffix}.pdf"
            if p.exists():
                text = _canonical_clean_text(_canonical_extract_text(str(p)))
                return text

    return None


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def process_paper(ds_id):
    text = get_paper_text(ds_id)
    if text is None:
        return None

    sections = detect_sections(text)
    chunks = chunk_text(text, sections)
    keyword_index = build_keyword_index(text, sections)

    total_tokens = sum(c["token_count"] for c in chunks)
    if total_tokens < 8000:
        length_cat = "short"
    elif total_tokens < 20000:
        length_cat = "medium"
    else:
        length_cat = "long"

    return {
        "dataset_id": ds_id,
        "chunks": chunks,
        "keyword_hits": keyword_index,
        "paper_stats": {
            "total_tokens": total_tokens,
            "total_chunks": len(chunks),
            "total_chars": len(text),
            "total_sections": len(sections),
            "sections_detected": [s["name"] for s in sections],
            "paper_length_category": length_cat,
            "fields_with_keywords": sum(1 for v in keyword_index.values() if v["keywords_found"]),
        },
    }


def main():
    all_ds = sorted(
        p.parent.name for p in PROCESSED.glob("*/full_pdf_metadata_result.json")
        if p.parent.name not in DUPES
    )
    if not all_ds:
        # Public release: data/processed/ is not shipped, so take the benchmark papers from the
        # dev/test split; their text is read from the PDFs in data/raw/ (scripts/download_papers.py).
        split = json.loads((ROOT / "data" / "agentic" / "dev_test_split.json").read_text())
        all_ds = sorted(set(split["dev"]) | set(split["test"]))
    print(f"Papers to process: {len(all_ds)}")

    # ── Test on 3 ──
    test_ids = ["AI4Math_MathVista", "openai_gsm8k", "rajpurkar_squad"]
    print(f"\n{'='*70}")
    print("VALIDATION: Testing on 3 papers")
    print(f"{'='*70}")

    for ds_id in test_ids:
        result = process_paper(ds_id)
        if result is None:
            print(f"\n  {ds_id}: NO TEXT FOUND")
            continue

        stats = result["paper_stats"]
        print(f"\n  {ds_id}:")
        print(f"    Tokens: {stats['total_tokens']:,} ({stats['paper_length_category']})")
        print(f"    Chunks: {stats['total_chunks']}")
        print(f"    Sections: {stats['total_sections']} — {stats['sections_detected'][:8]}{'...' if len(stats['sections_detected']) > 8 else ''}")
        print(f"    Fields with keywords: {stats['fields_with_keywords']}/30")

        # Validate chunks
        empty = [c for c in result["chunks"] if not c["text"].strip()]
        oversized = [c for c in result["chunks"] if c["token_count"] > 1000]
        print(f"    Validation: {len(empty)} empty chunks, {len(oversized)} oversized (>1000 tokens)")

        # Show top keyword fields
        top_kw = sorted(result["keyword_hits"].items(), key=lambda x: -x[1]["total_hits"])[:5]
        top_str = ", ".join(str(f.split(":")[-1]) + "(" + str(v["total_hits"]) + ")" for f, v in top_kw)
        print(f"    Top keyword fields: {top_str}")

    # ── Full run ──
    print(f"\n{'='*70}")
    print(f"Processing all {len(all_ds)} papers...")
    print(f"{'='*70}")

    success = 0
    failed = 0
    all_stats = []
    field_hit_counts = defaultdict(int)
    length_dist = defaultdict(int)
    section_fail = []

    for i, ds_id in enumerate(all_ds):
        result = process_paper(ds_id)
        if result is None:
            failed += 1
            continue

        out_path = OUTPUT / f"{ds_id}.json"
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        stats = result["paper_stats"]
        all_stats.append(stats)
        length_dist[stats["paper_length_category"]] += 1

        for field, hits in result["keyword_hits"].items():
            if hits["keywords_found"]:
                field_hit_counts[field] += 1

        if stats["total_sections"] == 0:
            section_fail.append(ds_id)

        # Validate
        empty = [c for c in result["chunks"] if not c["text"].strip()]
        oversized = [c for c in result["chunks"] if c["token_count"] > 1000]
        if empty or oversized:
            print(f"  [{i+1}] {ds_id}: {len(empty)} empty, {len(oversized)} oversized")

        success += 1
        if (i + 1) % 25 == 0:
            print(f"  [{i+1}/{len(all_ds)}] {success} OK, {failed} failed")

    print(f"  [{len(all_ds)}/{len(all_ds)}] {success} OK, {failed} failed")

    # ── Summary ──
    total_chunks = sum(s["total_chunks"] for s in all_stats)
    total_tokens = sum(s["total_tokens"] for s in all_stats)
    avg_sections = sum(s["total_sections"] for s in all_stats) / max(len(all_stats), 1)

    print(f"\n{'='*70}")
    print("PHASE 0 SUMMARY")
    print(f"{'='*70}")
    print(f"  Papers processed:    {success}/{len(all_ds)}")
    print(f"  Failed (no PDF):     {failed}")
    print(f"  Total chunks:        {total_chunks:,}")
    print(f"  Total tokens:        {total_tokens:,}")
    print(f"  Avg chunks/paper:    {total_chunks/max(success,1):.0f}")
    print(f"  Avg tokens/paper:    {total_tokens/max(success,1):,.0f}")
    print(f"  Avg sections/paper:  {avg_sections:.1f}")
    print(f"  Section detection failures: {len(section_fail)}")
    if section_fail:
        print(f"    Papers with 0 sections: {section_fail[:5]}{'...' if len(section_fail) > 5 else ''}")
    print(f"  Paper length distribution: {dict(length_dist)}")

    print(f"\n  Per-field keyword hit rate (% of papers with keywords):")
    for field in sorted(FIELD_KEYWORDS.keys()):
        rate = field_hit_counts[field] / max(success, 1) * 100
        short = field.split(":")[-1] if ":" in field else field
        bar = "#" * int(rate / 5)
        print(f"    {short:<30} {rate:>5.1f}% {bar}")

    # Save summary
    summary = {
        "phase": 0,
        "description": "Document Parsing and Indexing",
        "papers_processed": success,
        "papers_failed": failed,
        "total_chunks": total_chunks,
        "total_tokens": total_tokens,
        "avg_chunks_per_paper": round(total_chunks / max(success, 1), 1),
        "avg_tokens_per_paper": round(total_tokens / max(success, 1)),
        "avg_sections_per_paper": round(avg_sections, 1),
        "section_detection_failures": len(section_fail),
        "paper_length_distribution": dict(length_dist),
        "field_keyword_hit_rates": {
            field: round(field_hit_counts[field] / max(success, 1) * 100, 1)
            for field in sorted(FIELD_KEYWORDS.keys())
        },
    }
    summary_path = ROOT / "results" / "agentic_phase0_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Summary saved: {summary_path}")

    # Verify output files
    json_files = list(OUTPUT.glob("*.json"))
    print(f"  Output files: {len(json_files)}/103")


if __name__ == "__main__":
    main()
