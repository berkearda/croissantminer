"""
Enhance existing processed papers with dataset card metadata
"""

import argparse
import json
from pathlib import Path
from metadata.card_parser import parse_dataset_card, save_card_metadata
from metadata.unifier import convert_to_croissant
from config import PROCESSED_DATA_DIR, DATACARD_DIR


def enhance_paper_with_card(paper_id, dataset_card_path):
    """
    Enhance existing processed paper with dataset card metadata
    
    Args:
        paper_id (str): ID of the already processed paper
        dataset_card_path (str): Path to dataset card file
    """
    print(f"===== Enhancing paper '{paper_id}' with dataset card =====")
    
    # Check if paper directory exists
    paper_dir = PROCESSED_DATA_DIR / paper_id
    if not paper_dir.exists():
        print(f"✗ Paper directory not found: {paper_dir}")
        print("Available papers:")
        for p in PROCESSED_DATA_DIR.iterdir():
            if p.is_dir():
                print(f"  - {p.name}")
        return
    
    # Load existing unified metadata
    existing_metadata_path = paper_dir / "unified_metadata.json"
    if not existing_metadata_path.exists():
        print(f"✗ No existing unified metadata found at: {existing_metadata_path}")
        return
    
    print(f"✓ Found existing metadata at: {existing_metadata_path}")
    
    try:
        with open(existing_metadata_path, 'r', encoding='utf-8') as f:
            pdf_metadata = json.load(f)
        print("✓ Loaded existing PDF metadata")
    except Exception as e:
        print(f"✗ Error loading existing metadata: {str(e)}")
        return
    
    # Extract metadata from dataset card
    print(f"\n----- Extracting from dataset card: {dataset_card_path} -----")
    card_metadata = parse_dataset_card(dataset_card_path)
    
    if not card_metadata:
        print("✗ Failed to extract metadata from dataset card")
        return
    
    # Save card metadata
    card_output = paper_dir / "card_metadata.json"
    save_card_metadata(card_metadata, card_output)
    
    # Merge metadata using simple logical approach
    print("\n----- Merging PDF and card metadata -----")
    enhanced_metadata = merge_metadata_sources(pdf_metadata, card_metadata)
    
    # Save enhanced metadata as unified_metadata2.json (preserve original)
    enhanced_output = paper_dir / "unified_metadata2.json"
    try:
        with open(enhanced_output, 'w', encoding='utf-8') as f:
            json.dump(enhanced_metadata, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved enhanced metadata to: {enhanced_output}")
    except Exception as e:
        print(f"✗ Error saving enhanced metadata: {str(e)}")
        return
    
    # Convert to Croissant format using enhanced metadata
    print("\n----- Converting to Croissant format -----")
    croissant_metadata = convert_to_croissant(enhanced_metadata, paper_dir)
    
    print(f"\n===== Successfully enhanced paper '{paper_id}' =====")
    print(f"Original metadata preserved: unified_metadata.json")
    print(f"Enhanced metadata saved: unified_metadata2.json")
    print_enhancement_summary(pdf_metadata, card_metadata, enhanced_metadata)


def merge_metadata_sources(pdf_metadata, card_metadata):
    """
    Simple and logical merging: 
    - If dataset card has a field, use it directly (it's authoritative)
    - Otherwise, use PDF metadata
    """
    enhanced = pdf_metadata.copy()
    
    print("----- Applying direct replacement from dataset card -----")
    
    changes_made = []
    
    for field, card_value in card_metadata.items():
        # Skip empty/default values
        if card_value == "Not mentioned":
            continue
            
        # Skip empty creator objects
        if isinstance(card_value, dict) and card_value.get("name") == "Not mentioned":
            continue
            
        current_value = enhanced.get(field, "Not mentioned")
        
        # Dataset card has this field -> use it directly
        if card_value != "Not mentioned":
            enhanced[field] = card_value
            
            if current_value != card_value:
                changes_made.append({
                    'field': field,
                    'action': 'replaced' if current_value != "Not mentioned" else 'added',
                    'old_value': current_value,
                    'new_value': card_value
                })
    
    print(f"✓ Made {len(changes_made)} direct updates from dataset card")
    log_merge_decisions(changes_made)
    
    return enhanced


def log_merge_decisions(changes_made):
    """Log what fields were updated from dataset card"""
    if not changes_made:
        print("ℹ️ No fields were updated (dataset card had no new information)")
        return
        
    print("\n----- Fields Updated from Dataset Card -----")
    
    added_fields = [c for c in changes_made if c['action'] == 'added']
    replaced_fields = [c for c in changes_made if c['action'] == 'replaced']
    
    if added_fields:
        print(f"✅ Added {len(added_fields)} new fields:")
        for change in added_fields:
            value_preview = str(change['new_value'])[:80] + "..." if len(str(change['new_value'])) > 80 else str(change['new_value'])
            print(f"  + {change['field']}: {value_preview}")
    
    if replaced_fields:
        print(f"🔄 Replaced {len(replaced_fields)} existing fields:")
        for change in replaced_fields:
            old_preview = str(change['old_value'])[:40] + "..." if len(str(change['old_value'])) > 40 else str(change['old_value'])
            new_preview = str(change['new_value'])[:40] + "..." if len(str(change['new_value'])) > 40 else str(change['new_value'])
            print(f"  ~ {change['field']}: '{old_preview}' → '{new_preview}'")


def print_enhancement_summary(pdf_metadata, card_metadata, enhanced_metadata):
    """Print summary of enhancements made"""
    print("\n----- Enhancement Summary -----")
    
    def count_meaningful_fields(metadata):
        count = 0
        for v in metadata.values():
            if isinstance(v, dict):
                # Handle creator object
                if v.get("name") != "Not mentioned":
                    count += 1
            elif v != "Not mentioned":
                count += 1
        return count
    
    pdf_fields = count_meaningful_fields(pdf_metadata)
    card_fields = count_meaningful_fields(card_metadata)
    enhanced_fields = count_meaningful_fields(enhanced_metadata)
    
    print(f"📄 Original PDF metadata: {pdf_fields} meaningful fields")
    print(f"🏷️  Dataset card metadata: {card_fields} meaningful fields")
    print(f"🎯 Enhanced metadata: {enhanced_fields} meaningful fields")
    print(f"📈 Net improvement: +{enhanced_fields - pdf_fields} fields")
    
    # Show which fields came from which source
    print("\n----- Field Sources -----")
    card_contributed = []
    pdf_only = []
    
    for field, value in enhanced_metadata.items():
        if field in card_metadata and card_metadata[field] != "Not mentioned":
            if isinstance(card_metadata[field], dict):
                if card_metadata[field].get("name") != "Not mentioned":
                    card_contributed.append(field)
            else:
                card_contributed.append(field)
        else:
            if isinstance(value, dict):
                if value.get("name") != "Not mentioned":
                    pdf_only.append(field)
            elif value != "Not mentioned":
                pdf_only.append(field)
    
    if card_contributed:
        print(f"🏷️  From dataset card ({len(card_contributed)}): {', '.join(card_contributed)}")
    
    if pdf_only:
        print(f"📄 From PDF only ({len(pdf_only)}): {', '.join(pdf_only)}")


def main():
    """Command-line interface for enhancing papers with dataset cards"""
    parser = argparse.ArgumentParser(description="Enhance existing processed paper with dataset card metadata")
    
    # Use DATACARD_DIR from config for the default path
    default_card_path = DATACARD_DIR / "Dolly.txt"
    parser.add_argument("--dataset-card", default=str(default_card_path), help="Path to dataset card file")
    parser.add_argument("--paper-id", default='dolly', help="Paper ID to enhance")
    
    args = parser.parse_args()
    
    if not Path(args.dataset_card).exists():
        # Show available dataset cards
        print(f"Dataset card file not found: {args.dataset_card}")
        if DATACARD_DIR.exists():
            print(f"\nAvailable dataset cards in {DATACARD_DIR}:")
            for f in DATACARD_DIR.iterdir():
                if f.is_file():
                    print(f"  - {f.name}")
        parser.error("Dataset card file not found")
    
    enhance_paper_with_card(args.paper_id, args.dataset_card)


if __name__ == "__main__":
    main()