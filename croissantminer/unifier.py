import json
from collections import Counter
from pathlib import Path
import re
from copy import deepcopy
from .config import METADATA_SCHEMA


def is_valid_value(val):
    """
    Checks if a metadata value is informative and not just a placeholder.
    """
    if val is None:
        return False
    if not isinstance(val, str):
        return bool(val)  # For non-string types, check if truthy
    val = val.strip().lower()
    placeholders = [
        "not mentioned", "not available", "n/a", "unknown", "unspecified",
        "not specified", "not provided", "not mentioned or equivalent value",
        "null", ""
    ]
    return val and all(p not in val for p in placeholders)


def unify_metadata(metadata_list, output_dir):
    unified = deepcopy(METADATA_SCHEMA)
    ambiguous_fields = {}

    def aggregate_string_field(field_name, target_dict=unified):
        if field_name not in target_dict:
            print(f"Warning: Field '{field_name}' not in schema, skipping")
            return None

        values = []
        for metadata in metadata_list:
            if field_name in metadata:
                val = metadata.get(field_name, "")
                if is_valid_value(val):
                    values.append(val.strip())

        if values:
            counts = Counter(values)
            most_common = counts.most_common()
            if len(most_common) == 1 or most_common[0][1] > most_common[1][1]:
                target_dict[field_name] = most_common[0][0]
            else:
                top_values = [v for v, c in most_common if c == most_common[0][1]]
                ambiguous_fields[field_name] = top_values
                target_dict[field_name] = max(top_values, key=len)

        return target_dict.get(field_name, "Not mentioned")

    def aggregate_nested_field(parent_field, child_field, target_dict=unified):
        if parent_field not in target_dict:
            print(f"Warning: Field '{parent_field}' not in schema, skipping")
            return None
        if child_field not in target_dict[parent_field]:
            print(f"Warning: Field '{parent_field}.{child_field}' not in schema, skipping")
            return None

        values = []
        for metadata in metadata_list:
            if parent_field in metadata and isinstance(metadata[parent_field], dict):
                val = metadata[parent_field].get(child_field, "")
                if is_valid_value(val):
                    values.append(val.strip())

        if values:
            counts = Counter(values)
            most_common = counts.most_common()
            if len(most_common) == 1 or most_common[0][1] > most_common[1][1]:
                target_dict[parent_field][child_field] = most_common[0][0]
            else:
                top_values = [v for v, c in most_common if c == most_common[0][1]]
                ambiguous_fields[f"{parent_field}.{child_field}"] = top_values
                target_dict[parent_field][child_field] = max(top_values, key=len)

        return target_dict[parent_field].get(child_field, "Not mentioned")

    def aggregate_array_field(field_name, target_dict=unified):
        if field_name not in target_dict:
            print(f"Warning: Field '{field_name}' not in schema, skipping")
            return None

        all_values = []
        for metadata in metadata_list:
            if field_name in metadata:
                vals = metadata.get(field_name, [])
                if isinstance(vals, list):
                    for val in vals:
                        if is_valid_value(val):
                            all_values.append(val.strip())
                elif isinstance(vals, str) and is_valid_value(vals):
                    parts = [v.strip() for v in vals.split(",") if is_valid_value(v)]
                    all_values.extend(parts)

        if all_values:
            target_dict[field_name] = list(set(all_values))

        return target_dict.get(field_name, [])

    standard_fields = ["description", "license", "name", "url", "datePublished", 
                       "publisher", "inLanguage", "citeAs", "isLiveDataset"]
    rai_fields = ["dataCollection", "dataCollectionTimeframe", "dataAnnotationPlatform",
                  "annotatorDemographics", "dataUseCases", "personalSensitiveInformation"]

    for field in standard_fields + rai_fields:
        aggregate_string_field(field)

    if "creator" in unified:
        aggregate_nested_field("creator", "name")
        if "distribution" in unified:
            aggregate_nested_field("distribution", "encodingFormat")
            aggregate_nested_field("distribution", "contentUrl")

    if "creator" in unified and "@type" in unified["creator"]:
        creator_name = unified["creator"]["name"].lower()
        if is_valid_value(creator_name):
            org_indicators = ["university", "institute", "lab", "company", "inc", 
                              "corporation", "org", "centre", "center", "team"]
            if any(ind in creator_name for ind in org_indicators):
                unified["creator"]["@type"] = "Organization"
            else:
                unified["creator"]["@type"] = "Person"

    unified_path = Path(output_dir) / "unified_metadata.json"
    with open(unified_path, "w", encoding="utf-8") as f:
        json.dump(unified, f, indent=2)

    if ambiguous_fields:
        ambiguous_path = Path(output_dir) / "ambiguous_fields.json"
        with open(ambiguous_path, "w", encoding="utf-8") as f:
            json.dump(ambiguous_fields, f, indent=2)

    print(f"Saved unified metadata to {unified_path}")
    if ambiguous_fields:
        print(f"Saved {len(ambiguous_fields)} ambiguous fields to {ambiguous_path}")

    return unified, ambiguous_fields


def convert_to_croissant(metadata, output_dir):
    croissant = {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "cro": "https://w3id.org/cro/",
            "rai": "https://w3id.org/cro/rai/"
        },
        "@type": "cro:Dataset",
        "@id": f"https://huggingface.co/datasets/{(metadata.get('name') or 'unknown').lower().replace(' ', '_')}",
        "name": metadata.get("name"),
        "description": metadata.get("description"),
        "cro:dataModality": [],
        "license": metadata.get("license") if is_valid_value(metadata.get("license")) else "unknown"
    }

    if is_valid_value(metadata.get("datePublished", "")):
        croissant["datePublished"] = metadata["datePublished"]

    if is_valid_value(metadata.get("inLanguage", "")):
        croissant["inLanguage"] = metadata["inLanguage"]

    if is_valid_value(metadata.get("url", "")):
        croissant["url"] = metadata["url"]

    if is_valid_value(metadata.get("publisher", "")):
        croissant["publisher"] = metadata["publisher"]

    if is_valid_value(metadata.get("citeAs", "")):
        croissant["citeAs"] = metadata["citeAs"]

    # Handle isLiveDataset - can be boolean or string
    is_live = metadata.get("isLiveDataset", "")
    if isinstance(is_live, bool):
        croissant["isLiveDataset"] = is_live
    elif isinstance(is_live, str) and is_live.lower() in ["yes", "true"]:
        croissant["isLiveDataset"] = True

    # Handle creator - can be string or object
    creator = metadata.get("creator")
    if creator:
        if isinstance(creator, dict) and is_valid_value(creator.get("name", "")):
            croissant["creator"] = {
                "@type": creator.get("@type", "Organization"),
                "name": creator["name"]
            }
        elif isinstance(creator, str) and is_valid_value(creator):
            croissant["creator"] = {
                "@type": "Organization",
                "name": creator
            }

    rai_field_mapping = {
        "dataCollection": "rai:dataCollection",
        "dataCollectionTimeframe": "rai:dataCollectionTimeframe",
        "dataAnnotationPlatform": "rai:dataAnnotationPlatform",
        "annotatorDemographics": "rai:annotatorDemographics",
        "dataUseCases": "rai:dataUseCases",
        "personalSensitiveInformation": "rai:personalSensitiveInformation"
    }

    rai_metadata = {}
    for field, cro_field in rai_field_mapping.items():
        if is_valid_value(metadata.get(field, "")):
            rai_metadata[cro_field] = metadata[field]

    if rai_metadata:
        rai_metadata["@type"] = "rai:ResponsibleAIMetadata"
        croissant["rai:responsibleAIMetadata"] = rai_metadata

    croissant["cro:dataModality"] = ["cro:TabularData"]
    desc = metadata["description"].lower()
    if any(k in desc for k in ["text", "nlp", "language", "corpus"]):
        croissant["cro:dataModality"] = ["cro:TextData"]
    elif any(k in desc for k in ["image", "vision", "visual", "picture"]):
        croissant["cro:dataModality"] = ["cro:ImageData"]
    elif any(k in desc for k in ["math", "mathematics", "arithmetic", "problem"]):
        croissant["cro:dataModality"] = ["cro:TextData"]

    croissant_path = Path(output_dir) / "croissant_metadata.json"
    with open(croissant_path, "w", encoding="utf-8") as f:
        json.dump(croissant, f, indent=2)

    print(f"Saved Croissant metadata to {croissant_path}")
    return croissant
