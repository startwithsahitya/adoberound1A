# modules/indexer.py

import json
import os

def add_indexing(output_path):
    """
    Adds a sequential index to each entry in a JSON array.
    Modifies the file in-place.
    """
    
    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for i, entry in enumerate(data, start=1):
        entry["index"] = i

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    
