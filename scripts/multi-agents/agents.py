import json
import re
from typing import List, Dict

import anthropic
from anthropic.types import MessageParam

from prompts import (
    AGENT1_PROMPT, AGENT2_PROMPT, AGENT3_PROMPT,
    AGENT4_PROMPT, AGENT5_PROMPT, COORDINATOR_PROMPT,
)

MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 0
MAX_RETRIES = 3
SPECIALIST_MAX_TOKENS = 4096
COORDINATOR_MAX_TOKENS = 2048
USE_SIMPLE_COORDINATOR = True # True: simple dict merge, False: call MODEL to merge

AGENT_FIELDS: Dict[str, List[str]] = {
    "core": [
        "name", "description", "url", "license", "creator", "publisher",
        "datePublished", "inLanguage", "citeAs", "isLiveDataset",
    ],
    "collection": [
        "rai:dataCollection",
        "rai:dataCollectionType",
        "rai:dataCollectionMissingData",
        "rai:dataCollectionRawData",
        "rai:dataCollectionTimeframe",
    ],
    "annotation": [
        "rai:dataAnnotationProtocol",
        "rai:dataAnnotationPlatform",
        "rai:dataAnnotationAnalysis",
        "rai:annotationsPerItem",
        "rai:annotatorDemographics",
        "rai:machineAnnotationTools",
    ],
    "impact": [
        "rai:dataBiases",
        "rai:dataLimitations",
        "rai:dataSocialImpact",
        "rai:personalSensitiveInformation",
        "rai:dataUseCases",
        "rai:dataReleaseMaintenancePlan",
    ],
    "processing": [
        "rai:dataImputationProtocol",
        "rai:dataManipulationProtocol",
        "rai:dataPreprocessingProtocol",
    ],
}

ALL_FIELDS: List[str] = [field for group in AGENT_FIELDS.values() for field in group]
NULL_VALUES = {"null", "none", "n/a", "na", ""}


def normalize_nulls(obj: dict) -> dict:
    """Replace string nulls with None recursively."""
    cleaned = {}
    for k, v in obj.items():
        if isinstance(v, str) and v.strip().lower() in NULL_VALUES:
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def extract_json(text: str) -> dict:
    """
    Parse the first JSON object found in *text*.
    Strips Markdown fences if present before parsing.
    """
    # Remove ```json ... ``` formatting
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # Find the first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response:\n{text[:300]}")
    return json.loads(match.group())


def null_dict(fields: list[str]) -> dict:
    """Return a dict with all specified fields set to None."""
    return {f: None for f in fields}


_client = anthropic.Anthropic(max_retries=MAX_RETRIES)


def _call_api(system: str, user_message: str, max_tokens: int) -> tuple[str, dict]:
    message_param: MessageParam = {
        "role": "user",
        "content": user_message,
    }

    response = _client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=TEMPERATURE,
        system=system,
        messages=[message_param],
    )
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return response.content[0].text, usage


class SpecialistAgent:
    """
    Calls the API with a specialist system prompt and parses its JSON output.
    """

    def __init__(
            self,
            name: str,
            prompt: str,
            assigned_fields: list[str],
            max_tokens: int = SPECIALIST_MAX_TOKENS,
    ):
        self.name = name
        self.prompt = prompt
        self.assigned_fields = assigned_fields
        self.max_tokens = max_tokens

    def run(self, paper_text: str) -> tuple[dict, dict]:
        """
        Extract fields from *paper_text*.

        Returns:
            (extracted_fields, usage_dict)
            On failure, returns a null dict for all owned fields plus usage zeros.
        """
        try:
            raw_text, usage = _call_api(
                system=self.prompt,
                user_message=f"BEGIN PAPER TEXT {paper_text} END PAPER TEXT",
                max_tokens=self.max_tokens,
            )
            data = extract_json(raw_text)
            data = normalize_nulls(data)

            for f in self.assigned_fields:
                data.setdefault(f, None)

            data = {k: v for k, v in data.items() if k in self.assigned_fields}
            print(f" [{self.name}] done ({usage['input_tokens']}in / {usage['output_tokens']}out tokens)")

            return data, usage

        except Exception as e:
            print(f" [{self.name}] FAILED: {e}. Using null fallback.")

            return null_dict(self.assigned_fields), {"input_tokens": 0, "output_tokens": 0}


class CoordinatorAgent:
    """
    Merges the five specialist outputs into a single JSON using Claude.
    """

    def run(self, specialist_outputs: dict[str, dict]) -> tuple[dict, dict, int]:
        """
        Args:
            specialist_outputs: dict mapping agent name to field dict

        Returns:
            (merged_fields, usage_dict, modifications_count)
        """
        # Build the user message: present each specialist's output labeled
        sections = []
        for agent_name, fields in specialist_outputs.items():
            sections.append(f"=== {agent_name.upper()} AGENT OUTPUT ===\n{json.dumps(fields, indent=2)}")

        user_message = "\n\n".join(sections)

        try:
            raw_text, usage = _call_api(
                system=COORDINATOR_PROMPT,
                user_message=user_message,
                max_tokens=COORDINATOR_MAX_TOKENS,
            )
        except Exception as e:
            print(f" [coordinator] FAILED: {e}. Falling back to simple merge.")

            return _fallback_merge(specialist_outputs), {"input_tokens": 0, "output_tokens": 0}, 0

        # Parse the JSON portion
        try:
            merged = extract_json(raw_text)
            merged = normalize_nulls(merged)
        except Exception as e:
            print(f" [coordinator] JSON parse failed: {e}. Falling back to simple merge.")

            return _fallback_merge(specialist_outputs), usage, 0

        modifications = 0
        match = re.search(r"MODIFICATIONS:\s*(\d+)", raw_text, re.IGNORECASE)
        if match:
            modifications = int(match.group(1))

        usage_str = f"{usage['input_tokens']}in / {usage['output_tokens']}out tokens"

        print(f" [coordinator] done ({usage_str}) with {modifications} modifications")

        return merged, usage, modifications


class SimpleCoordinator:
    """
    Merges the five disjoint specialist outputs with a simple dict merge.
    Fields are mutually exclusive across agents so there are no conflicts to resolve.
    """

    def run(self, specialist_outputs: dict[str, dict]) -> tuple[dict, dict, int]:
        merged: dict = {}
        for fields in specialist_outputs.values():
            merged.update(fields)
        return merged, {"input_tokens": 0, "output_tokens": 0}, 0


def _fallback_merge(specialist_outputs: dict[str, dict]) -> dict:
    merged: dict = {}
    for fields in specialist_outputs.values():
        merged.update(fields)
    return merged


SPECIALISTS: List[SpecialistAgent] = [
    SpecialistAgent("core", AGENT1_PROMPT, AGENT_FIELDS["core"]),
    SpecialistAgent("collection", AGENT2_PROMPT, AGENT_FIELDS["collection"]),
    SpecialistAgent("annotation", AGENT3_PROMPT, AGENT_FIELDS["annotation"]),
    SpecialistAgent("impact", AGENT4_PROMPT, AGENT_FIELDS["impact"]),
    SpecialistAgent("processing", AGENT5_PROMPT, AGENT_FIELDS["processing"]),
]

COORDINATOR = SimpleCoordinator() if USE_SIMPLE_COORDINATOR else CoordinatorAgent()
