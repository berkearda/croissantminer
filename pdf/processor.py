"""
Robust section extractor for academic papers with integrated fix for spaced headers,
sequential number logic, and advanced TF-IDF based content filtering.
"""

import regex as re
import json
import numpy as np
from pathlib import Path
import datetime
from sklearn.feature_extraction.text import TfidfVectorizer

def clean_text(text):
    """
    Clean text extracted from PDF
    Handles OCR errors, hyphenation, encoding issues
    """
    if not isinstance(text, str):
        return ""

    # Basic cleaning
    text = text.replace("[PAGE_BREAK]", "\n")
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)  # Remove standalone page numbers

    # Fix common OCR errors
    # Ligatures
    text = text.replace("ﬁ", "fi")
    text = text.replace("ﬂ", "fl")
    text = text.replace("ﬀ", "ff")
    text = text.replace("ﬃ", "ffi")
    text = text.replace("ﬄ", "ffl")

    # Common misread characters
    text = text.replace("rn", "m")  # Only when it looks wrong in context
    text = text.replace("vv", "w")  # Double v misread as w

    # Fix hyphenation across line breaks
    # Pattern: word- \n word -> word-word or just word depending on context
    # For now, we'll rejoin hyphenated words (common in academic papers)
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

    # Unicode normalization (NFC form - composed characters)
    import unicodedata
    text = unicodedata.normalize('NFC', text)

    # Fix multiple spaces
    text = re.sub(r' +', ' ', text)

    # Fix multiple newlines (keep max 2 for paragraph breaks)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def preprocess_spaced_headers(text):
    """
    Fix section headers where first letter is separated like "I NTRODUCTION" -> "INTRODUCTION"
    """
    # Pattern to find headers with spaced first letter
    # This matches patterns like "1 I NTRODUCTION" or "2 D ATASET" 
    spaced_header_pattern = re.compile(
        r'(\d+)?\s+([A-Z])\s+([A-Z][A-Za-z]+)',
        re.MULTILINE
    )
    
    # Function to join the spaced first letter with the rest of the word
    def fix_spaced_header(match):
        number = match.group(1) or ""
        first_letter = match.group(2)
        rest_of_word = match.group(3)
        
        if number:
            return f"{number} {first_letter}{rest_of_word}"
        else:
            return f"{first_letter}{rest_of_word}"
    
    # Apply the fix
    preprocessed_text = re.sub(spaced_header_pattern, fix_spaced_header, text)
    
    # Also fix completely spaced headers (like "A B S T R A C T")
    all_caps_pattern = re.compile(r'([A-Z])\s+([A-Z])\s+([A-Z])')
    
    while re.search(all_caps_pattern, preprocessed_text):
        preprocessed_text = re.sub(r'([A-Z])\s+([A-Z])', r'\1\2', preprocessed_text)
    
    return preprocessed_text

def preprocess_for_section_detection(text):
    """
    Preprocess text for better section detection
    """
    # First fix spaced headers
    text = preprocess_spaced_headers(text)
    
    # Özel düzeltme: "2020 ABSTRACTTHIS" gibi birleşik abstract başlıklarını ayır
    text = re.sub(r'(\d{4})\s+(ABSTRACT)([A-Z]+)', r'\1\nABSTRACT \3', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Convert section titles after numbers to uppercase
    def uppercase_section_title(match):
        number = match.group(1)
        title = match.group(2).upper()
        return f"{number} {title}"
    
    # Convert titles that start with capital letter to all caps
    text = re.sub(r'(\d+\s+)([A-Z][a-zA-Z]+(?:\s+[a-zA-Z]+)*)', uppercase_section_title, text)
    
    # Handle cases with no space between number and title
    # Example: "1.INTRODUCTION" -> "1. INTRODUCTION"
    text = re.sub(r'(\d+)\.([A-Z]+)', r'\1. \2', text)
    
    # Handle cases with no space between number and title (without dot)
    # Example: "1INTRODUCTION" -> "1 INTRODUCTION"
    text = re.sub(r'(\d+)([A-Z]{3,})', r'\1 \2', text)
    
    # Fix common formatting issues with headers
    # 1. Add newlines before common section headers in all caps
    for header in ["ABSTRACT", "INTRODUCTION", "METHOD", "DATASET", "DATA", "EXPERIMENT", 
                  "RESULT", "DISCUSSION", "CONCLUSION", "REFERENCE"]:
        text = re.sub(r'([^\n])\s+(' + header + r')\s', r'\1\n\2 ', text, flags=re.IGNORECASE)
    
    # 2. Add newlines before numbered sections (e.g., "1 Introduction", "2.1 Dataset")
    text = re.sub(r'([^\n])\s+(\d+(?:\.\d+)?)\s+([A-Z][a-zA-Z]+)', r'\1\n\2 \3', text)
    
    # 3. Handle Abstract separately - often it's not numbered
    text = re.sub(r'([^\n])\s+(Abstract|ABSTRACT)(\s|\n)', r'\1\nAbstract\3', text)

    # Handle "1.\nIntroduction" or "2.\nDataset" → convert to "1. INTRODUCTION"
    text = re.sub(r'(\n|\s)(\d+)\.(\s*\n\s*)([A-Z][a-zA-Z]+)',
                lambda m: f"\n{m.group(2)}. {m.group(4).upper()}",
                text)

    return text

def is_likely_section_header(section_num, section_title):
    """
    Filter out false positive section headers (figure labels, table entries, etc.)

    Args:
        section_num: The section number (e.g., "1", "3.2")
        section_title: The section title text

    Returns:
        bool: True if likely a real section header, False if likely noise
    """
    # Parse section number
    try:
        num_parts = [int(p) for p in section_num.split('.') if p]
    except:
        return False

    if not num_parts:
        return False

    # Rule 1: Section numbers should be reasonable
    # Main sections typically go from 1-10, subsections don't exceed 20
    if num_parts[0] > 15:  # Main section number > 15 is suspicious
        return False

    if any(part > 25 for part in num_parts[1:]):  # Subsection numbers > 25 suspicious
        return False

    # Rule 2: Very large numbers are likely from figures/tables/years
    if num_parts[0] > 100:  # e.g., "8000 TRAINING SET SIZE"
        return False

    # Rule 3: 4-digit numbers are likely years in references
    if 1900 <= num_parts[0] <= 2100:  # e.g., "2020 CONFERENCE..."
        return False

    # Rule 4: Check if title looks like a valid section title
    title_lower = section_title.lower()

    # Common valid section titles
    valid_keywords = [
        'introduction', 'background', 'related', 'work', 'method', 'approach',
        'dataset', 'data', 'experiment', 'result', 'evaluation', 'discussion',
        'conclusion', 'future', 'limitation', 'ethics', 'broader', 'impact',
        'appendix', 'supplementary', 'acknowledgment', 'reference',
        'abstract', 'summary', 'overview', 'analysis', 'implementation',
        'model', 'architecture', 'training', 'inference', 'setup', 'baseline',
        'ablation', 'qualitative', 'quantitative', 'comparison', 'task'
    ]

    # If title contains any valid keyword, likely a real section
    if any(keyword in title_lower for keyword in valid_keywords):
        return True

    # Rule 5: Reject if title looks like noise
    # Common false positive patterns
    noise_patterns = [
        'epoch', 'figure', 'table', 'size', 'number', 'optimizer',
        'temperature', 'completion', 'sample', 'voting', 'hyperparameter',
        'value', 'adam', 'sgd', 'her', 'his', 'the', 'and', 'or',
        'nov', 'dec', 'jan', 'feb', 'mar', 'apr', 'may', 'jun',
        'jul', 'aug', 'sep', 'oct',  # month abbreviations
        'et al', 'al'  # author name patterns
    ]

    # If title is ONLY noise words (not part of larger title), reject
    title_words = title_lower.split()
    if len(title_words) <= 3 and all(any(noise in word for noise in noise_patterns) for word in title_words):
        return False

    # Rule 6: Reject author names (e.g., "2 RANJAY KRISHNA ET AL")
    if 'et al' in title_lower or title_lower.endswith(' al'):
        return False

    # Rule 6: Very short titles (1-2 words) without valid keywords are suspicious
    if len(title_words) <= 2 and not any(keyword in title_lower for keyword in valid_keywords):
        return False

    # If we get here, it's probably valid
    return True


def find_all_section_headers(text):
    """
    Find all potential section headers in the text using multiple patterns.
    Supports both numbered and unnumbered sections.
    Filters out false positives like figure labels, table entries, etc.

    Returns a list of tuples:
    (start_pos, end_pos, section_number, section_title, full_header)
    """
    headers = []

    # Look for Abstract only at the beginning
    beginning_text = text[:2000]
    abstract_pattern = re.compile(r'(?:^|\n)\s*(ABSTRACT|Abstract)(?=\s|\n|$)', re.MULTILINE)

    for match in abstract_pattern.finditer(beginning_text):
        start = match.start()
        end = match.end()
        section_num = "0"
        section_title = match.group(1).strip()
        full_header = match.group(0).strip()
        headers.append((start, end, section_num, section_title, full_header))
        print(f"Found Abstract at the beginning: {full_header}")

    # Patterns for numbered headers
    # Only match sections with reasonable structure: 1-2 digit numbers, possibly with subsection
    pattern1 = re.compile(r'(?:^|\n)\s*(\d{1,2}(?:\.\d{1,2}){0,3})\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)', re.MULTILINE)
    pattern2 = re.compile(r'(?:^|\n)\s*(\d{1,2}(?:\.\d{1,2}){0,3})\s+([A-Z][A-Z]+(?:\s+[A-Z][A-Z]+)*)', re.MULTILINE)
    pattern_dot = re.compile(r'(?:^|\n)\s*(\d{1,2}\.)\s+([A-Z][A-Z]+(?:\s+[A-Z][A-Z]+)*)', re.MULTILINE)

    # Process numbered section patterns
    for pattern_idx, pattern in enumerate([pattern1, pattern2, pattern_dot]):
        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()
            section_num = match.group(1)
            # Nokta ile biten bölüm numaralarını temizle
            if section_num.endswith('.'):
                section_num = section_num[:-1]

            raw_title = match.group(2).strip()

            title_words = raw_title.split()
            capitalized_words = []
            for word in title_words:
                if pattern_idx == 0 and word[0].isupper():
                    capitalized_words.append(word)
                elif pattern_idx == 1 and word.isupper():
                    capitalized_words.append(word)
                else:
                    break

            section_title = " ".join(capitalized_words)
            if not section_title:
                continue

            # FILTER: Check if this is likely a real section header
            if not is_likely_section_header(section_num, section_title):
                continue  # Skip false positives

            full_header = section_num + " " + section_title
            end = start + len(full_header)

            if section_title.isupper():
                section_title = section_title.title()

            headers.append((start, end, section_num, section_title, full_header))

    # NEW: Pattern for UNNUMBERED sections
    # Common section titles that appear without numbers
    unnumbered_pattern = re.compile(
        r'(?:^|\n)\s*(Introduction|INTRODUCTION|'
        r'Methods?|METHODS?|Methodology|METHODOLOGY|'
        r'Approach|APPROACH|'
        r'Results?|RESULTS?|Findings|FINDINGS|'
        r'Discussion|DISCUSSION|'
        r'Conclusion|CONCLUSION|Conclusions|CONCLUSIONS|'
        r'Related Work|RELATED WORK|'
        r'Background|BACKGROUND|'
        r'Experiments?|EXPERIMENTS?|'
        r'Evaluation|EVALUATION|'
        r'Implementation|IMPLEMENTATION|'
        r'Future Work|FUTURE WORK|'
        r'Limitations?|LIMITATIONS?|'
        r'Ethics Statement|ETHICS STATEMENT|'
        r'Broader Impact|BROADER IMPACT|'
        r'Acknowledgments?|ACKNOWLEDGMENTS?|'
        r'References|REFERENCES)'
        r'(?=\s|\n|$)',
        re.MULTILINE
    )

    # Assign section numbers to unnumbered sections based on position
    unnumbered_counter = 100  # Start at 100 to distinguish from numbered
    for match in unnumbered_pattern.finditer(text):
        start = match.start()
        end = match.end()
        raw_title = match.group(1).strip()

        # Assign pseudo section number
        section_num = str(unnumbered_counter)
        unnumbered_counter += 1

        # Normalize title
        if raw_title.isupper():
            section_title = raw_title.title()
        else:
            section_title = raw_title

        full_header = section_title
        headers.append((start, end, section_num, section_title, full_header))
        print(f"Found unnumbered section: {full_header}")

    # Sort and deduplicate
    headers.sort(key=lambda x: x[0])
    deduplicated_headers = []
    for header in headers:
        if deduplicated_headers and header[0] - deduplicated_headers[-1][0] < 10:
            continue
        deduplicated_headers.append(header)

    return deduplicated_headers

def parse_section_number(section_num):
    """
    Parse section numbers into a list of integers.
    """
    try:
        # Eğer section_num nokta ile bitiyorsa, nokta kaldırılır
        if section_num.endswith('.'):
            section_num = section_num[:-1]
        
        parts = [p for p in section_num.strip().split(".") if p != '']
        return list(map(int, parts))
    except:
        return []

def is_sequential(prev, current):
    """
    Enhanced function to determine if the current section number follows the previous one
    with a more flexible approach appropriate for academic papers.
    Handles both numbered sections (1, 2, 3.1) and unnumbered sections (100, 101, 102).
    """
    if not prev:
        return True  # İlk bölüm her zaman kabul edilir

    # Bölüm numaralarını analiz et
    prev_top_level = prev[0] if prev else 0
    current_top_level = current[0] if current else 0

    # Special case: Unnumbered sections (section numbers >= 100)
    # These are always accepted in sequence
    if current_top_level >= 100:
        return True  # Unnumbered sections always accepted
    
    # 1. ESNEK KURAL: Aynı üst seviyede ilerleyiş
    # Örn: 1, 1.1, 1.2, 1.3, 1.4
    if current_top_level == prev_top_level:
        # Alt seviyeler uyuşuyorsa:
        if len(current) == len(prev) and current[:-1] == prev[:-1]:
            # Alt seviyede makul bir artış olmalı (1.1 -> 1.5 kabul edilebilir)
            # RELAXED: Increased from 3 to 6 to allow gaps like 4.1 -> 4.5
            max_sublevel_gap = 6  # Maksimum 5 alt seviye atlayabilir (4.1 -> 4.6)
            return current[-1] > prev[-1] and current[-1] - prev[-1] <= max_sublevel_gap
        
        # Alt seviye açılışı (1 -> 1.1 veya 1.2 -> 1.2.1)
        elif len(current) == len(prev) + 1 and current[:-1] == prev:
            return True  # Alt bölüme geçiş her zaman kabul edilir
            
        # Alt seviyeden daha derin alt seviyeye sıçrama (1.1 -> 1.2.1)
        # Kabul et ama kontrol yap
        elif len(current) > len(prev):
            # Ortak kısmı kontrol et
            common_length = min(len(prev), len(current) - 1)
            if prev[:common_length] == current[:common_length]:
                return True
                
        return False  # Diğer durumlar
    
    # 2. ESNEK KURAL: Bir sonraki üst seviyeye geçiş
    # Örn: 1.3 -> 2 veya 1.2.3 -> 2
    elif current_top_level > prev_top_level:
        # Üst seviye bölüm geçişleri için makul bir sıçrama olmalı
        max_reasonable_section_jump = 5  # En fazla 4 bölüm atlayabilir
        
        # Ana bölümlerde makul bir sıçrama mı?
        if len(current) == 1:
            top_level_gap = current[0] - prev[0]
            return top_level_gap <= max_reasonable_section_jump
        
        # Alt bölüme direkt geçiş (1 -> 2.1 veya 1.2 -> 2.1)
        elif len(current) > 1:
            top_level_gap = current[0] - prev[0]
            # Yeni bölümün ilk alt bölümü olabilir
            return top_level_gap <= max_reasonable_section_jump
    
    # 3. ESNEK KURAL: Önceki üst seviyeye dönüş (çok nadir)
    # Örn: 2.1 -> 1.4 (normalde beklenmeyen durum)
    else:  # current_top_level < prev_top_level
        # Genelde akademik makalelerde geriye dönüş olmaz,
        # ancak PDF okuma hatası varsa veya özel durumlar için:
        return False  # Bu durumu reddediyoruz
    
    return False  # Varsayılan olarak reddet

def extract_sections(text):
    """
    Extract all valid sections from a paper using ONLY sequential number logic.
    Title validity is ignored - only section numbers are considered.
    First sort headers by section numbers, then apply sequential logic.
    Returns a list of dicts with section info and content.
    """
    processed_text = preprocess_for_section_detection(text)
    headers = find_all_section_headers(processed_text)

    print(f"\nFound {len(headers)} potential section headers:")
    for header in headers:
        print(f"- {header[4]} (Section {header[2]}, Title: {header[3]})")

    # Bölüm numaralarını ayrıştır
    parsed_headers = []
    for start, end, section_num, section_title, full_header in headers:
        num_parts = parse_section_number(section_num)
        section_title_clean = section_title.lower().strip()
        
        # Özet için özel durum
        if "abstract" in section_title_clean:
            num_parts = [0]  # Abstract'i 0 olarak numaralandır
            parsed_headers.append((start, end, section_num, section_title, full_header, num_parts))
            continue
            
        # Giriş için özel durum
        if "introduction" in section_title_clean:
            # Eğer num_parts boşsa veya geçersizse, 1 olarak ayarla
            if not num_parts:
                num_parts = [1]
            parsed_headers.append((start, end, section_num, section_title, full_header, num_parts))
            continue
            
        # Diğer bölümler: Sadece geçerli bir bölüm numarası olması yeterli
        if num_parts:
            parsed_headers.append((start, end, section_num, section_title, full_header, num_parts))
        else:
            print(f"⚠️ Cannot parse section number: {full_header}")

    # Bölümleri numaralarına göre sırala
    def sort_key(header):
        num_parts = header[5]
        # Geçerli bir bölüm numarası yoksa, sonda göster
        if not num_parts:
            return [999]
        return num_parts
    
    # Bölümleri numaralarına göre sırala
    sorted_headers = sorted(parsed_headers, key=sort_key)
    
    print("\nSorted headers by section numbers:")
    for header in sorted_headers:
        print(f"- {header[4]} (Section number: {header[5]})")
    
    # Şimdi sadece sekansiyel mantığı uygula
    valid_headers = []
    all_boundaries = []
    previous_number = []
    
    for start, end, section_num, section_title, full_header, num_parts in sorted_headers:
        # Abstract her zaman dahil edilir
        if "abstract" in section_title.lower():
            valid_headers.append((start, end, section_num, section_title, full_header))
            all_boundaries.append((start, end, section_num, section_title, full_header))
            print(f"✔️ Found and added abstract section: {full_header}")
            continue

        # Introduction her zaman dahil edilir
        if "introduction" in section_title.lower():
            valid_headers.append((start, end, section_num, section_title, full_header))
            all_boundaries.append((start, end, section_num, section_title, full_header))
            previous_number = num_parts
            print(f"✔️ Found and added introduction section: {full_header}")
            continue
        
        # Diğer bölümler için sadece sekansiyel kontrol
        if num_parts and previous_number:  # Önceki bölüm ve geçerli bölüm numarası varsa
            is_seq = is_sequential(previous_number, num_parts)
            if is_seq:
                all_boundaries.append((start, end, section_num, section_title, full_header))
                valid_headers.append((start, end, section_num, section_title, full_header))
                previous_number = num_parts
                print(f"✔️ Added sequential section: {full_header}")
            else:
                print(f"⚠️ Skipping non-sequential section: {full_header}")
        else:
            print(f"⚠️ Skipping section: {full_header} (missing previous number or current number)")

    # Extract content using ALL boundaries as boundaries
    sections = []
    for i, (start, end, section_num, section_title, full_header) in enumerate(all_boundaries):
        content_start = end
        content_end = all_boundaries[i + 1][0] if i < len(all_boundaries) - 1 else len(processed_text)
        content = processed_text[content_start:content_end].strip()

        if len(content) < 50:
            print(f"⚠️ Skipping short section: {full_header}")
            continue

        std_title = section_title.strip()
        if re.search(r'abstract', std_title, re.IGNORECASE):
            std_title = "Abstract"
        elif re.search(r'introduction', std_title, re.IGNORECASE):
            std_title = "Introduction"
        elif re.search(r'dataset', std_title, re.IGNORECASE) or re.search(r'^data$', std_title, re.IGNORECASE):
            std_title = "Dataset"

        sections.append({
            'header': full_header,
            'section_number': section_num,
            'section_title': std_title,
            'content': content,
            'start_pos': start,
            'end_pos': content_end
        })
        print(f"✅ Added section: {full_header} ({len(content)} chars)")

    return sections


def calculate_tfidf_scores(sections):
    """
    Calculate TF-IDF scores for all sections to identify dataset-related content.
    Returns a dictionary mapping section indices to their dataset relevance score.
    """
    # Extract section contents
    contents = [section['content'] for section in sections]
    
    if not contents:
        return {}
    
    # Create TF-IDF vectorizer
    vectorizer = TfidfVectorizer(
        max_features=5000,  # Use top 5000 features
        stop_words='english',  # Remove English stop words
        ngram_range=(1, 2)  # Use unigrams and bigrams
    )
    
    # Compute TF-IDF matrix
    tfidf_matrix = vectorizer.fit_transform(contents)
    feature_names = vectorizer.get_feature_names_out()
    
    # Define dataset-related keywords
    dataset_primary = ['dataset', 'datasets', 'benchmark', 'samples', 'corpus']
    dataset_secondary = [
        'annotation', 'collection', 'instances', 'statistics', 'labeled',
        'images', 'categories', 'objects', 'classes', 'training',
        'test', 'validation', 'split', 'set', 'data'
    ]

    # RAI (Responsible AI) keywords - highly important for Croissant metadata!
    rai_keywords = [
        'consent', 'demographics', 'annotators', 'annotator', 'workers', 'crowdworkers',
        'ethics', 'ethical', 'privacy', 'bias', 'biases', 'fairness', 'fair',
        'limitations', 'limitation', 'risks', 'risk', 'harm', 'harms',
        'compensation', 'paid', 'payment', 'volunteer', 'volunteers',
        'participants', 'participant', 'subjects', 'human', 'humans',
        'sensitive', 'personal', 'identifiable', 'anonymize', 'anonymized',
        'license', 'licensed', 'copyright', 'terms', 'usage', 'restrictions'
    ]

    # Check for bigrams (compound terms)
    dataset_bigrams = [
        'data collection', 'data set', 'training set', 'test set',
        'validation set', 'annotated images', 'labeled data',
        'dataset statistics', 'dataset split', 'data annotation'
    ]

    # RAI bigrams - compound terms related to responsible AI
    rai_bigrams = [
        'informed consent', 'human subjects', 'personal information', 'sensitive information',
        'ethical considerations', 'ethical approval', 'privacy concerns', 'bias mitigation',
        'data privacy', 'crowd workers', 'annotator demographics', 'compensation paid',
        'broader impact', 'potential harms', 'potential risks', 'data protection'
    ]
    
    # Get indices of keywords in the feature_names
    primary_indices = [i for i, feature in enumerate(feature_names) if feature in dataset_primary]
    secondary_indices = [i for i, feature in enumerate(feature_names) if feature in dataset_secondary]
    bigram_indices = [i for i, feature in enumerate(feature_names) if feature in dataset_bigrams]
    rai_indices = [i for i, feature in enumerate(feature_names) if feature in rai_keywords]
    rai_bigram_indices = [i for i, feature in enumerate(feature_names) if feature in rai_bigrams]

    # Calculate a dataset relevance score for each section
    relevance_scores = {}

    for i, section_vector in enumerate(tfidf_matrix):
        # Convert sparse vector to array for easier manipulation
        dense_vector = section_vector.toarray()[0]

        # Calculate scores for different keyword categories
        primary_score = sum(dense_vector[idx] for idx in primary_indices)
        secondary_score = sum(dense_vector[idx] for idx in secondary_indices)
        bigram_score = sum(dense_vector[idx] for idx in bigram_indices)
        rai_score = sum(dense_vector[idx] for idx in rai_indices)
        rai_bigram_score = sum(dense_vector[idx] for idx in rai_bigram_indices)

        # Combined score (weighted)
        # RAI keywords get VERY high weight (3.0) because they're critical for Croissant metadata
        total_score = (
            (primary_score * 2.0) +
            (secondary_score * 1.0) +
            (bigram_score * 2.5) +
            (rai_score * 3.0) +           # High weight for RAI keywords!
            (rai_bigram_score * 4.0)      # Even higher for RAI bigrams!
        )

        # Normalize by section length (to avoid favoring very long sections)
        word_count = len(sections[i]['content'].split())
        normalized_score = total_score * 1000 / max(1, word_count)  # Per 1000 words

        relevance_scores[i] = normalized_score

    return relevance_scores


def extract_targeted_sections_with_tfidf(text):
    """
    Extract Abstract, Introduction, and Dataset-related sections using both
    title-based and advanced content-based TF-IDF filtering.
    """
    # İlk olarak tüm bölümleri çıkar
    all_sections = extract_sections(text)
    title_targeted_sections = []
    
    # 1. İlk Aşama: Başlık tabanlı filtreleme (Mevcut yaklaşım)
    for section in all_sections:
        title_lower = section['section_title'].lower()
        
        # Abstract
        if title_lower == "abstract":
            title_targeted_sections.append({
                'header': section['header'],
                'section_number': section['section_number'],
                'section_title': 'Abstract',
                'content': section['content'],
                'selection_method': 'title'
            })
            print(f"Added Abstract section ({len(section['content'])} chars)")
            continue
            
        # Introduction
        if title_lower == "introduction":
            title_targeted_sections.append({
                'header': section['header'],
                'section_number': section['section_number'],
                'section_title': 'Introduction',
                'content': section['content'],
                'selection_method': 'title'
            })
            print(f"Added Introduction section ({len(section['content'])} chars)")
            continue
            
        # Dataset/Data/Corpus
        if "dataset" in title_lower or "data" in title_lower or "corpus" in title_lower:
            title_targeted_sections.append({
                'header': section['header'],
                'section_number': section['section_number'],
                'section_title': 'Dataset',
                'content': section['content'],
                'selection_method': 'title'
            })
            print(f"Added Dataset section: {section['header']} ({len(section['content'])} chars)")
            continue

        # RAI-related sections (Ethics, Limitations, Broader Impact, etc.)
        # These often contain critical metadata for Croissant
        rai_keywords_in_title = ['ethic', 'limitation', 'broader', 'impact', 'bias',
                                 'fairness', 'privacy', 'risk', 'harm', 'consent']
        if any(keyword in title_lower for keyword in rai_keywords_in_title):
            title_targeted_sections.append({
                'header': section['header'],
                'section_number': section['section_number'],
                'section_title': 'RAI',  # Mark as Responsible AI section
                'content': section['content'],
                'selection_method': 'title'
            })
            print(f"Added RAI section: {section['header']} ({len(section['content'])} chars)")
            continue

        # Methods/Experiments sections (often contain dataset details)
        if "method" in title_lower or "experiment" in title_lower or "approach" in title_lower:
            title_targeted_sections.append({
                'header': section['header'],
                'section_number': section['section_number'],
                'section_title': 'Methods',
                'content': section['content'],
                'selection_method': 'title'
            })
            print(f"Added Methods section: {section['header']} ({len(section['content'])} chars)")
    
    # Başlık tabanlı hedeflenen bölümleri ID'lerine göre işaretleyin
    title_targeted_ids = set()
    for section in title_targeted_sections:
        for i, original_section in enumerate(all_sections):
            if section['header'] == original_section['header']:
                title_targeted_ids.add(i)
                break
    
    # 2. İkinci Aşama: İçerik tabanlı TF-IDF filtreleme
    relevance_scores = calculate_tfidf_scores(all_sections)

    # Relevance scores için eşik değeri belirle
    # LOWERED from 0.5 to 0.3 to catch more RAI-relevant sections
    # Adaptive threshold: use lower value if we have many sections
    if len(all_sections) > 10:
        tfidf_threshold = 0.3  # More lenient for longer papers
    else:
        tfidf_threshold = 0.4  # Slightly stricter for short papers
    
    # TFIDF'a göre ek bölümler ekleyin
    content_targeted_sections = []
    
    for i, section in enumerate(all_sections):
        # Eğer başlık tabanlı filtrelemeden geçmişse, atla
        if i in title_targeted_ids:
            continue
        
        # Eğer yüksek TF-IDF skoru varsa, bu bölümü Dataset olarak dahil et
        if i in relevance_scores and relevance_scores[i] > tfidf_threshold:
            content_targeted_sections.append({
                'header': section['header'],
                'section_number': section['section_number'],
                'section_title': 'Dataset',  # İçerik bazlı seçildiği için Dataset olarak işaretle
                'content': section['content'],
                'selection_method': 'tfidf',
                'tfidf_score': relevance_scores[i]
            })
            print(f"Added Dataset section based on TF-IDF: {section['header']} (score: {relevance_scores[i]:.4f}, {len(section['content'])} chars)")
    
    # Tüm hedeflenen bölümleri birleştir
    targeted_sections = title_targeted_sections + content_targeted_sections
    
    # TF-IDF skorlarına göre sırala (en önemliden en az önemliye)
    targeted_sections.sort(key=lambda x: 
                         float('inf') if x['selection_method'] == 'title' else -x.get('tfidf_score', 0))
    
    print(f"\nFound {len(targeted_sections)} targeted sections:")
    for section in targeted_sections:
        method = section['selection_method']
        score_info = f" (TF-IDF score: {section.get('tfidf_score', 0):.4f})" if method == "tfidf" else ""
        print(f"- {section['section_title']} (section {section['section_number']}): {len(section['content'])} chars, selected by {method}{score_info}")
    
    return targeted_sections


# Geriye dönük uyumluluk için eski fonksiyon adı
def extract_targeted_sections(text):
    """
    Backward compatibility function that calls extract_targeted_sections_with_tfidf.
    """
    return extract_targeted_sections_with_tfidf(text)


def count_tokens(text, encoding_name="cl100k_base"):
    """
    Count tokens in text using tiktoken encoder
    """
    try:
        import tiktoken
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except:
        # Fallback to character-based estimation (1 token ≈ 4 chars)
        return len(text) // 4


def split_into_chunks(content, max_chunk_tokens=3000, overlap_tokens=200):
    """
    Split content into chunks of maximum token size with overlap.
    Preserves paragraph and sentence boundaries where possible.

    Args:
        content: Text to chunk
        max_chunk_tokens: Maximum tokens per chunk (default 3000, ~12000 chars)
        overlap_tokens: Tokens to overlap between chunks (default 200)

    Returns:
        List of text chunks with overlap for context preservation
    """
    if not isinstance(content, str) or not content:
        return []

    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        use_tokens = True
    except:
        # Fallback to character-based if tiktoken not available
        use_tokens = False
        max_chunk_tokens = max_chunk_tokens * 4  # Convert to chars
        overlap_tokens = overlap_tokens * 4

    chunks = []

    # Split by paragraphs
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
    if not paragraphs:
        paragraphs = [content]

    current_chunk = ""
    current_chunk_tokens = 0
    overlap_buffer = []  # Store recent paragraphs for overlap
    overlap_buffer_tokens = 0

    for para in paragraphs:
        # Skip empty paragraphs
        if not para:
            continue

        para_tokens = count_tokens(para) if use_tokens else len(para)

        # Case 1: Paragraph is too large - split into sentences
        if para_tokens > max_chunk_tokens:
            # Finish current chunk if exists
            if current_chunk_tokens > 0:
                chunks.append(current_chunk.strip())
                # Keep overlap from end of chunk
                overlap_buffer = [current_chunk]
                overlap_buffer_tokens = current_chunk_tokens
                current_chunk = ""
                current_chunk_tokens = 0

            # Split large paragraph into sentences
            try:
                import nltk
                sentences = nltk.sent_tokenize(para)
            except:
                # Fallback: split by sentence-ending punctuation
                sentences = re.split(r'(?<=[.!?])\s+', para)

            temp_chunk = ""
            temp_chunk_tokens = 0

            for sentence in sentences:
                if not sentence:
                    continue

                sentence_tokens = count_tokens(sentence) if use_tokens else len(sentence)

                # If single sentence is too large, split it forcefully
                if sentence_tokens > max_chunk_tokens:
                    if temp_chunk_tokens > 0:
                        chunks.append(temp_chunk.strip())
                        temp_chunk = ""
                        temp_chunk_tokens = 0

                    # Split long sentence into smaller parts
                    words = sentence.split()
                    part = ""
                    part_tokens = 0
                    for word in words:
                        word_tokens = count_tokens(word) if use_tokens else len(word)
                        if part_tokens + word_tokens + 1 <= max_chunk_tokens:
                            part += (" " if part else "") + word
                            part_tokens += word_tokens + (1 if part else 0)
                        else:
                            if part:
                                chunks.append(part.strip())
                            part = word
                            part_tokens = word_tokens
                    if part:
                        chunks.append(part.strip())

                # Sentence fits in temp chunk
                elif temp_chunk_tokens + sentence_tokens + 1 <= max_chunk_tokens:
                    temp_chunk += (" " if temp_chunk else "") + sentence
                    temp_chunk_tokens += sentence_tokens + (1 if temp_chunk else 0)
                # Sentence doesn't fit - start new chunk
                else:
                    chunks.append(temp_chunk.strip())
                    temp_chunk = sentence
                    temp_chunk_tokens = sentence_tokens

            # Add last temp chunk
            if temp_chunk_tokens > 0:
                chunks.append(temp_chunk.strip())

        # Case 2: Paragraph fits in current chunk
        elif current_chunk_tokens + para_tokens + 2 <= max_chunk_tokens:
            current_chunk += ("\n\n" if current_chunk else "") + para
            current_chunk_tokens += para_tokens + (2 if current_chunk else 0)

            # Update overlap buffer
            overlap_buffer.append(para)
            overlap_buffer_tokens += para_tokens + 2

            # Trim overlap buffer to stay within overlap size
            while overlap_buffer and overlap_buffer_tokens > overlap_tokens:
                removed = overlap_buffer.pop(0)
                removed_tokens = count_tokens(removed) if use_tokens else len(removed)
                overlap_buffer_tokens -= removed_tokens + 2

        # Case 3: Paragraph doesn't fit - finish chunk and start new with overlap
        else:
            chunks.append(current_chunk.strip())

            # Start new chunk with overlap from previous chunk
            if overlap_buffer:
                current_chunk = "\n\n".join(overlap_buffer) + "\n\n" + para
                current_chunk_tokens = overlap_buffer_tokens + para_tokens + 2
            else:
                current_chunk = para
                current_chunk_tokens = para_tokens

            # Reset overlap buffer with current paragraph
            overlap_buffer = [para]
            overlap_buffer_tokens = para_tokens

    # Add final chunk
    if current_chunk_tokens > 0:
        chunks.append(current_chunk.strip())

    return chunks

def process_sections(sections):
    """
    Process sections and add chunks for LLM processing
    """
    processed_sections = []
    
    for section in sections:
        content = section.get('content', '')
        chunks = split_into_chunks(content)
        
        processed_section = {
            'header': section.get('header', 'Unknown'),
            'section_number': section.get('section_number', 'N/A'),
            'section_title': section.get('section_title', 'Unknown'),
            'content': content,
            'chunks': chunks,
            'num_chunks': len(chunks),
            'selection_method': section.get('selection_method', 'unknown')
        }
        
        # Eğer TF-IDF skoru varsa, onu da ekle
        if 'tfidf_score' in section:
            processed_section['tfidf_score'] = section['tfidf_score']
            
        processed_sections.append(processed_section)
    
    return processed_sections

def chunk_for_llm(processed_sections, max_chunk_tokens=3000, overlap_tokens=200):
    """
    Prepare chunks for LLM processing with token-aware chunking

    Args:
        processed_sections: Sections to chunk
        max_chunk_tokens: Maximum tokens per chunk (default 3000)
        overlap_tokens: Overlap between chunks in tokens (default 200)
    """
    llm_ready_chunks = []

    for section in processed_sections:
        chunks = section.get('chunks', [])
        num_chunks = len(chunks)

        if num_chunks == 0:
            continue

        base_header = section.get('header', 'Unknown Section')
        section_title = section.get('section_title', 'Unknown Title')
        section_number = section.get('section_number', 'N/A')
        selection_method = section.get('selection_method', 'unknown')

        if num_chunks == 1:
            # If only one chunk, use the original section header
            chunk_info = {
                'section_name': base_header,
                'content': chunks[0],
                'section_title': section_title,
                'section_number': section_number,
                'selection_method': selection_method,
                'token_count': count_tokens(chunks[0])
            }

            # TF-IDF skoru varsa ekle
            if 'tfidf_score' in section:
                chunk_info['tfidf_score'] = section['tfidf_score']

            llm_ready_chunks.append(chunk_info)
        else:
            # If multiple chunks, add part number to header
            for i, chunk in enumerate(chunks):
                chunk_header = f"{base_header} (part {i+1}/{num_chunks})"
                chunk_info = {
                    'section_name': chunk_header,
                    'content': chunk,
                    'section_title': section_title,
                    'section_number': section_number,
                    'selection_method': selection_method,
                    'token_count': count_tokens(chunk)
                }

                # TF-IDF skoru varsa ekle
                if 'tfidf_score' in section:
                    chunk_info['tfidf_score'] = section['tfidf_score']

                llm_ready_chunks.append(chunk_info)
    
    return llm_ready_chunks

def save_processed_paper(paper_data, output_path):
    """
    Save processed paper data to JSON file
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(paper_data, f, indent=2, ensure_ascii=False)
        print(f"Saved processed paper to {output_path}")
    except Exception as e:
        print(f"Error saving processed paper: {e}")

def process_paper(cleaned_text, output_path=None, debug=False):
    """
    Process a paper and extract sections
    """
    print("--- Starting Paper Processing ---")
    start_time = datetime.datetime.now()
    
    # Extract targeted sections using advanced TF-IDF filtering
    print("Step 1: Extracting targeted sections with TF-IDF filtering...")
    targeted_sections = extract_targeted_sections_with_tfidf(cleaned_text)
    
    print(f"Found {len(targeted_sections)} targeted sections:")
    for section in targeted_sections:
        method = section.get('selection_method', 'unknown')
        score_info = f" (TF-IDF score: {section.get('tfidf_score', 0):.4f})" if method == "tfidf" else ""
        print(f"- {section['section_title']} (section {section['section_number']}): {len(section['content'])} chars, selected by {method}{score_info}")
    
    # Process sections
    print("\nStep 2: Processing sections and creating chunks...")
    processed_sections = process_sections(targeted_sections)
    
    # Prepare result
    llm_chunks = chunk_for_llm(processed_sections)
    
    paper_data = {
        'sections': processed_sections,
        'llm_chunks': llm_chunks,
        'metadata': {
            'total_targeted_sections_extracted': len(processed_sections),
            'total_llm_chunks_generated': len(llm_chunks),
            'has_abstract': any(s.get('section_title') == 'Abstract' for s in processed_sections),
            'has_introduction': any(s.get('section_title') == 'Introduction' for s in processed_sections),
            'has_dataset_section': any(s.get('section_title') == 'Dataset' for s in processed_sections),
            'processing_timestamp': start_time.isoformat(),
            'processing_duration_seconds': (datetime.datetime.now() - start_time).total_seconds(),
        }
    }
    
    # Save to file if path is provided
    if output_path:
        save_processed_paper(paper_data, output_path)
    
    print("--- Paper Processing Completed ---")
    return paper_data

def test_extraction(text):
    """
    Test the extraction on a sample text
    """
    print("Testing section extraction...")
    # First preprocess to fix spaced headers
    preprocessed_text = preprocess_spaced_headers(text)
    
    # Print first 500 characters of preprocessed text
    print("\nFirst 500 characters of preprocessed text:")
    print(preprocessed_text[:500])
    
    # Find all section headers
    print("\nFinding all section headers...")
    all_sections = extract_sections(preprocessed_text)
    
    print(f"\nExtracted {len(all_sections)} sections:")
    for section in all_sections:
        print(f"- {section['header']} ({len(section['content'])} chars)")
        print(f"  First 50 chars: {section['content'][:50]}...")
    
    # Extract targeted sections with TF-IDF
    print("\nExtracting targeted sections with TF-IDF analysis...")
    targeted = extract_targeted_sections_with_tfidf(preprocessed_text)
    print(f"Found {len(targeted)} targeted sections:")
    for section in targeted:
        method = section.get('selection_method', 'unknown')
        score_info = f" (TF-IDF score: {section.get('tfidf_score', 0):.4f})" if method == "tfidf" else ""
        print(f"- {section['section_title']} selected by {method}{score_info}")
    
    return all_sections