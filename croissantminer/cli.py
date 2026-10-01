"""Command line: croissantminer extract | methods | validate"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from pathlib import Path

from . import __version__

DRAFT_NOTE = "These are drafts by a language model: check each value against the paper before publishing."


def _err(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


def _method_rows() -> list[tuple[str, ...]]:
    from . import methods
    from .api import KEY_VARIABLES, METHOD_NAMES
    rows = []
    for name, key in METHOD_NAMES.items():
        m = methods.METHODS_BY_KEY[key]
        rows.append((name, m.label.split(" · ", 1)[1], f"{m.paper_score:.3f}",
                     m.typical.replace(" ", " "), KEY_VARIABLES[m.provider]))
    return rows


def cmd_methods(args) -> int:
    header = ("method", "model", "score in the paper", "usual time", "API key")
    rows = [header] + _method_rows()
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    for i, r in enumerate(rows):
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
        if i == 0:
            print("  ".join("-" * w for w in widths))
    print("\nThe score is the composite over all 30 fields on the paper's 88 test papers (higher is better).")
    print("single-pass is the default: the best system in the paper and the cheapest (a few US cents per paper).")
    return 0


def _print_check(passed, messages) -> None:
    if passed is None:
        print(f"Check:  not run ({messages[0]})")
    elif passed:
        n = len(messages)
        print("Check:  passes the mlcroissant validator"
              + (f" ({n} recommended {'property' if n == 1 else 'properties'} missing)" if n else ""))
    else:
        print("Check:  the mlcroissant validator reports problems:")
        for m in messages:
            print(f"  - {m}")


def _print_merge(source: str, added: list[str], kept: list[str]) -> None:
    rai = sum(k.startswith("rai:") for k in added)
    print(f"Merged: added {len(added)} fields ({rai} Responsible AI) to the Croissant file of {source}"
          + (f"; kept its own {', '.join(kept)}" if kept else ""))


def cmd_extract(args) -> int:
    from .api import METHOD_NAMES, MissingKey, extract
    from .croissant import _HF_ID, load, merge, validate
    if args.method not in METHOD_NAMES:
        return _err(f"unknown method {args.method!r}; see `croissantminer methods`")
    paper = Path(args.paper)
    if not paper.is_file():
        return _err(f"no such file: {paper}")
    host = None
    if args.merge_into:  # fetched first, so a wrong id fails before any API call
        try:
            host = load(args.merge_into)
        except Exception as e:  # noqa: BLE001
            return _err(f"cannot read the Croissant file to merge into: {e}")
        if not args.hf_id and _HF_ID.match(args.merge_into) and not Path(args.merge_into).exists():
            args.hf_id = args.merge_into
    out = Path(args.output) if args.output else Path(f"{paper.stem}.croissant.json")
    from . import methods
    label = methods.METHODS_BY_KEY[METHOD_NAMES[args.method]].label
    print(f"Extracting with {label} "
          f"(usually {methods.METHODS_BY_KEY[METHOD_NAMES[args.method]].typical.replace(chr(160), ' ')})...",
          file=sys.stderr)
    if not args.verbose:
        os.environ.setdefault("TQDM_DISABLE", "1")
    quiet = contextlib.nullcontext() if args.verbose else contextlib.redirect_stdout(io.StringIO())
    try:
        with quiet:
            result = extract(paper, args.method, hf_dataset_id=args.hf_id, dataset_card=args.card)
    except MissingKey as e:
        return _err(str(e))
    except methods.InvalidKey:
        return _err("the provider rejected the API key")
    except Exception as e:  # noqa: BLE001 - report any failure of the systems plainly
        return _err(f"extraction failed: {type(e).__name__}: {str(e)[:300]}")
    croissant = result.croissant
    if host is not None:
        croissant, added, kept = merge(host, croissant)
    out.write_text(json.dumps(croissant, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.fields:
        Path(args.fields).write_text(json.dumps({
            "paper": str(paper), "method": result.method, "fields": result.fields, "evidence": result.evidence,
            "null_reasons": result.null_reasons, "cost_usd": result.cost_usd, "elapsed_s": round(result.elapsed_s, 1),
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    cost = f", about ${result.cost_usd:.2f}" if result.cost_usd else ""
    print(f"{result.summary()} with {result.method} in {result.elapsed_s:.0f} s{cost}.")
    if result.missing:
        print("Not found: " + ", ".join(result.missing))
    if host is not None:
        _print_merge(args.merge_into, added, kept)
    print(f"Wrote:  {out}" + (" (Croissant 1.1)" if host is None else "")
          + (f" and {args.fields} (values with evidence)" if args.fields else ""))
    if not args.no_validate:
        _print_check(*validate(croissant))
    print(DRAFT_NOTE)
    return 0


def cmd_merge(args) -> int:
    from .croissant import load, merge, validate
    try:
        host, ours = load(args.host), load(args.extracted)
    except Exception as e:  # noqa: BLE001
        return _err(str(e))
    merged, added, kept = merge(host, ours)
    out = Path(args.output)
    out.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _print_merge(args.host, added, kept)
    print(f"Wrote:  {out}")
    if not args.no_validate:
        passed, messages = validate(merged)
        _print_check(passed, messages)
    return 0


def cmd_validate(args) -> int:
    from .croissant import validate
    try:
        croissant = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _err(f"cannot read {args.file}: {e}")
    passed, messages = validate(croissant)
    _print_check(passed, messages)
    return 2 if passed is None else (0 if passed else 1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="croissantminer",
        description="Extract Croissant metadata, including the Responsible AI fields, from ML dataset papers.")
    p.add_argument("--version", action="version", version=f"croissantminer {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("extract", help="extract the metadata of one paper and write a Croissant file")
    e.add_argument("paper", help="the paper: a PDF, text or Markdown file")
    e.add_argument("-o", "--output", help="Croissant file to write (default: <paper name>.croissant.json)")
    e.add_argument("-m", "--method", default="single-pass",
                   help="extraction system, see `croissantminer methods` (default: single-pass)")
    e.add_argument("--hf-id", metavar="ORG/NAME", help="the dataset's Hugging Face id (lets the agentic "
                   "methods check the license and URL)")
    e.add_argument("--card", metavar="FILE", help="dataset card or README to read together with the paper")
    e.add_argument("--fields", metavar="FILE", help="also write the extracted values with their evidence as JSON")
    e.add_argument("--merge-into", metavar="SOURCE", help="add the extracted fields to an existing Croissant file: "
                   "a Hugging Face dataset id (org/name), a URL or a path; see `croissantminer merge`")
    e.add_argument("--no-validate", action="store_true", help="skip the mlcroissant check")
    e.add_argument("-v", "--verbose", action="store_true", help="show the systems' own progress output")
    e.set_defaults(func=cmd_extract)

    g = sub.add_parser("merge", help="add extracted fields to the Croissant file of a data host (Hugging Face, "
                       "Kaggle, OpenML or a local file); the host's own values are kept")
    g.add_argument("host", help="Hugging Face dataset id (org/name), URL or path of the host's Croissant file")
    g.add_argument("extracted", help="the file written by `croissantminer extract`")
    g.add_argument("-o", "--output", default="croissant_with_rai.json", help="default: croissant_with_rai.json")
    g.add_argument("--no-validate", action="store_true", help="skip the mlcroissant check")
    g.set_defaults(func=cmd_merge)

    m = sub.add_parser("methods", help="list the extraction systems with their scores in the paper")
    m.set_defaults(func=cmd_methods)

    v = sub.add_parser("validate", help="check a Croissant file with mlcroissant")
    v.add_argument("file")
    v.set_defaults(func=cmd_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ImportError as e:  # installed without the repository's benchmark code
        return _err(str(e))


if __name__ == "__main__":
    sys.exit(main())
