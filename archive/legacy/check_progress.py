#!/usr/bin/env python3
"""Check extraction progress with visual progress bar."""

import json
import os
import sys
from datetime import datetime

def check_progress():
    # Load parsed datasets
    with open('data/parsed_datasets.json') as f:
        data = json.load(f)
    
    # Count datasets with papers
    total_with_papers = 0
    completed = 0
    completed_datasets = []
    pending_datasets = []
    
    for d in data['datasets']:
        if d['status'] in ['has_paper', 'uncertain']:
            safe_name = d['safe_name']
            pdf_path = f"data/raw/{safe_name}.pdf"
            
            # Skip if PDF doesn't exist
            if not os.path.exists(pdf_path):
                continue
            
            total_with_papers += 1
            result_file = f"data/processed/{safe_name}/full_pdf_metadata_result.json"
            
            if os.path.exists(result_file):
                try:
                    with open(result_file) as f:
                        result = json.load(f)
                        if len(result) == 30:
                            completed += 1
                            completed_datasets.append(d['dataset_id'])
                            continue
                except:
                    pass
            
            pending_datasets.append(d['dataset_id'])
    
    # Calculate progress
    progress = completed / total_with_papers if total_with_papers > 0 else 0
    bar_width = 50
    filled = int(bar_width * progress)
    bar = '█' * filled + '░' * (bar_width - filled)
    
    # Clear screen and print
    print('\033[2J\033[H', end='')  # Clear screen
    print('=' * 60)
    print('  CroissantMiner - RAI Metadata Extraction Progress')
    print('=' * 60)
    print()
    print(f'  [{bar}] {progress*100:.1f}%')
    print()
    print(f'  Completed: {completed} / {total_with_papers}')
    print(f'  Remaining: {total_with_papers - completed}')
    print()
    
    # Estimate time remaining
    if completed > 0:
        avg_time = 60  # seconds per dataset
        remaining_time = (total_with_papers - completed) * avg_time
        mins, secs = divmod(remaining_time, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            print(f'  Est. remaining: {int(hours)}h {int(mins)}m')
        else:
            print(f'  Est. remaining: {int(mins)}m {int(secs)}s')
    print()
    
    # Show last 5 completed
    if completed_datasets:
        print('  Last completed:')
        for ds in completed_datasets[-5:]:
            print(f'    ✓ {ds}')
        print()
    
    # Show next 3 pending
    if pending_datasets:
        print('  Next in queue:')
        for ds in pending_datasets[:3]:
            print(f'    ○ {ds}')
        print()
    
    print(f'  Last updated: {datetime.now().strftime("%H:%M:%S")}')
    print('=' * 60)
    print('  Press Ctrl+C to exit | Run again to refresh')
    print('=' * 60)

if __name__ == '__main__':
    os.chdir('str(Path(__file__).resolve().parent.parent)')
    check_progress()
