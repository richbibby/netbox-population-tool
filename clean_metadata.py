#!/usr/bin/env python3
"""Remove old NetBox metadata from JSON files."""

import json
from pathlib import Path

# Fields to remove
REMOVE_FIELDS = ['url', 'display_url', 'created', 'last_updated', 'display']

def clean_file(filepath):
    """Remove metadata fields from a JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        cleaned = []
        for item in data:
            if isinstance(item, dict):
                cleaned_item = {k: v for k, v in item.items() if k not in REMOVE_FIELDS}
                cleaned.append(cleaned_item)
            else:
                cleaned.append(item)
    elif isinstance(data, dict):
        cleaned = {k: v for k, v in data.items() if k not in REMOVE_FIELDS}
    else:
        cleaned = data
    
    with open(filepath, 'w') as f:
        json.dump(cleaned, f, indent=2)
    
    return len(data) if isinstance(data, list) else 1

# Process all JSON files in extracted_data
data_dir = Path('extracted_data')
total_files = 0
total_objects = 0

for json_file in sorted(data_dir.glob('*.json')):
    if json_file.name in ['id_mappings.json', 'm2m_mappings.json', 'metadata.json']:
        continue  # Skip helper files
    
    count = clean_file(json_file)
    total_files += 1
    total_objects += count
    print(f"✓ Cleaned {json_file.name}: {count} objects")

print(f"\n✓ Cleaned {total_files} files ({total_objects} total objects)")
