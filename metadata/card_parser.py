"""
Robust dataset card parser that handles various markdown formats and structures
"""

import json
import re
from pathlib import Path
from config import METADATA_SCHEMA


def parse_dataset_card(card_path):
    """
    Parse dataset card and extract metadata from markdown content with adaptive strategies
    
    Args:
        card_path (str): Path to the dataset card file
        
    Returns:
        dict: Extracted metadata using adaptive parsing strategies
    """
    print(f"----- Parsing dataset card (adaptive): {card_path} -----")
    
    try:
        with open(card_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"✗ Error reading dataset card: {str(e)}")
        return None
    
    # Skip YAML frontmatter and get only markdown content
    markdown_content = extract_markdown_only(content)
    
    # Extract metadata using multiple adaptive strategies
    card_metadata = extract_with_adaptive_strategies(markdown_content)
    
    print(f"✓ Successfully parsed dataset card with adaptive strategies")
    return card_metadata


def extract_markdown_only(content):
    """Extract only the markdown content, skipping YAML frontmatter"""
    
    # Check for YAML frontmatter and skip it
    yaml_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
    if yaml_match:
        markdown_content = yaml_match.group(2)
        print("ℹ️ Skipped YAML frontmatter, using only markdown content")
    else:
        markdown_content = content
        print("ℹ️ No YAML frontmatter found, using full content")
    
    return markdown_content


def extract_with_adaptive_strategies(markdown_content):
    """Extract metadata using multiple adaptive strategies for different card formats"""
    
    # Start with default schema
    metadata = METADATA_SCHEMA.copy()
    
    print("----- Applying adaptive extraction strategies -----")
    
    # Strategy 1: Extract basic information (works for all formats)
    metadata = extract_basic_info(markdown_content, metadata)
    
    # Strategy 2: Extract structured description sections
    metadata = extract_description_sections(markdown_content, metadata)
    
    # Strategy 3: Extract URLs and links
    metadata = extract_urls_and_links(markdown_content, metadata)
    
    # Strategy 4: Extract citation information
    metadata = extract_citation_info(markdown_content, metadata)
    
    # Strategy 5: Extract licensing information
    metadata = extract_license_info(markdown_content, metadata)
    
    # Strategy 6: Extract task and usage information
    metadata = extract_task_usage_info(markdown_content, metadata)
    
    # Strategy 7: Extract creator and contribution information
    metadata = extract_creator_info(markdown_content, metadata)
    
    # Strategy 8: Extract language information
    metadata = extract_language_info(markdown_content, metadata)
    
    # Strategy 9: Extract sensitive information notices
    metadata = extract_sensitive_info(markdown_content, metadata)
    
    # Count meaningful extractions
    meaningful_fields = count_meaningful_fields(metadata)
    print(f"✓ Extracted {meaningful_fields} meaningful fields using adaptive strategies")
    
    return metadata


def extract_basic_info(markdown_content, metadata):
    """Extract basic dataset information that appears in most formats"""
    
    # Extract dataset name from various header patterns
    name_patterns = [
        r'# Dataset Card for (.+)',
        r'# (.+)',
        r'## (.+)\s*(?:\n|$)',
    ]
    
    for pattern in name_patterns:
        name_match = re.search(pattern, markdown_content)
        if name_match:
            potential_name = clean_text(name_match.group(1))
            # Filter out common non-name headers
            if not any(word in potential_name.lower() for word in ['table of contents', 'dataset description', 'examples']):
                metadata['name'] = potential_name
                print(f"✓ Found name: {metadata['name']}")
                break
    
    return metadata


def extract_description_sections(markdown_content, metadata):
    """Extract description from various section formats"""
    
    # Multiple patterns to catch different description formats
    description_patterns = [
        r'### Dataset Summary\s*\n\n(.*?)(?=\n### |\n## |\Z)',
        r'## Dataset Summary\s*\n\n(.*?)(?=\n### |\n## |\Z)',
        r'## Dataset Description\s*\n\n(.*?)(?=\n### |\n## |\Z)',
        r'### Dataset Description\s*\n\n(.*?)(?=\n### |\n## |\Z)',
        r'## Description\s*\n\n(.*?)(?=\n### |\n## |\Z)',
        # Pattern for cards that have description right after title
        r'# [^\n]+\s*\n\n([^#].*?)(?=\n## |\Z)',
    ]
    
    for pattern in description_patterns:
        desc_match = re.search(pattern, markdown_content, re.DOTALL | re.IGNORECASE)
        if desc_match:
            description = clean_text(desc_match.group(1))
            if description and len(description) > 50:  # Only substantial descriptions
                metadata['description'] = description
                print(f"✓ Found description: {description[:100]}...")
                break
    
    return metadata


def extract_urls_and_links(markdown_content, metadata):
    """Extract URLs from various link formats"""
    
    # Homepage/Repository patterns
    url_patterns = {
        'url': [
            r'- \*\*Homepage:\*\*\s*\[.*?\]\((https?://[^\)]+)\)',
            r'\*\*Homepage:\*\*\s*\[.*?\]\((https?://[^\)]+)\)',
            r'- \*\*Repository:\*\*\s*\[.*?\]\((https?://[^\)]+)\)',
            r'\*\*Repository:\*\*\s*\[.*?\]\((https?://[^\)]+)\)',
            r'\[🌐 Homepage\]\((https?://[^\)]+)\)',
            r'Homepage.*?:\s*([https://][^\s\)]+)',
        ]
    }
    
    for field, patterns in url_patterns.items():
        if metadata.get(field) == "Not mentioned":
            for pattern in patterns:
                match = re.search(pattern, markdown_content, re.IGNORECASE)
                if match:
                    url = match.group(1)
                    if is_valid_url(url):
                        metadata[field] = url
                        print(f"✓ Found {field}: {url}")
                        break
    
    return metadata


def extract_citation_info(markdown_content, metadata):
    """Extract citation information in various formats"""
    
    # Look for citation sections
    citation_sections = [
        r'### Citation Information(.*?)(?=\n### |\n## |\Z)',
        r'## Citation Information(.*?)(?=\n### |\n## |\Z)',
        r'### Citation(.*?)(?=\n### |\n## |\Z)',
        r'## Citation(.*?)(?=\n### |\n## |\Z)',
    ]
    
    for pattern in citation_sections:
        citation_section = re.search(pattern, markdown_content, re.DOTALL | re.IGNORECASE)
        if citation_section:
            citation_text = citation_section.group(1)
            
            # Extract full citation blocks
            citation_patterns = [
                r'```(?:bibtex)?\s*\n(.*?)\n```',
                r'```\s*\n(.*?)\n```',
                r'@\w+\{[^}]+,.*?\}',  # Direct bibtex pattern
            ]
            
            for cite_pattern in citation_patterns:
                cite_match = re.search(cite_pattern, citation_text, re.DOTALL)
                if cite_match:
                    full_citation = cite_match.group(1).strip() if cite_match.groups() else cite_match.group(0)
                    if full_citation and len(full_citation) > 20:
                        metadata['citeAs'] = full_citation
                        print(f"✓ Found citation: {full_citation[:100]}...")
                        
                        # Extract authors from citation
                        author_match = re.search(r'author.*?=.*?[{"]([^}"]+)[}"]', full_citation, re.IGNORECASE)
                        if author_match and metadata['creator']['name'] == "Not mentioned":
                            authors = clean_author_names(author_match.group(1))
                            metadata['creator']['name'] = authors
                            print(f"✓ Found authors: {authors}")
                        
                        # Extract publisher/journal
                        pub_patterns = [
                            r'journal.*?=.*?[{"]([^}"]+)[}"]',
                            r'booktitle.*?=.*?[{"]([^}"]+)[}"]',
                            r'publisher.*?=.*?[{"]([^}"]+)[}"]',
                        ]
                        
                        for pub_pattern in pub_patterns:
                            pub_match = re.search(pub_pattern, full_citation, re.IGNORECASE)
                            if pub_match and metadata['publisher'] == "Not mentioned":
                                metadata['publisher'] = pub_match.group(1)
                                print(f"✓ Found publisher: {metadata['publisher']}")
                                break
                        
                        # Extract year
                        year_match = re.search(r'year.*?=.*?[{"]([^}"]+)[}"]', full_citation, re.IGNORECASE)
                        if year_match and metadata['datePublished'] == "Not mentioned":
                            metadata['datePublished'] = year_match.group(1)
                            print(f"✓ Found year: {metadata['datePublished']}")
                        
                        break
            break
    
    return metadata


def extract_license_info(markdown_content, metadata):
    """Extract licensing information from various formats"""
    
    license_sections = [
        r'### Licensing Information(.*?)(?=\n### |\n## |\Z)',
        r'## Licensing Information(.*?)(?=\n### |\n## |\Z)',
        r'### License(.*?)(?=\n### |\n## |\Z)',
        r'## License(.*?)(?=\n### |\n## |\Z)',
    ]
    
    for pattern in license_sections:
        license_section = re.search(pattern, markdown_content, re.DOTALL | re.IGNORECASE)
        if license_section:
            license_text = clean_text(license_section.group(1))
            if license_text and len(license_text) > 10:
                metadata['license'] = license_text
                print(f"✓ Found license: {license_text[:100]}...")
                break
    
    return metadata


def extract_task_usage_info(markdown_content, metadata):
    """Extract task and usage information"""
    
    task_sections = [
        r'### Supported Tasks and Leaderboards(.*?)(?=\n### |\n## |\Z)',
        r'## Supported Tasks and Leaderboards(.*?)(?=\n### |\n## |\Z)',
        r'### Supported Tasks(.*?)(?=\n### |\n## |\Z)',
        r'## Supported Tasks(.*?)(?=\n### |\n## |\Z)',
    ]
    
    for pattern in task_sections:
        task_section = re.search(pattern, markdown_content, re.DOTALL | re.IGNORECASE)
        if task_section:
            task_text = task_section.group(1)
            
            # Extract tasks in various formats
            task_mentions = []
            
            # Backtick format
            backtick_tasks = re.findall(r'`([^`]+)`', task_text)
            task_mentions.extend([task for task in backtick_tasks if is_likely_task(task)])
            
            # Dash list format
            dash_tasks = re.findall(r'- ([^\n]+)', task_text)
            task_mentions.extend([clean_text(task) for task in dash_tasks if is_likely_task(task)])
            
            if task_mentions:
                unique_tasks = list(set(task_mentions))
                metadata['dataUseCases'] = ", ".join(unique_tasks[:5])  # Limit to avoid too long
                print(f"✓ Found tasks: {metadata['dataUseCases']}")
                break
    
    return metadata


def extract_creator_info(markdown_content, metadata):
    """Extract creator/contributor information"""
    
    if metadata['creator']['name'] != "Not mentioned":
        return metadata  # Already found in citation
    
    creator_sections = [
        r'### Dataset Curators(.*?)(?=\n### |\n## |\Z)',
        r'## Dataset Curators(.*?)(?=\n### |\n## |\Z)',
        r'### Contributions(.*?)(?=\n### |\n## |\Z)',
        r'## Contributions(.*?)(?=\n### |\n## |\Z)',
        r'### Contributors(.*?)(?=\n### |\n## |\Z)',
        r'## Contributors(.*?)(?=\n### |\n## |\Z)',
    ]
    
    for pattern in creator_sections:
        creator_section = re.search(pattern, markdown_content, re.DOTALL | re.IGNORECASE)
        if creator_section:
            creator_text = creator_section.group(1)
            
            # Extract GitHub usernames
            github_users = re.findall(r'@([a-zA-Z0-9_-]+)', creator_text)
            if github_users:
                metadata['creator']['name'] = ", ".join(github_users[:3])  # Limit to 3
                print(f"✓ Found contributors: {metadata['creator']['name']}")
                break
            
            # Extract regular names
            cleaned_text = clean_text(creator_text)
            if cleaned_text and len(cleaned_text) > 5 and len(cleaned_text) < 200:
                metadata['creator']['name'] = cleaned_text
                print(f"✓ Found curators: {cleaned_text}")
                break
    
    return metadata


def extract_language_info(markdown_content, metadata):
    """Extract language information"""
    
    language_sections = [
        r'### Languages\s*\n\n(.*?)(?=\n### |\n## |\Z)',
        r'## Languages\s*\n\n(.*?)(?=\n### |\n## |\Z)',
    ]
    
    for pattern in language_sections:
        lang_section = re.search(pattern, markdown_content, re.DOTALL | re.IGNORECASE)
        if lang_section:
            lang_text = clean_text(lang_section.group(1))
            if lang_text and len(lang_text) > 3:
                metadata['inLanguage'] = lang_text
                print(f"✓ Found languages: {lang_text}")
                break
    
    # Fallback: look for language mentions in text
    if metadata['inLanguage'] == "Not mentioned":
        lang_patterns = [
            r'(\d+\s+languages?)',
            r'(multilingual)',
            r'(English)',
            r'languages?[:\-\s]*([^\n.]+)',
        ]
        
        for pattern in lang_patterns:
            lang_match = re.search(pattern, markdown_content, re.IGNORECASE)
            if lang_match:
                lang_info = lang_match.group(1) if len(lang_match.groups()) == 1 else lang_match.group(0)
                metadata['inLanguage'] = clean_text(lang_info)
                print(f"✓ Found language info: {lang_info}")
                break
    
    return metadata


def extract_sensitive_info(markdown_content, metadata):
    """Extract personal and sensitive information notices"""
    
    pii_sections = [
        r'### Personal and Sensitive Information(.*?)(?=\n### |\n## |\Z)',
        r'## Personal and Sensitive Information(.*?)(?=\n### |\n## |\Z)',
        r'### Privacy(.*?)(?=\n### |\n## |\Z)',
        r'## Privacy(.*?)(?=\n### |\n## |\Z)',
    ]
    
    for pattern in pii_sections:
        pii_section = re.search(pattern, markdown_content, re.DOTALL | re.IGNORECASE)
        if pii_section:
            pii_text = clean_text(pii_section.group(1))
            if pii_text and len(pii_text) > 10:
                metadata['personalSensitiveInformation'] = pii_text
                print(f"✓ Found PII info: {pii_text[:100]}...")
                break
    
    return metadata


def clean_text(text):
    """Clean and normalize text content"""
    if not text:
        return ""
    
    # Remove markdown formatting
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Links
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)       # Bold
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)           # Italic
    text = re.sub(r'`([^`]+)`', r'\1', text)              # Code
    text = re.sub(r'^\s*[-*+>]\s+', '', text, flags=re.MULTILINE)  # List items
    
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Remove placeholder text
    if text.lower() in ['[needs more information]', '[more information needed]', 'n/a', 'tbd']:
        return ""
    
    return text


def clean_author_names(authors_text):
    """Clean and format author names from citations"""
    # Handle "First Last and First Last" format
    authors = re.sub(r'\s+and\s+', ', ', authors_text)
    # Remove extra whitespace
    authors = re.sub(r'\s+', ' ', authors)
    return authors.strip()


def is_valid_url(url):
    """Check if string is a valid URL"""
    return url.startswith(('http://', 'https://')) and len(url) > 10


def is_likely_task(text):
    """Check if text is likely a valid task name"""
    text = text.lower().strip()
    # Filter out common non-task terms
    non_tasks = {'datasets', 'load_dataset', 'streaming', 'true', 'false', 'none', 'example', 'test'}
    return len(text) > 3 and len(text) < 50 and text not in non_tasks and not text.isdigit()


def count_meaningful_fields(metadata):
    """Count fields with meaningful (non-default) values"""
    count = 0
    for key, value in metadata.items():
        if isinstance(value, dict):
            if value.get('name') != "Not mentioned":
                count += 1
        elif value != "Not mentioned":
            count += 1
    return count


def save_card_metadata(card_metadata, output_path):
    """Save parsed card metadata to JSON file"""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(card_metadata, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved card metadata to {output_path}")
        return True
    except Exception as e:
        print(f"✗ Error saving card metadata: {str(e)}")
        return False