#!/usr/bin/env python3
"""
Generate Google Apps Scripts for creating annotation forms.

This script generates .js files that can be copy-pasted into
Google Apps Script (script.google.com) to create Google Forms.

Usage:
    python scripts/generate_forms_scripts.py
"""

import json
from pathlib import Path
from datetime import datetime

PROCESSED_DIR = Path("data/processed")
OUTPUT_DIR = Path("data/annotations/forms_scripts")

ANNOTATOR_ASSIGNMENTS = {
    "Annotator_01": ["name", "description", "url"],
    "Annotator_02": ["license", "creator", "publisher"],
    "Annotator_03": ["datePublished", "inLanguage", "citeAs"],
    "Annotator_04": ["isLiveDataset", "rai:dataCollection", "rai:dataCollectionType"],
    "Annotator_05": ["rai:dataCollectionMissingData", "rai:dataCollectionRawData", "rai:dataCollectionTimeframe"],
    "Annotator_06": ["rai:dataImputationProtocol", "rai:dataManipulationProtocol", "rai:dataPreprocessingProtocol"],
    "Annotator_07": ["rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis"],
    "Annotator_08": ["rai:annotationsPerItem", "rai:annotatorDemographics", "rai:machineAnnotationTools"],
    "Annotator_09": ["rai:dataReleaseMaintenancePlan", "rai:personalSensitiveInformation", "rai:dataSocialImpact"],
    "Annotator_10": ["rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases"],
}


def load_all_extractions():
    """Load all extracted metadata."""
    extractions = {}
    for dataset_dir in sorted(PROCESSED_DIR.iterdir()):
        if not dataset_dir.is_dir():
            continue
        for filename in ["full_pdf_metadata_result.json", "croissant_metadata.json"]:
            result_file = dataset_dir / filename
            if result_file.exists():
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if "rai:dataCollection" in data or "rai:dataUseCases" in data:
                        extractions[dataset_dir.name] = data
                        break
                except:
                    pass
    return extractions


def escape_js_string(s):
    """Escape a string for JavaScript."""
    if s is None:
        return "[NULL]"
    if isinstance(s, (dict, list)):
        s = json.dumps(s, ensure_ascii=False)
    s = str(s)
    # Escape for JS string
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("'", "\\'")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    # Truncate very long strings
    if len(s) > 800:
        s = s[:797] + "..."
    return s


def generate_form_script(annotator_name, fields, extractions):
    """Generate a Google Apps Script for one annotator."""

    num_items = len(extractions) * len(fields)

    script = f'''/**
 * Google Apps Script - {annotator_name}
 *
 * HOW TO USE:
 * 1. Go to https://script.google.com
 * 2. Click "New Project"
 * 3. Delete any existing code
 * 4. Paste this ENTIRE script
 * 5. Click "Run" (play button) on createAnnotationForm
 * 6. Click "Review permissions" and authorize
 * 7. Check the Execution Log for the form URL
 *
 * Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
 * Total items: {num_items}
 */

function createAnnotationForm() {{
  // Create form
  const form = FormApp.create("CroissantMiner Annotation - {annotator_name}");

  form.setDescription(
    "Annotation Task for {annotator_name}\\n\\n" +
    "YOUR ASSIGNED FIELDS:\\n" +
    "{', '.join(fields)}\\n\\n" +
    "INSTRUCTIONS:\\n" +
    "1. Review each extracted value\\n" +
    "2. Select TRUE if correct, FALSE if incorrect\\n" +
    "3. If FALSE, provide the correct value\\n" +
    "4. Rate your confidence (1=uncertain, 5=confident)\\n\\n" +
    "Total items to annotate: {num_items}"
  );

  form.setProgressBar(true);
  form.setCollectEmail(true);

  // Add items
  let itemNum = 0;
'''

    for dataset_id, data in sorted(extractions.items()):
        for field in fields:
            value = data.get(field)
            escaped_value = escape_js_string(value)

            script += f'''
  // Item {dataset_id} - {field}
  itemNum++;
  if (itemNum > 1) form.addPageBreakItem().setTitle("Item " + itemNum + " of {num_items}");

  form.addSectionHeaderItem()
    .setTitle("{dataset_id}")
    .setHelpText("Field: {field}");

  form.addSectionHeaderItem()
    .setTitle("EXTRACTED VALUE:")
    .setHelpText("{escaped_value}");

  form.addMultipleChoiceItem()
    .setTitle("Is this correct?")
    .setChoiceValues(["TRUE", "FALSE"])
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle("If FALSE, provide correct value:")
    .setRequired(false);

  form.addScaleItem()
    .setTitle("Confidence")
    .setBounds(1, 5)
    .setLabels("Uncertain", "Confident")
    .setRequired(true);
'''

    script += '''
  // Log results
  Logger.log("=================================");
  Logger.log("Form created successfully!");
  Logger.log("Form URL: " + form.getPublishedUrl());
  Logger.log("Edit URL: " + form.getEditUrl());
  Logger.log("=================================");

  return form;
}
'''
    return script


def main():
    print("=" * 60)
    print("Generating Google Forms Scripts")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\nLoading extracted metadata...")
    extractions = load_all_extractions()
    print(f"  Loaded {len(extractions)} datasets")

    print("\nGenerating scripts...")
    for annotator, fields in ANNOTATOR_ASSIGNMENTS.items():
        script = generate_form_script(annotator, fields, extractions)
        output_file = OUTPUT_DIR / f"{annotator}_form.js"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(script)
        print(f"  Created {output_file}")

    # Create instructions
    readme = OUTPUT_DIR / "README.md"
    with open(readme, 'w') as f:
        f.write("""# Google Forms Scripts

## How to Create a Form

1. Open https://script.google.com
2. Click **"New Project"**
3. Delete any existing code in the editor
4. Open one of the `.js` files (e.g., `Annotator_01_form.js`)
5. Copy ALL the code and paste it into the script editor
6. Click the **Run** button (▶️)
7. Select `createAnnotationForm` if prompted
8. Click **"Review permissions"** → Choose your Google account → **"Allow"**
9. Check the **Execution Log** (View → Execution log) for the form URL

## Form Features

- Progress bar showing completion
- One item per page for focus
- Required verdict (TRUE/FALSE)
- Optional correction field
- Confidence scale (1-5)
- Collects annotator email

## Generated Files

| File | Annotator | Fields |
|------|-----------|--------|
| Annotator_01_form.js | Annotator 01 | name, description, url |
| Annotator_02_form.js | Annotator 02 | license, creator, publisher |
| ... | ... | ... |
""")

    print(f"\n✅ Scripts saved to {OUTPUT_DIR}/")
    print("\nTo create a form:")
    print("  1. Go to https://script.google.com")
    print("  2. Create new project")
    print("  3. Paste the script content")
    print("  4. Run createAnnotationForm()")
    print("  5. Check execution log for form URL")


if __name__ == "__main__":
    main()
