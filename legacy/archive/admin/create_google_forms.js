/**
 * Google Apps Script to create annotation forms for CroissantMiner
 *
 * HOW TO USE:
 * 1. Go to https://script.google.com
 * 2. Create a new project
 * 3. Paste this entire script
 * 4. Update the ANNOTATOR_DATA section below with your data
 * 5. Run the createAnnotationForm() function
 * 6. Authorize when prompted
 * 7. The form URL will appear in the execution log
 */

// ============================================================
// CONFIGURATION - Update this for each annotator
// ============================================================

const ANNOTATOR_NAME = "Annotator_01";
const ASSIGNED_FIELDS = ["name", "description", "url"];

// Sample data - replace with actual extracted data
// Format: { datasetId: { fieldName: extractedValue, ... }, ... }
const EXTRACTED_DATA = {
  "AI4Math_MathVista": {
    "name": "MathVista",
    "description": "MathVista is a benchmark designed to combine challenges from diverse mathematical and visual tasks...",
    "url": "https://mathvista.github.io"
  },
  "BianYx_VAP-Data": {
    "name": "VAP-Data",
    "description": "The largest dataset for semantic-controlled video generation with over 100K paired videos...",
    "url": "https://bytedance.github.io/Video-As-Prompt"
  }
  // Add more datasets...
};

// ============================================================
// FORM CREATION FUNCTIONS
// ============================================================

function createAnnotationForm() {
  // Create the form
  const form = FormApp.create(`CroissantMiner Annotation - ${ANNOTATOR_NAME}`);

  // Set form description
  form.setDescription(
    `Annotation task for ${ANNOTATOR_NAME}\n\n` +
    `Your assigned fields: ${ASSIGNED_FIELDS.join(", ")}\n\n` +
    `Instructions:\n` +
    `1. For each item, review the "Extracted Value" shown\n` +
    `2. Select TRUE if correct, FALSE if incorrect\n` +
    `3. If FALSE, provide the correct value\n` +
    `4. Rate your confidence (1-5)\n\n` +
    `Total items: ${Object.keys(EXTRACTED_DATA).length * ASSIGNED_FIELDS.length}`
  );

  // Add progress indicator section
  form.addSectionHeaderItem()
    .setTitle("Begin Annotation")
    .setHelpText("Each section below contains one dataset field to validate.");

  let itemCount = 0;

  // Create questions for each dataset and field
  for (const [datasetId, data] of Object.entries(EXTRACTED_DATA)) {
    for (const field of ASSIGNED_FIELDS) {
      itemCount++;
      const extractedValue = data[field] || "[NULL]";

      // Add page break between items for cleaner navigation
      if (itemCount > 1) {
        form.addPageBreakItem()
          .setTitle(`Item ${itemCount}: ${datasetId}`);
      }

      // Section header showing the context
      form.addSectionHeaderItem()
        .setTitle(`${datasetId} - ${field}`)
        .setHelpText(`Dataset: ${datasetId}\nField: ${field}`);

      // Show the extracted value (read-only info)
      form.addSectionHeaderItem()
        .setTitle("Extracted Value:")
        .setHelpText(truncateText(extractedValue, 500));

      // Verdict question
      const verdictItem = form.addMultipleChoiceItem()
        .setTitle("Is this extraction correct?")
        .setChoiceValues(["TRUE - The extracted value is correct", "FALSE - The extracted value is incorrect"])
        .setRequired(true);

      // Correction field (shown always, but only needed if FALSE)
      form.addParagraphTextItem()
        .setTitle("If FALSE, provide the correct value:")
        .setHelpText("Leave blank if you selected TRUE above")
        .setRequired(false);

      // Confidence rating
      form.addScaleItem()
        .setTitle("Confidence level")
        .setHelpText("How confident are you in your verdict?")
        .setBounds(1, 5)
        .setLabels("Uncertain", "Very confident")
        .setRequired(true);

      // Optional notes
      form.addParagraphTextItem()
        .setTitle("Notes (optional)")
        .setHelpText("Any additional comments about this extraction")
        .setRequired(false);
    }
  }

  // Set form to collect email addresses for tracking
  form.setCollectEmail(true);

  // Log the form URL
  Logger.log("Form created successfully!");
  Logger.log("Form URL: " + form.getPublishedUrl());
  Logger.log("Edit URL: " + form.getEditUrl());

  return form;
}

function truncateText(text, maxLength) {
  if (!text) return "[NULL]";
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength - 3) + "...";
}

// ============================================================
// HELPER: Generate data from CSV (optional)
// ============================================================

function importDataFromSheet() {
  // If you have data in a Google Sheet, you can import it
  // Update the sheet ID and range as needed
  const sheetId = "YOUR_SHEET_ID_HERE";
  const range = "Sheet1!A:D";

  const sheet = SpreadsheetApp.openById(sheetId);
  const data = sheet.getRange(range).getValues();

  // Process and return data...
  return data;
}
