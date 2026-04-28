# Contamination overlap summary

Generated 2026-04-28 09:21 UTC.

Per-paper 8/13/25-gram overlap of the first 1500 words of each benchmark paper (after PyPDF2 text extraction) against streaming samples of three training corpora.

Note: this is a *lower bound* on contamination. Non-zero overlap is strong evidence of training-data leakage; zero overlap does not prove absence (we are sampling fractions of a percent of each corpus). 25-gram matches are nearly impossible by chance, so any non-zero count there is a clear contamination flag.

## Per-corpus aggregate

| Corpus | n-gram | papers w/ any match | total matches | max per paper | mean overlap |
|---|---|---|---|---|---|
| arxiv | 8-gram | 23/102 | 55 | 9 | 0.0364% |
| arxiv | 13-gram | 1/102 | 1 | 1 | 0.0007% |
| arxiv | 25-gram | 0/102 | 0 | 0 | 0.0000% |
| c4 | 8-gram | 1/102 | 2 | 2 | 0.0014% |
| c4 | 13-gram | 0/102 | 0 | 0 | 0.0000% |
| c4 | 25-gram | 0/102 | 0 | 0 | 0.0000% |
| pile | 8-gram | 5/102 | 14 | 6 | 0.0094% |
| pile | 13-gram | 0/102 | 0 | 0 | 0.0000% |
| pile | 25-gram | 0/102 | 0 | 0 | 0.0000% |

## Papers with any non-zero match

| paper_id | corpus | n-gram | matches | overlap |
|---|---|---|---|---|
| tanganke_resisc45 | arxiv | 13-gram | 1 | 0.0700% |
| tanganke_resisc45 | arxiv | 8-gram | 9 | 0.6000% |
| MohamedRashad_arabic-books | arxiv | 8-gram | 6 | 0.4200% |
| MohamedRashad_arabic-books | pile | 8-gram | 6 | 0.4200% |
| FLORES_30field | arxiv | 8-gram | 4 | 0.2700% |
| ScaleAI_SWE-bench_Pro | arxiv | 8-gram | 4 | 0.2700% |
| bezirganyan_LUMA | arxiv | 8-gram | 4 | 0.2700% |
| nebius_SWE-rebench | arxiv | 8-gram | 3 | 0.2000% |
| FLORES_30field | pile | 8-gram | 3 | 0.2000% |
| nebius_SWE-rebench | pile | 8-gram | 3 | 0.2000% |
| CIFAR_30field | arxiv | 8-gram | 2 | 0.1300% |
| IGNF_PASTIS-HD | arxiv | 8-gram | 2 | 0.1300% |
| Idavidrein_gpqa | arxiv | 8-gram | 2 | 0.1400% |
| Visual_Genome_30field | arxiv | 8-gram | 2 | 0.1300% |
| WINGNUS_ACL-OCL | arxiv | 8-gram | 2 | 0.1300% |
| allenai_ai2_arc | arxiv | 8-gram | 2 | 0.1300% |
| allenai_sciq | arxiv | 8-gram | 2 | 0.1300% |
| tanganke_dtd | arxiv | 8-gram | 2 | 0.1300% |
| allenai_winogrande | c4 | 8-gram | 2 | 0.1400% |
| Rowan_hellaswag | arxiv | 8-gram | 1 | 0.0700% |
| allenai_math_qa | arxiv | 8-gram | 1 | 0.0700% |
| allenai_winogrande | arxiv | 8-gram | 1 | 0.0700% |
| cimec_lambada | arxiv | 8-gram | 1 | 0.0700% |
| google_IFEval | arxiv | 8-gram | 1 | 0.0700% |
| google_xtreme_s | arxiv | 8-gram | 1 | 0.0700% |
| lmms-lab_ChartQA | arxiv | 8-gram | 1 | 0.0700% |
| rajpurkar_squad | arxiv | 8-gram | 1 | 0.0700% |
| ucla-contextual_contextual_test | arxiv | 8-gram | 1 | 0.0700% |
| callanwu_WebWalkerQA | pile | 8-gram | 1 | 0.0700% |
| tanganke_resisc45 | pile | 8-gram | 1 | 0.0700% |

## Reading the numbers

- **8-gram matches** are common-phrase noise. Even uncontaminated papers can have a few 8-grams matching a corpus by chance (generic phrases like 'in this paper we propose').
- **13-gram matches** are unlikely by chance. Any non-zero count flags possible contamination of that paper's prose.
- **25-gram matches** are essentially impossible without the paper text being verbatim in the corpus. Any non-zero count is a strong contamination flag.

## Methodology

- Paper text: first 1500 words from PyPDF2 extraction of each paper's source PDF, lowercased and alphanumeric-normalised.
- Corpora: arxiv (`armanc/scientific_papers` arxiv subset), c4 (`allenai/c4` en validation), pile (`NeelNanda/pile-10k`). First 3,000 normalised tokens of each corpus document.
- Hashing: md5 truncated to 16 bytes per n-gram.
- Per cell: `overlap = |paper_ngrams ∩ corpus_ngrams| / |paper_ngrams|`.
