"""
LLM-based metadata extraction from academic papers
"""

import re
import json
import time
from pathlib import Path
from models.factory import create_model
from config import METADATA_SCHEMA


def create_metadata_extraction_prompt(section_content, section_name):
    """
    Create a prompt for the LLM to extract metadata from a section

    Args:
        section_content (str): Content of the section
        section_name (str): Name of the section

    Returns:
        str: Prompt for the LLM
    """
    # Create the JSON template structure based on our schema
    schema_template = json.dumps(METADATA_SCHEMA, indent=2)

    # Replace values with extraction placeholders
    schema_template = re.sub(r':\s*"([^"]*)"', r': "[EXTRACT: \1 or equivalent value]"', schema_template)
    schema_template = re.sub(r':\s*\[\]', r': ["[EXTRACT: List items if present]"]', schema_template)

    # Build the prompt
    prompt = f"""You are an expert in extracting dataset metadata from academic papers. Your task is to thoroughly analyze the text and extract ALL relevant information about the dataset.

    Section Name: {section_name}

    Section Content:
    \"\"\"
    {section_content}
    \"\"\"

    IMPORTANT INSTRUCTIONS:
    1. Extract ALL information about the dataset, even if mentioned indirectly.
    2. If information is implied but not explicitly stated, make reasonable inferences.
    3. Keep your description concise (2-3 sentences).
    4. For dataset name, always use the PRIMARY dataset name rather than section titles.
    5. For data collection, note any information about how problems were created, collected, or selected.
    6. For dataset uses, identify the intended purposes mentioned in the text.
    7. Look for information about quality control, data creation processes, and human involvement.

    Create a JSON object with this structure:
    {schema_template}

    Your JSON output must be complete and thorough. Only use "Not mentioned" when information is truly unavailable after careful analysis.

    BEGIN JSON OUTPUT:"""

    return prompt


def create_full_pdf_extraction_prompt(pdf_content):
    """
    Create a prompt for extracting metadata from the entire PDF in one call

    Args:
        pdf_content (str): Full text content of the PDF

    Returns:
        str: Prompt for the LLM
    """
    # Create the JSON template structure based on our schema
    schema_template = json.dumps(METADATA_SCHEMA, indent=2)

    # Replace values with extraction placeholders
    schema_template = re.sub(r':\s*"([^"]*)"', r': "[EXTRACT: \1 or equivalent value]"', schema_template)
    schema_template = re.sub(r':\s*\[\]', r': ["[EXTRACT: List items if present]"]', schema_template)

    # Build the prompt for full PDF
    prompt = f"""You are an expert in extracting dataset metadata from academic papers. Your task is to thoroughly analyze the ENTIRE paper and extract ALL relevant information about the dataset.

    FULL PAPER CONTENT:
    \"\"\"
    {pdf_content}
    \"\"\"

    IMPORTANT INSTRUCTIONS:
    1. This is the COMPLETE paper. Analyze ALL sections to extract comprehensive metadata.
    2. Look for dataset information in: Abstract, Introduction, Dataset/Data, Methods, Results, Ethics/Limitations sections.
    3. Extract ALL information about the dataset, even if mentioned indirectly across different sections.
    4. If information is implied but not explicitly stated, make reasonable inferences based on the full context.
    5. Keep your description concise (2-3 sentences) but comprehensive.
    6. For dataset name, always use the PRIMARY dataset name (often in title, abstract, or dataset section).
    7. For data collection, note any information about how data was created, collected, or selected.
    8. For dataset uses, identify the intended purposes mentioned anywhere in the paper.
    9. For RAI fields (responsible AI), look for information about:
       - Data collection methods and timeframe
       - Annotation platforms or processes
       - Annotator demographics
       - Intended use cases and limitations
       - Personal/sensitive information handling
    10. Cross-reference information from multiple sections to provide the most accurate metadata.

    Create a JSON object with this structure:
    {schema_template}

    Your JSON output must be complete and thorough. Only use "Not mentioned" when information is truly unavailable after analyzing the ENTIRE paper.

    BEGIN JSON OUTPUT:"""

    return prompt


def setup_llm_pipeline(model_name="gpt-4o-mini", **kwargs):
    """
    Set up the language model pipeline for metadata extraction
    
    Args:
        model_name (str): Model name (e.g. 'gpt-4o-mini', 'mistral-7b')
        **kwargs: Additional model configuration
        
    Returns:
        BaseModel: Initialized model instance
    """
    print(f"Loading model: {model_name}")
    
    try:
        model = create_model(model_name, **kwargs)
        
        if not model.setup():
            raise RuntimeError(f"Failed to initialize model: {model_name}")
        
        print("Model loaded successfully")
        return model
        
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        raise


def clean_llm_output(raw_output, prompt):
    """
    Clean and extract JSON from LLM output
    
    Args:
        raw_output (str): Raw LLM output
        prompt (str): Original prompt
        
    Returns:
        str: Cleaned JSON string
    """
    # Extract just the generated part (removing the prompt)
    if raw_output.startswith(prompt):
        raw_output = raw_output[len(prompt):].strip()
    
    # Remove trailing text after JSON
    if "END JSON OUTPUT" in raw_output:
        raw_output = raw_output.split("END JSON OUTPUT")[0].strip()
        
    # Extract JSON between outer braces
    first_brace = raw_output.find("{")
    last_brace = raw_output.rfind("}")
    
    if first_brace != -1 and last_brace != -1:
        json_str = raw_output[first_brace:last_brace+1]
        
        # Fix common JSON issues
        json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)  # Remove control chars
        json_str = json_str.replace('\\\"', '\"')  # Fix escaped quotes
        json_str = re.sub(r'(?<!\\)\\n', ' ', json_str)  # Fix line breaks
        json_str = re.sub(r',\s*}', '}', json_str)  # Fix trailing commas
        json_str = re.sub(r',\s*]', ']', json_str)  # Fix trailing commas in arrays
        
        return json_str
    
    return raw_output


def extract_metadata(sections, model, output_dir):
    """
    Extract metadata from sections using LLM
    
    Args:
        sections (list): List of sections for extraction
        model: Model instance (HuggingFace pipeline or OpenAI model)
        output_dir (Path): Directory to save results
        
    Returns:
        dict: Dictionary of results by section
    """
    section_results = {}
    print(f"Extracting metadata from {len(sections)} sections...")
    
    for i, section in enumerate(sections):
        section_name = section['section_name']
        content = section['content']
        
        print(f"\nProcessing {i+1}/{len(sections)}: {section_name}")
        
        # Create the prompt
        prompt = create_metadata_extraction_prompt(content, section_name)
        
        try:
            # Generate response with model
            output = model.generate(prompt)
            
            # Clean the output to extract just the JSON
            json_str = clean_llm_output(output, prompt)
            
            # Store result
            section_results[section_name] = json_str
            
            # Print preview
            preview = json_str[:100] + "..." if len(json_str) > 100 else json_str
            print(f"  Extracted metadata preview: {preview}")
            
        except Exception as e:
            print(f"  Error processing section {section_name}: {str(e)}")
            section_results[section_name] = f"Error: {str(e)}"
        
        # Pause briefly between requests
        time.sleep(0.1)
    
    # Save raw results
    results_path = Path(output_dir) / "section_metadata_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(section_results, f, indent=2)
    
    print(f"\nSaved raw metadata extraction results to: {results_path}")
    return section_results


def parse_metadata_results(section_results):
    """
    Parse the raw JSON strings into Python dictionaries

    Args:
        section_results (dict): Raw extraction results by section

    Returns:
        list: List of parsed metadata dictionaries
    """
    metadata_list = []

    for section_name, raw_json_str in section_results.items():
        try:
            # Skip entries with errors
            if raw_json_str.startswith("Error:"):
                continue

            # Parse the JSON
            metadata = json.loads(raw_json_str)

            # Only include if it has meaningful content
            if "name" in metadata and metadata["name"] != "Not mentioned":
                if not metadata["name"].endswith("?"):
                    metadata_list.append(metadata)
                    print(f"✓ Successfully parsed: {section_name}")
            else:
                print(f"✗ Skipping section with placeholder: {section_name}")

        except json.JSONDecodeError as e:
            print(f"✗ JSON error in section '{section_name}': {e}")

    print(f"\nSuccessfully parsed {len(metadata_list)} valid metadata entries")
    return metadata_list


def extract_metadata_full_pdf(full_text, model, output_dir, max_chars=50000):
    """
    Extract metadata from entire PDF in one LLM call

    Args:
        full_text (str): Full text content of the PDF
        model: Model instance (HuggingFace pipeline or OpenAI model)
        output_dir (Path): Directory to save results
        max_chars (int): Maximum characters to process (for token limit safety)

    Returns:
        dict: Parsed metadata dictionary (already unified, no need for unification)
    """
    print(f"Extracting metadata from full PDF (mode: FULL-PDF, 1 LLM call)...")

    # Truncate if needed to stay within token limits
    if len(full_text) > max_chars:
        print(f"⚠️ PDF text is {len(full_text)} chars, truncating to {max_chars} chars")
        full_text = full_text[:max_chars]
    else:
        print(f"PDF text length: {len(full_text)} chars")

    # Create the full-PDF prompt
    prompt = create_full_pdf_extraction_prompt(full_text)

    try:
        # Generate response with model
        print("Calling LLM with full PDF content...")
        output = model.generate(prompt)

        # Clean the output to extract just the JSON
        json_str = clean_llm_output(output, prompt)

        # Save raw result
        results_path = Path(output_dir) / "full_pdf_metadata_result.json"
        with open(results_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        print(f"Saved raw metadata extraction result to: {results_path}")

        # Parse the JSON
        metadata = json.loads(json_str)

        # Validate that we got meaningful content
        if "name" in metadata and metadata["name"] != "Not mentioned":
            print(f"✅ Successfully extracted metadata for dataset: {metadata['name']}")
            return metadata
        else:
            print("⚠️ Warning: Extracted metadata may be incomplete (no dataset name found)")
            return metadata

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"Raw output preview: {json_str[:500]}...")
        raise
    except Exception as e:
        print(f"❌ Error during full-PDF extraction: {str(e)}")
        raise