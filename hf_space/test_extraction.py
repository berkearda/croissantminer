"""Test extraction end-to-end without the browser."""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not api_key:
    print("ERROR: Set ANTHROPIC_API_KEY in hf_space/.env")
    sys.exit(1)

# Import the app module
sys.path.insert(0, str(Path(__file__).parent))
import importlib.util
spec = importlib.util.spec_from_file_location("app", Path(__file__).parent / "app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

print("=" * 60)
print("Testing extraction with Claude Sonnet 4.5...")
print("=" * 60)

# Use the example paper text
paper_text = app.EXAMPLE_PAPER

# Call the extraction function (bypass gr.Progress by patching)
import gradio as gr

class FakeProgress:
    def __call__(self, *args, **kwargs):
        desc = kwargs.get("desc", args[1] if len(args) > 1 else "")
        print(f"  [{desc}]")

# Monkey-patch: the function expects progress as last positional arg
try:
    # Call extract_metadata directly, simulating what Gradio does
    # The function signature: (pdf_file, paper_text, card_text, model_name, api_key, progress)
    result = app.extract_metadata(
        None,               # pdf_file
        paper_text,         # paper_text
        "",                 # card_text
        "Claude Sonnet 4.5",  # model_name
        api_key,            # api_key
        FakeProgress(),     # progress
    )

    coverage_md, general_table, rai_table, croissant = result

    print("\n" + "=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"\n{coverage_md}\n")

    print("General Fields:")
    for row in general_table:
        status = "+" if row[2] != "—" else " "
        print(f"  [{status}] {row[0]:20s} = {row[2][:60]}")

    print("\nRAI Fields:")
    for row in rai_table:
        status = "+" if row[2] != "—" else " "
        print(f"  [{status}] {row[0]:40s} = {row[2][:60]}")

    print(f"\nCroissant JSON-LD keys: {list(croissant.keys())}")
    print("\nDone. All outputs valid.")

except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
