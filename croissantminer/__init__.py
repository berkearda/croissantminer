"""CroissantMiner: extract Croissant metadata, including the 20 Responsible AI
fields, from the paper that introduces an ML dataset.

    from croissantminer import extract
    result = extract("paper.pdf")      # the best system in the paper
    result.croissant                   # Croissant 1.1 JSON-LD

Command line: croissantminer --help
"""

__version__ = "0.2.0"

# Loaded on first use, so that `import croissantminer` stays light: the
# extraction systems need the API clients, the earlier prototype needs scipy.
_LAZY = {
    "extract": ("api", "extract"),
    "read_paper": ("api", "read_paper"),
    "Extraction": ("api", "Extraction"),
    "to_croissant": ("croissant", "to_croissant"),
    "validate": ("croissant", "validate"),
    # earlier prototype, kept for existing code
    "SYSTEM_PROMPT": ("config", "SYSTEM_PROMPT"),
    "USER_PROMPT_TEMPLATE": ("config", "USER_PROMPT_TEMPLATE"),
    "METADATA_SCHEMA": ("config", "METADATA_SCHEMA"),
    "extract_metadata_full_pdf": ("extractor", "extract_metadata_full_pdf"),
    "setup_llm_pipeline": ("extractor", "setup_llm_pipeline"),
    "bootstrap_ci": ("metrics", "bootstrap_ci"),
    "mcnemar_test": ("metrics", "mcnemar_test"),
    "cohens_h": ("metrics", "cohens_h"),
    "krippendorff_alpha": ("metrics", "krippendorff_alpha"),
    "fleiss_kappa": ("metrics", "fleiss_kappa"),
}
__all__ = ["__version__", *_LAZY]


def __getattr__(name):
    if name in _LAZY:
        import importlib
        module, attr = _LAZY[name]
        return getattr(importlib.import_module(f".{module}", __name__), attr)
    raise AttributeError(f"module 'croissantminer' has no attribute {name!r}")
