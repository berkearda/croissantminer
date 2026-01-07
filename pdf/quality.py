"""
Chunk quality validation module for CroissantMiner

This module provides functions to validate and filter chunks before LLM processing,
ensuring high-quality content reaches the metadata extraction stage.
"""

import re
from typing import Dict, List


def count_sentences(text: str) -> int:
    """
    Count the number of sentences in text
    """
    # Simple sentence counting based on sentence-ending punctuation
    sentences = re.split(r'[.!?]+\s+', text.strip())
    return len([s for s in sentences if s.strip()])


def has_meaningful_content(chunk: str, min_words: int = 20) -> bool:
    """
    Check if chunk contains meaningful content (not just references, tables, etc.)

    Args:
        chunk: Text chunk to validate
        min_words: Minimum number of words required

    Returns:
        True if chunk has meaningful content
    """
    if not isinstance(chunk, str) or not chunk.strip():
        return False

    # Count words (exclude numbers and single chars)
    words = [w for w in chunk.split() if len(w) > 1 and not w.isdigit()]
    if len(words) < min_words:
        return False

    # Check if chunk is mostly references (e.g., "[1], [2], [3]...")
    reference_ratio = len(re.findall(r'\[\d+\]', chunk)) / max(1, len(words))
    if reference_ratio > 0.3:  # More than 30% references
        return False

    # Check if chunk is mostly numbers/symbols (like tables)
    text_chars = sum(1 for c in chunk if c.isalpha())
    total_chars = len(chunk.replace(' ', '').replace('\n', ''))
    if total_chars > 0:
        text_ratio = text_chars / total_chars
        if text_ratio < 0.4:  # Less than 40% alphabetic characters
            return False

    # Check for at least some sentence structure
    num_sentences = count_sentences(chunk)
    if num_sentences < 2:  # At least 2 sentences
        return False

    return True


def is_likely_table_or_figure(chunk: str) -> bool:
    """
    Detect if chunk is likely a table or figure caption/content

    Args:
        chunk: Text chunk to check

    Returns:
        True if chunk appears to be table/figure content
    """
    # Check for table/figure indicators
    lower_chunk = chunk.lower()

    # Strong indicators at the start
    table_figure_starts = [
        'table ', 'figure ', 'fig. ', 'fig ', 'algorithm ',
        'listing ', 'equation ', 'eq. ', 'eq '
    ]
    for indicator in table_figure_starts:
        if lower_chunk.strip().startswith(indicator):
            return True

    # Check for high density of numbers and special chars (tables)
    lines = chunk.split('\n')
    numeric_heavy_lines = 0
    for line in lines:
        if not line.strip():
            continue
        # Count numeric chars vs text chars
        nums = sum(1 for c in line if c.isdigit())
        letters = sum(1 for c in line if c.isalpha())
        if nums > letters:
            numeric_heavy_lines += 1

    if len(lines) > 0 and numeric_heavy_lines / len(lines) > 0.5:
        return True

    # Check for table column separators
    separator_chars = chunk.count('|') + chunk.count('\t')
    if separator_chars > 10:  # Lots of separators suggests table
        return True

    return False


def is_valid_chunk(
    chunk: str,
    min_length: int = 100,
    max_reference_ratio: float = 0.3,
    min_sentences: int = 2
) -> bool:
    """
    Comprehensive validation of chunk quality

    Args:
        chunk: Text chunk to validate
        min_length: Minimum character length
        max_reference_ratio: Maximum ratio of references to words
        min_sentences: Minimum number of sentences

    Returns:
        True if chunk passes all quality checks
    """
    if not isinstance(chunk, str) or not chunk.strip():
        return False

    # Check minimum length
    if len(chunk.strip()) < min_length:
        return False

    # Check for table/figure content
    if is_likely_table_or_figure(chunk):
        return False

    # Check for meaningful content
    if not has_meaningful_content(chunk, min_words=20):
        return False

    # Check sentence count
    if count_sentences(chunk) < min_sentences:
        return False

    return True


def calculate_chunk_quality_score(chunk: str) -> float:
    """
    Calculate a quality score for a chunk (0.0 to 1.0)

    Higher scores indicate better quality content for metadata extraction.

    Args:
        chunk: Text chunk to score

    Returns:
        Quality score between 0.0 and 1.0
    """
    if not isinstance(chunk, str) or not chunk.strip():
        return 0.0

    score = 0.0
    max_score = 7.0  # Total possible points

    # 1. Length score (up to 1.0)
    length = len(chunk.strip())
    if length >= 500:
        score += 1.0
    elif length >= 200:
        score += 0.7
    elif length >= 100:
        score += 0.4

    # 2. Sentence structure (up to 1.0)
    num_sentences = count_sentences(chunk)
    if num_sentences >= 5:
        score += 1.0
    elif num_sentences >= 3:
        score += 0.7
    elif num_sentences >= 2:
        score += 0.4

    # 3. Word diversity (up to 1.0)
    words = chunk.lower().split()
    if len(words) > 0:
        unique_ratio = len(set(words)) / len(words)
        score += unique_ratio

    # 4. Alphabetic content ratio (up to 1.0)
    text_chars = sum(1 for c in chunk if c.isalpha())
    total_chars = len(chunk.replace(' ', '').replace('\n', ''))
    if total_chars > 0:
        alpha_ratio = text_chars / total_chars
        score += alpha_ratio

    # 5. Not table/figure (up to 1.0)
    if not is_likely_table_or_figure(chunk):
        score += 1.0

    # 6. Low reference density (up to 1.0)
    words_list = chunk.split()
    if len(words_list) > 0:
        ref_ratio = len(re.findall(r'\[\d+\]', chunk)) / len(words_list)
        score += max(0, 1.0 - ref_ratio * 3)

    # 7. Contains key academic keywords (up to 1.0)
    academic_keywords = [
        'dataset', 'data', 'method', 'approach', 'model', 'analysis',
        'results', 'experiment', 'evaluation', 'performance', 'task',
        'training', 'annotation', 'collection', 'source', 'license'
    ]
    keyword_count = sum(1 for kw in academic_keywords if kw in chunk.lower())
    score += min(1.0, keyword_count / 5)  # Max score if 5+ keywords

    # Normalize to 0-1 range
    return min(1.0, score / max_score)


def filter_low_quality_chunks(
    chunks: List[Dict],
    quality_threshold: float = 0.4,
    keep_top_n: int = None
) -> List[Dict]:
    """
    Filter chunks based on quality score

    Args:
        chunks: List of chunk dictionaries with 'content' field
        quality_threshold: Minimum quality score to keep (0.0 to 1.0)
        keep_top_n: If specified, keep only top N chunks by quality

    Returns:
        Filtered list of high-quality chunks
    """
    if not chunks:
        return []

    # Calculate quality scores for all chunks
    scored_chunks = []
    for chunk in chunks:
        content = chunk.get('content', '')
        quality_score = calculate_chunk_quality_score(content)
        chunk_with_score = chunk.copy()
        chunk_with_score['quality_score'] = quality_score
        scored_chunks.append(chunk_with_score)

    # Filter by threshold
    filtered = [c for c in scored_chunks if c['quality_score'] >= quality_threshold]

    # If keep_top_n specified, sort and take top N
    if keep_top_n is not None and keep_top_n < len(filtered):
        filtered = sorted(filtered, key=lambda x: x['quality_score'], reverse=True)
        filtered = filtered[:keep_top_n]

    return filtered


def validate_chunk_list(chunks: List[Dict], verbose: bool = False) -> Dict:
    """
    Validate a list of chunks and return statistics

    Args:
        chunks: List of chunk dictionaries
        verbose: If True, print detailed statistics

    Returns:
        Dictionary with validation statistics
    """
    if not chunks:
        return {
            'total_chunks': 0,
            'valid_chunks': 0,
            'invalid_chunks': 0,
            'avg_quality_score': 0.0,
            'quality_distribution': {}
        }

    total = len(chunks)
    valid = 0
    quality_scores = []

    for chunk in chunks:
        content = chunk.get('content', '')
        if is_valid_chunk(content):
            valid += 1
        score = calculate_chunk_quality_score(content)
        quality_scores.append(score)

    avg_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    # Quality distribution
    distribution = {
        'excellent (>0.8)': sum(1 for s in quality_scores if s > 0.8),
        'good (0.6-0.8)': sum(1 for s in quality_scores if 0.6 <= s <= 0.8),
        'fair (0.4-0.6)': sum(1 for s in quality_scores if 0.4 <= s < 0.6),
        'poor (<0.4)': sum(1 for s in quality_scores if s < 0.4)
    }

    stats = {
        'total_chunks': total,
        'valid_chunks': valid,
        'invalid_chunks': total - valid,
        'avg_quality_score': avg_score,
        'quality_distribution': distribution
    }

    if verbose:
        print(f"\nChunk Quality Statistics:")
        print(f"  Total chunks: {total}")
        print(f"  Valid chunks: {valid} ({100*valid/total:.1f}%)")
        print(f"  Invalid chunks: {total-valid}")
        print(f"  Average quality score: {avg_score:.3f}")
        print(f"\nQuality Distribution:")
        for level, count in distribution.items():
            print(f"  {level}: {count} ({100*count/total:.1f}%)")

    return stats
