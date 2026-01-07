"""
Improved baseline metadata extractors that properly parse structured dataset cards.
"""

import re
import json
import yaml
from pathlib import Path
from collections import Counter

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except:
    nlp = None

try:
    from nltk.tokenize import sent_tokenize
except:
    sent_tokenize = lambda x: re.split(r'[.!?]+', x)


def create_empty_result():
    """Create properly formatted empty metadata result"""
    return {
        "description": "Not mentioned",
        "license": "Not mentioned", 
        "name": "Not mentioned",
        "url": "Not mentioned",
        "creator": {"@type": "Person", "name": "Not mentioned"},
        "publisher": "Not mentioned",
        "datePublished": "Not mentioned",
        "inLanguage": "Not mentioned",
        "citeAs": "Not mentioned",
        "isLiveDataset": "Not mentioned",
        "dataCollection": "Not mentioned",
        "dataCollectionTimeframe": "Not mentioned",
        "dataAnnotationPlatform": "Not mentioned",
        "annotatorDemographics": "Not mentioned",
        "dataUseCases": "Not mentioned",
        "personalSensitiveInformation": "Not mentioned"
    }


def parse_dataset_card_structure(content):
    """Parse dataset card into YAML frontmatter and markdown content"""
    # Split YAML frontmatter and markdown
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            yaml_content = parts[1].strip()
            markdown_content = parts[2].strip()
        else:
            yaml_content = ""
            markdown_content = content
    else:
        yaml_content = ""
        markdown_content = content
    
    # Parse YAML
    yaml_data = {}
    if yaml_content:
        try:
            yaml_data = yaml.safe_load(yaml_content)
        except:
            yaml_data = {}
    
    # Parse markdown sections
    markdown_sections = {}
    if markdown_content:
        # Split by headers
        sections = re.split(r'\n#+\s+([^\n]+)', markdown_content)
        if len(sections) > 1:
            for i in range(1, len(sections), 2):
                if i + 1 < len(sections):
                    header = sections[i].strip()
                    content = sections[i + 1].strip()
                    markdown_sections[header.lower()] = content
    
    return yaml_data, markdown_sections


def regex_baseline(sections, output_dir):
    """Improved regex baseline with structured card parsing"""
    print("----- Running regex_baseline extraction -----")
    
    result = create_empty_result()
    
    # Process each section
    for section in sections:
        content = section.get('content', '')
        
        # Check if this is a dataset card
        if 'dataset card' in section.get('section_name', '').lower() or content.startswith('---'):
            yaml_data, markdown_sections = parse_dataset_card_structure(content)
            
            # Extract from YAML frontmatter
            if yaml_data:
                # License
                if 'license' in yaml_data:
                    license_val = yaml_data['license']
                    if isinstance(license_val, list):
                        result['license'] = ', '.join(str(x) for x in license_val)
                    else:
                        result['license'] = str(license_val)
                
                # Pretty name as dataset name
                if 'pretty_name' in yaml_data:
                    result['name'] = yaml_data['pretty_name']
                
                # Language
                if 'language' in yaml_data:
                    lang_val = yaml_data['language']
                    if isinstance(lang_val, list):
                        result['inLanguage'] = ', '.join(str(x) for x in lang_val)
                    else:
                        result['inLanguage'] = str(lang_val)
                
                # Task categories as use cases
                if 'task_categories' in yaml_data:
                    tasks = yaml_data['task_categories']
                    if isinstance(tasks, list):
                        result['dataUseCases'] = ', '.join(str(x).replace('-', ' ') for x in tasks[:3])
                
                # Annotation creators as demographics
                if 'annotations_creators' in yaml_data:
                    creators = yaml_data['annotations_creators']
                    if isinstance(creators, list):
                        result['annotatorDemographics'] = ', '.join(str(x) for x in creators)
            
            # Extract from markdown sections
            if markdown_sections:
                # Dataset description/summary
                for key in ['dataset summary', 'dataset description', 'description']:
                    if key in markdown_sections:
                        desc = markdown_sections[key]
                        # Clean and extract first substantial paragraph
                        paragraphs = [p.strip() for p in desc.split('\n\n') if len(p.strip()) > 50]
                        if paragraphs:
                            result['description'] = paragraphs[0][:300]
                        break
                
                # Homepage/Repository URLs
                for key in ['dataset description', 'paper information']:
                    if key in markdown_sections:
                        content = markdown_sections[key]
                        # Look for URLs
                        urls = re.findall(r'https?://[^\s\)]{10,100}', content)
                        if urls:
                            # Prefer homepage/repository over paper URLs
                            for url in urls:
                                if any(word in url.lower() for word in ['github', 'homepage', 'repository']):
                                    result['url'] = url
                                    break
                            else:
                                result['url'] = urls[0]
                        break
                
                # Citation information
                if 'citation information' in markdown_sections:
                    citation_section = markdown_sections['citation information']
                    # Extract bibtex
                    bibtex_match = re.search(r'```(?:bibtex)?\s*\n(.*?)\n```', citation_section, re.DOTALL)
                    if bibtex_match:
                        result['citeAs'] = bibtex_match.group(1).strip()
                        
                        # Extract author from bibtex
                        author_match = re.search(r'author\s*=\s*[{"]([^}"]+)[}"]', result['citeAs'])
                        if author_match:
                            authors = author_match.group(1)
                            # Clean up author names
                            if ' and ' in authors:
                                first_author = authors.split(' and ')[0].strip()
                                result['creator']['name'] = first_author
                            else:
                                result['creator']['name'] = authors
                        
                        # Extract year
                        year_match = re.search(r'year\s*=\s*[{"]?([0-9]{4})[}"]?', result['citeAs'])
                        if year_match:
                            result['datePublished'] = year_match.group(1)
                
                # Licensing information
                if 'licensing information' in markdown_sections:
                    license_section = markdown_sections['licensing information']
                    # Look for license mentions
                    license_patterns = [
                        r'licensed under the ([^\.]+)',
                        r'(MIT License|CC [A-Z\-0-9\.]+|Apache [0-9\.]+|GPL [0-9\.]+)',
                    ]
                    for pattern in license_patterns:
                        match = re.search(pattern, license_section, re.IGNORECASE)
                        if match:
                            result['license'] = match.group(1)
                            break
                
                # Data collection information
                for key in ['source data', 'dataset creation', 'initial data collection']:
                    if key in markdown_sections:
                        section_content = markdown_sections[key]
                        # Look for collection methods
                        collection_patterns = [
                            r'(collected.*?by.*?[^\.]+)',
                            r'(hiring.*?contractors.*?[^\.]+)',
                            r'(data.*?collection.*?[^\.]+)',
                        ]
                        for pattern in collection_patterns:
                            match = re.search(pattern, section_content, re.IGNORECASE | re.DOTALL)
                            if match:
                                collection_text = match.group(1)[:200]
                                result['dataCollection'] = collection_text
                                break
                        if result['dataCollection'] != "Not mentioned":
                            break
                
                # Annotator information
                if 'who are the annotators' in markdown_sections:
                    annotator_section = markdown_sections['who are the annotators']
                    # Extract annotator info
                    if len(annotator_section.strip()) > 5 and 'more information' not in annotator_section.lower():
                        result['annotatorDemographics'] = annotator_section[:150]
        
        else:
            # Process regular paper sections with improved patterns
            text = content
            
            # Better patterns for paper content
            patterns = {
                'name': [
                    r'(?:introduce|present)\s+([A-Z][A-Za-z0-9\-]{2,30})\b(?:\s*,|\s+dataset)',
                    r'\b([A-Z][A-Za-z0-9\-]{3,30})\s+(?:is\s+a\s+(?:dataset|corpus))',
                ],
                'datePublished': [
                    r'\b([12][0-9]{3})\b(?![\d\.])',  # Year not part of larger number
                ],
                'creator': [
                    r'(?:by|authors?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b',
                ],
                'description': [
                    r'(?:dataset|corpus)\s+(?:of|contains|includes)\s+([^\.]{40,200})',
                ],
            }
            
            for field, field_patterns in patterns.items():
                if result[field] == "Not mentioned" or (field == 'creator' and result[field]['name'] == "Not mentioned"):
                    for pattern in field_patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        if matches:
                            best_match = matches[0] if len(matches) == 1 else max(matches, key=len)
                            if field == 'creator':
                                result['creator']['name'] = best_match
                            else:
                                result[field] = best_match
                            break
    
    return save_result(result, output_dir, "regex_baseline")


def ner_baseline(sections, output_dir):
    """Improved NER baseline with structured parsing"""
    print("----- Running ner_baseline extraction -----")
    
    result = create_empty_result()
    
    # First try structured parsing
    for section in sections:
        content = section.get('content', '')
        
        if 'dataset card' in section.get('section_name', '').lower() or content.startswith('---'):
            yaml_data, markdown_sections = parse_dataset_card_structure(content)
            
            # Extract structured data first
            if yaml_data:
                if 'pretty_name' in yaml_data:
                    result['name'] = yaml_data['pretty_name']
                if 'license' in yaml_data:
                    license_val = yaml_data['license']
                    result['license'] = ', '.join(str(x) for x in license_val) if isinstance(license_val, list) else str(license_val)
                if 'language' in yaml_data:
                    lang_val = yaml_data['language']
                    result['inLanguage'] = ', '.join(str(x) for x in lang_val) if isinstance(lang_val, list) else str(lang_val)
    
    # Then use NER on remaining content
    if not nlp:
        print("❌ spaCy not available, using fallback")
        return save_result(result, output_dir, "ner_baseline")
    
    # Process all text with NER
    all_text = " ".join(section.get('content', '') for section in sections)
    if len(all_text) > 150000:
        all_text = all_text[:150000]
    
    doc = nlp(all_text)
    
    # Collect high-quality entities
    entities = {'PERSON': [], 'ORG': [], 'DATE': []}
    for ent in doc.ents:
        if ent.label_ in entities:
            entity_text = ent.text.strip()
            # Better entity validation
            if (len(entity_text) > 2 and 
                not entity_text.lower().startswith(('figure', 'table', 'appendix', 'section')) and
                not re.match(r'^[\d\.\s\-\(\)]+$', entity_text) and
                'dataset' not in entity_text.lower()):
                entities[ent.label_].append(entity_text)
    
    # Extract creator from PERSON entities (if not already found)
    if result['creator']['name'] == "Not mentioned" and entities['PERSON']:
        person_counts = Counter(entities['PERSON'])
        for person, count in person_counts.most_common(5):
            # Better name validation
            if (' ' in person and len(person) > 5 and len(person) < 50 and
                not any(word in person.lower() for word in ['data', 'field', 'information', 'example'])):
                result['creator']['name'] = person
                break
    
    # Extract publisher from ORG entities
    if entities['ORG']:
        org_counts = Counter(entities['ORG'])
        for org, count in org_counts.most_common(5):
            if any(word in org.lower() for word in ['university', 'institute', 'lab', 'college', 'research']):
                result['publisher'] = org
                break
    
    # Extract date (if not already found)
    if result['datePublished'] == "Not mentioned" and entities['DATE']:
        for date in entities['DATE']:
            year_match = re.search(r'\b([12][0-9]{3})\b', date)
            if year_match:
                result['datePublished'] = year_match.group(1)
                break
    
    return save_result(result, output_dir, "ner_baseline")


def tfidf_baseline(sections, output_dir):
    """Improved TF-IDF baseline with structured parsing"""
    print("----- Running tfidf_baseline extraction -----")
    
    result = create_empty_result()
    
    # First, try structured parsing for dataset cards
    structured_found = False
    for section in sections:
        content = section.get('content', '')
        
        if 'dataset card' in section.get('section_name', '').lower() or content.startswith('---'):
            yaml_data, markdown_sections = parse_dataset_card_structure(content)
            
            if yaml_data:
                structured_found = True
                
                # Extract from YAML
                if 'pretty_name' in yaml_data:
                    result['name'] = yaml_data['pretty_name']
                if 'license' in yaml_data:
                    license_val = yaml_data['license']
                    result['license'] = ', '.join(str(x) for x in license_val) if isinstance(license_val, list) else str(license_val)
                if 'task_categories' in yaml_data:
                    tasks = yaml_data['task_categories']
                    if isinstance(tasks, list):
                        result['dataUseCases'] = ', '.join(str(x).replace('-', ' ') for x in tasks[:3])
            
            # Extract from markdown sections using TF-IDF approach
            if markdown_sections:
                section_texts = list(markdown_sections.values())
                
                # Field-specific extraction from most relevant sections
                field_configs = {
                    'description': {
                        'keywords': ['dataset', 'summary', 'contains', 'problems', 'examples'],
                        'sections': ['dataset summary', 'dataset description']
                    },
                    'dataCollection': {
                        'keywords': ['collected', 'created', 'generated', 'contractors', 'workers'],
                        'sections': ['source data', 'initial data collection']
                    },
                    'annotatorDemographics': {
                        'keywords': ['annotators', 'workers', 'contractors', 'crowd', 'surge'],
                        'sections': ['who are the annotators', 'annotation process']
                    }
                }
                
                for field, config in field_configs.items():
                    if result[field] != "Not mentioned":
                        continue
                    
                    best_section = None
                    best_score = 0
                    
                    # Score sections based on keywords
                    for section_name, section_text in markdown_sections.items():
                        score = 0
                        # Direct section name match
                        if any(target in section_name.lower() for target in config['sections']):
                            score += 10
                        
                        # Keyword matching
                        for keyword in config['keywords']:
                            score += section_text.lower().count(keyword)
                        
                        if score > best_score and len(section_text) > 20:
                            best_score = score
                            best_section = section_text
                    
                    if best_section and best_score > 0:
                        # Extract relevant content from best section
                        if field == 'description':
                            # Get first substantial paragraph
                            paragraphs = [p.strip() for p in best_section.split('\n\n') if len(p.strip()) > 30]
                            if paragraphs:
                                result['description'] = paragraphs[0][:300]
                        elif field == 'dataCollection':
                            # Look for collection-related sentences
                            sentences = sent_tokenize(best_section) if callable(sent_tokenize) else best_section.split('.')
                            for sent in sentences:
                                if any(word in sent.lower() for word in ['collect', 'creat', 'generat', 'hiring']) and len(sent) > 30:
                                    result['dataCollection'] = sent.strip()[:200]
                                    break
                        elif field == 'annotatorDemographics':
                            # Get annotator information
                            if 'more information' not in best_section.lower():
                                result['annotatorDemographics'] = best_section.strip()[:150]
    
    # If no structured data found, use traditional TF-IDF on all content
    if not structured_found:
        all_sentences = []
        for section in sections:
            content = section.get('content', '')
            sentences = sent_tokenize(content) if callable(sent_tokenize) else content.split('.')
            all_sentences.extend([s.strip() for s in sentences if len(s.strip()) > 30])
        
        # Simple keyword-based scoring for remaining fields
        field_keywords = {
            'name': ['introduce', 'present', 'dataset', 'called'],
            'description': ['dataset', 'contains', 'problems', 'examples'],
            'dataCollection': ['collected', 'generated', 'created', 'workers'],
        }
        
        for field, keywords in field_keywords.items():
            if result[field] != "Not mentioned":
                continue
            
            best_sentence = ""
            best_score = 0
            
            for sentence in all_sentences:
                score = sum(1 for keyword in keywords if keyword in sentence.lower())
                if score > best_score:
                    best_score = score
                    best_sentence = sentence
            
            if best_sentence and best_score > 0:
                if field == 'name':
                    # Extract dataset name
                    name_match = re.search(r'(?:introduce|present)\s+([A-Z][A-Za-z0-9\-]{2,30})', best_sentence)
                    if name_match:
                        result['name'] = name_match.group(1)
                else:
                    result[field] = best_sentence[:200]
    
    return save_result(result, output_dir, "tfidf_baseline")


def save_result(result, output_dir, method_name):
    """Save result to file"""
    output_path = Path(output_dir) / f"{method_name}_metadata.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved {method_name} results to {output_path}")
    return result


def run_all_baselines(sections, output_dir):
    """Run all improved baseline methods"""
    print("Running improved baseline methods with structured parsing...")
    
    baselines = [
        ("regex_baseline", regex_baseline),
        ("ner_baseline", ner_baseline), 
        ("tfidf_baseline", tfidf_baseline)
    ]
    
    results = {}
    for name, method in baselines:
        try:
            print(f"\n{'='*50}")
            result = method(sections, output_dir)
            results[name] = result
            
            # Count meaningful fields
            count = sum(1 for v in result.values() 
                       if (isinstance(v, dict) and v.get('name') != 'Not mentioned') or 
                          (isinstance(v, str) and v != 'Not mentioned'))
            print(f"✓ {name} extracted {count} meaningful fields")
            
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            results[name] = create_empty_result()
    
    # Save combined results
    combined_path = Path(output_dir) / "all_baseline_results.json"
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Saved all results to {combined_path}")
    return results