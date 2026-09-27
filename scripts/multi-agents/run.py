import argparse
import sys
from pipeline import MultiAgentPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-agent Croissant metadata extraction pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--split",
        choices=["dev", "test"],
        default="test",
        help="Which split to process (default: test)",
    )
    group.add_argument(
        "--id",
        metavar="DATASET_ID",
        help="Process a single paper by its dataset ID",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run specialist agents in parallel instead of sequentially",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-run and overwrite existing outputs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    pipeline = MultiAgentPipeline(
        parallel=args.parallel,
        skip_existing=not args.overwrite,
    )

    if args.id:
        result = pipeline.run_individual_paper(args.id)
        if result is None:
            sys.exit(0)
        fields = result.get("metadata", {})
        non_null = sum(f is not None for f in fields.values())
        print(f"Extracted {non_null}/{len(fields)} non-null fields.")
    else:
        counts = pipeline.run_all_split_papers(args.split)
        if counts["errors"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
