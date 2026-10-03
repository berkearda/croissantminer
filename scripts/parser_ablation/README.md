# PDF parser ablation

Code and results for the PDF parser ablation in the paper (Appendix C.3, Table 8): does a better PDF parser than
PyPDF2 improve extraction? Single-pass extraction with the paper's canonical prompt, on 30 test papers sampled at
random (seed 42, `data/extractions/parser_ablation/sample30.json`), with two models and four parser setups:

| Parser | Backend in `croissantminer/pdf/reader.py` |
|---|---|
| PyPDF2 (the paper's pipeline) | `pypdf2` |
| PyMuPDF | `pymupdf` |
| Docling, full export: body text, page headers/footers, text inside figures | `docling_full` |
| Docling, default export: body text only | `docling` |

Only the parser changes: each parser's text goes through the paper's preprocessing (`clean_text`, UTF-8 sanitising)
and the same prompt, models (Claude Sonnet 4.6, GPT-5.4) and scorer.

## Run

```bash
pip install pymupdf docling                 # only needed for this ablation
python scripts/parser_ablation/parse.py     # cache each parser's text in data/parsed_cache/
python scripts/parser_ablation/extract.py   # 8 runs x 30 papers, needs ANTHROPIC_API_KEY and OPENAI_API_KEY
python scripts/parser_ablation/score.py     # writes results/parser_ablation/
```

The outputs of the eight runs are in `data/extractions/parser_ablation/<model>__<parser>/`, so `score.py` works
without re-running anything. It uses the paper's scorer (`scripts/figures/build_test88_headline_table.py`) unchanged:
rules for the 10 core fields, and for the 20 Responsible AI fields the stored GLM-5 verdicts in
`data/judged/parser_ablation_glm5_2026-09-26.parquet`. All eight runs were judged in one session (GLM-5 on DeepInfra,
26 September 2026), so compare the runs with each other, not with the main results table.

## Results

`results/parser_ablation/scores.csv` (per-field scores in `per_field.csv`):

| Model | Parser | Papers | Core | RAI | Composite |
|---|---|---|---|---|---|
| Sonnet 4.6 | PyPDF2 | 30 | 0.773 | 0.468 | 0.570 |
| Sonnet 4.6 | PyMuPDF | 30 | 0.760 | 0.466 | 0.564 |
| Sonnet 4.6 | Docling, full export | 29 | 0.752 | 0.461 | 0.558 |
| Sonnet 4.6 | Docling, body only | 29 | 0.680 | 0.472 | 0.541 |
| GPT-5.4 | PyPDF2 | 30 | 0.671 | 0.466 | 0.534 |
| GPT-5.4 | PyMuPDF | 30 | 0.672 | 0.476 | 0.543 |
| GPT-5.4 | Docling, full export | 30 | 0.659 | 0.476 | 0.539 |
| GPT-5.4 | Docling, body only | 30 | 0.557 | 0.505 | 0.523 |

The parser makes little difference once Docling's full text is exported. Docling's default export drops the page
headers and footers, where papers usually print the venue and year, which costs about 0.1 core, almost all on
`sc:datePublished` and `cr:citeAs`.

**Sonnet 4.6 with Docling covers 29 papers.** One paper (`uoft-cs_cifar100`, a 2009 technical report) uses legacy
Type 3 bitmap fonts without a Unicode map. Docling's default parser resolves their glyph names as ZapfDingbats symbols,
so the text comes out letter-substituted (Docling's pdfium backend reads it correctly), and Sonnet 4.6 refuses the
input. GPT-5.4 decodes it.
