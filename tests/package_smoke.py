"""Run every method from the installed package with the model calls replaced by a fixed answer.

CI runs this outside the repository after installing the built wheel, so it checks that the
package needs nothing from the repository. No API keys, no cost. Not collected by pytest."""
import json
import sys

import croissantminer
from croissantminer import api, methods
from croissantminer.systems import helpers, locator_extractor, specialists, triage_critique

# One answer that every prompt can parse: field values, a quote per field and a triage verdict per group.
ANSWER = {"name": "Toy Images", "description": "A toy dataset.", "license": "MIT", "publisher": "Toy Lab",
          "datePublished": "2021", "rai:dataCollection": "Images were collected by volunteers.",
          "rai:dataBiases": "Only daytime images."}
ANSWER["evidence"] = {k: "We collected toy images." for k in ANSWER}
ANSWER.update({g: {"presence": "likely", "headings": ["Data"]} for g in ("core", "collection", "annotation", "impact", "processing")})


def fake_call(cfg, system_prompt, user_content, max_tokens=8192, *args, **kwargs):
    return json.dumps(ANSWER), {"input_tokens": 100, "output_tokens": 50}


methods._check_key = lambda provider, key: None
for module in (helpers, specialists, triage_critique, locator_extractor):
    module.call_llm = fake_call

paper = "Title: Toy Images\n\nAbstract\nWe collected toy images.\n\n1 Data\nVolunteers took the photos in 2021.\n" * 20
failures = []
for method in api.METHOD_NAMES:
    if method == "react":   # calls the Anthropic client directly; checked with real runs
        continue
    try:
        result = api.extract(None, method, text=paper, api_key="test")
        assert result.found() > 0 and result.croissant["conformsTo"].endswith("/1.1"), result.summary()
        print(f"ok    {method:22s} {result.summary()}")
    except Exception as e:  # noqa: BLE001
        failures.append(method)
        print(f"FAIL  {method:22s} {type(e).__name__}: {e}")
from croissantminer.react_agent import agent  # noqa: E402,F401  (import check for ReAct)
print("loaded from", croissantminer.__file__)
sys.exit(1 if failures else 0)
