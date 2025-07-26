import json
import os
import copy


def refine_hierarchy_structure(hierarchy_path):
    if not os.path.exists(hierarchy_path):
        print(f"❌ Hierarchy file not found: {hierarchy_path}")
        return

    with open(hierarchy_path, 'r', encoding='utf-8') as f:
        hierarchy = json.load(f)

    # --- RULE 1: Remove duplicate simultaneous H1 with diff font styles ---
    cleaned_hierarchy = []
    prev_item = None
    for item in hierarchy:
        if item["level"] == 1 and prev_item and prev_item["level"] == 1:
            # Check if styles are different
            if (item.get("fontName") != prev_item.get("fontName")) or (item.get("fontSize") != prev_item.get("fontSize")):
                # Skip current H1 (keep only the first)
                continue
        cleaned_hierarchy.append(item)
        prev_item = item

    # --- RULE 2: Promote headings if consistent structure ---
    def get_flat_sequence(item):
        """Flatten nested hierarchy to get levels like [1,2,3,4] etc."""
        result = []

        def recurse(i):
            result.append(i["level"])
            for child in i.get("children", []):
                recurse(child)

        recurse(item)
        return result

    def all_same_pattern(blocks):
        """Check if all blocks have same level structure and indexes are continuous"""
        if not blocks:
            return False
        reference = get_flat_sequence(blocks[0])
        for b in blocks[1:]:
            if get_flat_sequence(b) != reference:
                return False
        return True

    def promote_levels(item, promotion_offset):
        """Recursively promote levels up"""
        item["level"] = max(1, item["level"] - promotion_offset)
        for child in item.get("children", []):
            promote_levels(child, promotion_offset)

    # Find H1 blocks that could be promoted
    blocks_to_check = []
    i = 0
    while i < len(cleaned_hierarchy) - 1:
        block = cleaned_hierarchy[i]
        next_block = cleaned_hierarchy[i + 1]
        if next_block["index"] == block["index"] + 1:
            blocks_to_check.append(copy.deepcopy(block))
        i += 1

    # If the pattern is consistent → promote
    if all_same_pattern(blocks_to_check):
        print("🔁 Consistent heading pattern detected — promoting all")
        for item in cleaned_hierarchy:
            promote_levels(item, promotion_offset=1)

    # Save modified structure back
    with open(hierarchy_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_hierarchy, f, indent=2)
    print(f"✅ Hierarchy refined and saved: {hierarchy_path}")
