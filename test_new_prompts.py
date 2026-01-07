"""
Test script for new RAI-focused prompts on 2 datasets
Tests: MSCOCO and MMLU
"""

import os
import sys
import json
import time
from datetime import datetime
import fitz  # PyMuPDF

# Add project to path
sys.path.insert(0, 'croissantminer')

from models.claude_model import ClaudeModel

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file using PyMuPDF"""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def main():
    print("=" * 80)
    print("YENİ RAI PROMPT TESTİ - 2 DATASET")
    print(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Test datasets - ALL 8
    datasets = [
        {"name": "MLS", "pdf": "data/2012.03411v2.pdf", "description": "Multilingual LibriSpeech"},
        {"name": "FLORES", "pdf": "data/2106.03193v1.pdf", "description": "FLORES-101"},
        {"name": "CIFAR", "pdf": "data/2404.00498v2.pdf", "description": "CIFAR-10/100"},
        {"name": "Visual Genome", "pdf": "data/1602.07332v1.pdf", "description": "Visual Genome"},
        {"name": "MSCOCO", "pdf": "data/1405.0312v3.pdf", "description": "MS COCO"},
        {"name": "MMLU", "pdf": "data/2009.03300v3.pdf", "description": "MMLU"},
        {"name": "MMMU", "pdf": "data/2311.16502v4.pdf", "description": "MMMU"},
        {"name": "MathVista", "pdf": "data/2310.02255v3.pdf", "description": "MathVista"},
    ]

    # Initialize Claude model
    print("\n🚀 Claude Sonnet 4.5 başlatılıyor...")
    model = ClaudeModel(model_id="claude-sonnet-4-5-20250929")

    results = {}

    for dataset in datasets:
        print(f"\n{'='*80}")
        print(f"📄 Dataset: {dataset['name']}")
        print(f"   {dataset['description']}")
        print(f"   PDF: {dataset['pdf']}")
        print("=" * 80)

        # Extract text from PDF
        pdf_path = os.path.join('croissantminer', dataset['pdf'])

        if not os.path.exists(pdf_path):
            print(f"❌ PDF bulunamadı: {pdf_path}")
            continue

        print(f"\n📖 PDF okunuyor...")
        text = extract_text_from_pdf(pdf_path)
        print(f"   Toplam karakter: {len(text):,}")

        # Extract metadata with new prompts
        print(f"\n🤖 Metadata extraction başlıyor...")
        start_time = time.time()

        try:
            # Use the new RAI schema - provide full schema for validation
            schema = {
                "sc:name": "string",
                "sc:description": "string",
                "sc:url": "string",
                "sc:license": "string",
                "sc:creator": "string",
                "sc:publisher": "string",
                "sc:datePublished": "string",
                "sc:inLanguage": "string",
                "cr:citeAs": "string",
                "cr:isLiveDataset": "string",
                "rai:dataCollection": "string",
                "rai:dataCollectionType": "string",
                "rai:dataCollectionMissingData": "string",
                "rai:dataCollectionRawData": "string",
                "rai:dataCollectionTimeframe": "string",
                "rai:dataImputationProtocol": "string",
                "rai:dataManipulationProtocol": "string",
                "rai:dataPreprocessingProtocol": "string",
                "rai:dataAnnotationProtocol": "string",
                "rai:dataAnnotationPlatform": "string",
                "rai:dataAnnotationAnalysis": "string",
                "rai:annotationsPerItem": "string",
                "rai:annotatorDemographics": "string",
                "rai:machineAnnotationTools": "string",
                "rai:dataReleaseMaintenancePlan": "string",
                "rai:personalSensitiveInformation": "string",
                "rai:dataSocialImpact": "string",
                "rai:dataBiases": "string",
                "rai:dataLimitations": "string",
                "rai:dataUseCases": "string"
            }
            metadata = model.extract_metadata_full_pdf(text, schema)

            elapsed_time = time.time() - start_time
            print(f"✅ Extraction tamamlandı: {elapsed_time:.2f}s")

            # Count non-null fields
            non_null = sum(1 for v in metadata.values() if v is not None and v != "" and v != "null")
            total_fields = len(metadata)

            print(f"\n📊 Sonuçlar:")
            print(f"   Toplam field: {total_fields}")
            print(f"   Dolu field: {non_null}")
            print(f"   Boş field: {total_fields - non_null}")
            print(f"   Doluluk oranı: {non_null/total_fields*100:.1f}%")

            # Store results
            results[dataset['name']] = {
                "metadata": metadata,
                "stats": {
                    "total_fields": total_fields,
                    "non_null_fields": non_null,
                    "null_fields": total_fields - non_null,
                    "fill_rate": f"{non_null/total_fields*100:.1f}%",
                    "extraction_time": f"{elapsed_time:.2f}s"
                }
            }

            # Print extracted metadata
            print(f"\n📝 Extracted Metadata:")
            print("-" * 60)
            for key, value in metadata.items():
                if value is not None and value != "" and value != "null":
                    # Truncate long values
                    display_value = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                    print(f"   {key}: {display_value}")
                else:
                    print(f"   {key}: (null)")

        except Exception as e:
            print(f"❌ Hata: {e}")
            results[dataset['name']] = {"error": str(e)}

        # Wait between requests
        print(f"\n⏳ Rate limit için bekleniyor...")
        time.sleep(30)

    # Save results
    output_path = 'new_prompt_test_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n\n{'='*80}")
    print("✅ TEST TAMAMLANDI")
    print(f"   Sonuçlar kaydedildi: {output_path}")
    print("=" * 80)

    return results

if __name__ == "__main__":
    results = main()
