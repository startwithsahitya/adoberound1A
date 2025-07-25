from collections import defaultdict
import json


def _style_key(style):
    s = style[0]
    return (
        s["font"],
        s["size"],
        s["color"],
        s["font_flags"]["bold"],
        s["font_flags"]["italic"],
        s["font_flags"]["serif"]
    )


def _entry_key(entry, ignore_page=False):
    pos = entry["position"]
    return (
        round(pos["x"]), round(pos["y"]),
        _style_key(entry["styles_used"]),
        entry["text"].strip(),
        None if ignore_page else entry["page_number"]
    )


def remove_cross_page_duplicates(data):
    seen = defaultdict(list)
    for entry in data:
        key = _entry_key(entry, ignore_page=True)
        seen[key].append(entry)
    return [entries[0] for entries in seen.values() if len(entries) == 1]


def merge_fragments(fragments):
    if not fragments:
        return ""

    fragments = sorted(fragments, key=lambda x: x['position']['x'])
    result = fragments[0]['text']

    for i in range(1, len(fragments)):
        current_text = fragments[i]['text']
        overlap = 0
        max_overlap = min(len(result), len(current_text))
        for j in range(max_overlap, 0, -1):
            if result.endswith(current_text[:j]):
                overlap = j
                break
        result += current_text[overlap:]
    return result


def group_entries_loose_by_line(entries):
    """
    Group entries by page and approximate Y position (line), ignoring styles.
    """
    lines = defaultdict(list)
    for entry in entries:
        key = (
            entry["page_number"],
            round(entry["position"]["y"] / 5) * 5  # group within ~5px y tolerance
        )
        lines[key].append(entry)
    return lines


def merge_duplicates_same_page(data):
    unique_map = {}
    for entry in data:
        key = _entry_key(entry)
        if key in unique_map:
            continue
        unique_map[key] = entry

    deduped = list(unique_map.values())

    # Use relaxed grouping: by (page_number, rounded y)
    lines = group_entries_loose_by_line(deduped)

    final_entries = []

    for key, group in lines.items():
        if not group:
            continue

        # Sort by X position
        group = sorted(group, key=lambda x: x["position"]["x"])

        # Merge the text fragments
        merged_text = merge_fragments(group)

        # Use the first fragment's metadata
        base = group[0].copy()
        base["text"] = merged_text

        final_entries.append(base)

    return final_entries


def clean_and_merge(output_path):
    """Legacy function for backward compatibility"""
    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    step1 = merge_duplicates_same_page(data)
    step2 = remove_cross_page_duplicates(step1)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(step2, f, indent=2)

    print(f"✅ Cleaning complete. Data updated in-place at {output_path}")
