""" Section selection for metadata extraction """

import re

def select_relevant_sections(sections, max_sections=15, top_tfidf_sections=5):
    """
    Select Introduction, Abstract and Dataset related sections based on both
    section titles and TF-IDF scores (if available).

    Args:
        sections (list): List of section dictionaries
        max_sections (int): Maximum number of sections to return
        top_tfidf_sections (int): Maximum number of TF-IDF based sections to return

    Returns:
        list: Filtered list of relevant sections
    """
    print(f"Selecting relevant sections from {len(sections)} total sections")

    # Initialize categories
    abstract_intro_sections = []
    dataset_sections_by_title = []
    methods_sections = []
    rai_sections = []  # New: RAI sections
    tfidf_sections = []
    excluded = []

    # Keywords for INCLUSION only
    abstract_intro_keywords = ['abstract', 'introduction']
    dataset_keywords = ['dataset', 'data set', 'corpus', 'data']
    methods_keywords = ['method', 'approach', 'experiment']
    rai_keywords = ['ethic', 'limitation', 'broader', 'impact', 'bias', 'fairness', 'privacy']

    # İlk geçiş: Bölümleri kategorilere ayır
    for section in sections:
        section_name = section['section_name'].lower()

        # Kısa içerikli bölümleri atla
        if len(section['content']) < 100:
            continue

        # TF-IDF ile tespit edilen bölümleri ayrı bir listeye topla
        # LOWERED threshold from 1.0 to 0.4 to catch more sections
        if 'selection_method' in section and section.get('selection_method') == 'tfidf' and section.get('tfidf_score', 0) >= 0.4:
            tfidf_sections.append(section)
            continue

        # DON'T auto-exclude Related Work - it might contain dataset info!
        # Only exclude if it's very short or clearly just citations
        # (Removed the automatic exclusion)

        # Abstract ve Introduction bölümlerini seç
        if any(k in section_name for k in abstract_intro_keywords):
            abstract_intro_sections.append(section)
            continue

        # Başlığına göre Dataset bölümlerini seç
        if any(k in section_name for k in dataset_keywords):
            dataset_sections_by_title.append(section)
            continue

        # Methods/Experiments sections
        if any(k in section_name for k in methods_keywords):
            methods_sections.append(section)
            continue

        # RAI sections (Ethics, Limitations, etc.)
        if any(k in section_name for k in rai_keywords):
            rai_sections.append(section)
            continue

        excluded.append(section)
    
    # TF-IDF skorlarına göre sırala ve sadece en yüksek skorlu top_tfidf_sections kadarını al
    if tfidf_sections:
        tfidf_sections.sort(key=lambda x: -x.get('tfidf_score', 0))  # Yüksek skorlar önce
        tfidf_sections = tfidf_sections[:top_tfidf_sections]  # Sadece en yüksek top_tfidf_sections'ı al

    # Bölümleri öncelik sırasına göre birleştir
    # Priority: Abstract/Intro > RAI > Dataset > Methods > TF-IDF
    selected = (abstract_intro_sections +
                rai_sections +              # High priority for RAI sections!
                dataset_sections_by_title +
                methods_sections +
                tfidf_sections)

    # Maksimum bölüm sayısına kes
    selected = selected[:max_sections]

    # Seçim özetini yazdır
    print(f"\nSection selection summary:")
    print(f"- Abstract/Intro sections: {len(abstract_intro_sections)}")
    print(f"- RAI sections (Ethics/Limitations): {len(rai_sections)}")
    print(f"- Dataset sections (by title): {len(dataset_sections_by_title)}")
    print(f"- Methods sections: {len(methods_sections)}")
    print(f"- Additional sections (by TF-IDF): {len(tfidf_sections)}")
    print(f"- Excluded: {len(excluded)}")
    print(f"Total selected: {len(selected)} sections")

    # Seçilen bölüm adlarını yazdır
    print("\nSelected sections:")
    for i, section in enumerate(selected):
        selection_info = ""
        if 'selection_method' in section and section['selection_method'] == 'tfidf':
            selection_info = f" (TF-IDF score: {section.get('tfidf_score', 0):.4f})"
        print(f"{i+1}. {section['section_name']}{selection_info}")

    return selected