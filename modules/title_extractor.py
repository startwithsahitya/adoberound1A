import json
from collections import defaultdict

def get_font_family_signature(style):
    font_flags = style.get("font_flags", {})
    return (
        style.get("font", ""),
        style.get("color", 0),
        font_flags.get("bold", False),
        font_flags.get("italic", False),
        font_flags.get("serif", False)
    )

def get_font_signature_with_size(style):
    return get_font_family_signature(style) + (style.get("size", 0),)

def merge_simultaneous_entries(entries):
    if not entries:
        return None
    entries = sorted(entries, key=lambda e: e.get("position", {}).get("x", 0))
    combined_text = " ".join(entry.get("text", "") for entry in entries)

    all_styles = []
    seen_signatures = set()
    for entry in entries:
        for style in entry.get("styles_used", []):
            sig = json.dumps(style, sort_keys=True)
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                all_styles.append(style)

    all_positions = [entry.get("position", {}) for entry in entries]
    min_x = min(pos.get("x", 0) for pos in all_positions)
    max_x = max(pos.get("x", 0) + pos.get("width", 0) for pos in all_positions)
    min_y = min(pos.get("y", 0) for pos in all_positions)
    max_y = max(pos.get("y", 0) + pos.get("height", 0) for pos in all_positions)

    base_entry = entries[-1].copy()
    base_entry.update({
        "text": combined_text,
        "styles_used": all_styles,
        "position": {
            "x": min_x,
            "y": min_y,
            "width": max_x - min_x,
            "height": max_y - min_y
        },
        "bbox": [min_x, min_y, max_x, max_y],
        "merged_simultaneous": True,
        "original_entries_count": len(entries)
    })
    return base_entry

def valid_title_position(candidate_indices, data_length):
    last_idx = max(candidate_indices)
    before = last_idx
    after = data_length - last_idx - 1
    return after > before

def extract_title_precise(data):
    page1 = [e for e in data if e.get("page_number", 1) == 1]
    page2_plus = [e for e in data if e.get("page_number", 1) >= 2]
    if not page1:
        return {"title": None, "reason": "No page 1 elements", "debug": {}}

    family2entries = defaultdict(list)
    size_family2count = defaultdict(int)
    family_count = defaultdict(int)

    for entry in data:
        for style in entry.get("styles_used", []):
            fam = get_font_family_signature(style)
            fam_size = get_font_signature_with_size(style)
            family2entries[fam].append(entry)
            size_family2count[fam_size] += 1
            family_count[fam] += 1

    family_max_size = {}
    for fam, entries in family2entries.items():
        sizes = [
            s.get("size", 0)
            for e in entries for s in e.get("styles_used", [])
            if get_font_family_signature(s) == fam
        ]
        family_max_size[fam] = max(sizes) if sizes else 0

    max_page2_size = max(
        (s.get("size", 0) for e in page2_plus for s in e.get("styles_used", [])),
        default=0,
    )

    group_a_candidates = []
    for idx, entry in enumerate(page1):
        styles = entry.get("styles_used", [])
        if not styles:
            continue
        s = styles[0]
        fam = get_font_family_signature(s)
        fam_size = get_font_signature_with_size(s)
        size = s.get("size", 0)
        if family_count[fam] < 2:
            continue
        if size != family_max_size[fam]:
            continue
        if size_family2count[fam_size] != 1:
            continue
        if size <= max_page2_size:
            continue
        group_a_candidates.append({"entry": entry, "idx": idx, "size": size})

    merged_a = []
    if group_a_candidates:
        group_a_candidates.sort(key=lambda x: x["idx"])
        group = [group_a_candidates[0]]
        for cur in group_a_candidates[1:]:
            if cur["idx"] == group[-1]["idx"] + 1:
                group.append(cur)
            else:
                merged_a.append(group)
                group = [cur]
        if group:
            merged_a.append(group)

    group_a_final = []
    data_len = len(data)
    for group in merged_a:
        indices = [g["idx"] for g in group]
        if len(group) == 1:
            if valid_title_position(indices, data_len):
                group_a_final.append(group[0])
        else:
            merged = merge_simultaneous_entries([g["entry"] for g in group])
            merged_candidate = {
                "entry": merged,
                "size": max(g["size"] for g in group),
                "idx": max(indices),
                "indices": indices
            }
            if valid_title_position(indices, data_len):
                group_a_final.append(merged_candidate)

    group_b_candidates = []
    for idx, entry in enumerate(page1):
        styles = entry.get("styles_used", [])
        if not styles:
            continue
        s = styles[0]
        fam = get_font_family_signature(s)
        fam_size = get_font_signature_with_size(s)
        size = s.get("size", 0)
        if family_count[fam] != 1:
            continue
        if size_family2count[fam_size] != 1:
            continue
        if valid_title_position([idx], len(data)):
            group_b_candidates.append({"entry": entry, "idx": idx, "size": size})

    best_a = max(group_a_final, key=lambda x: x["size"], default=None)
    best_b = max(group_b_candidates, key=lambda x: x["size"], default=None)

    if best_a and (not best_b or best_a["size"] > best_b["size"]):
        title_entry = best_a["entry"]
        reason = "Font family recurring, largest+unique size and unrepeatable (A) with required position."
    elif best_b and (not best_a or best_b["size"] > best_a["size"]):
        title_entry = best_b["entry"]
        reason = "Unique font family, unique size in doc (B), with required position."
    elif best_a and best_b and best_a["size"] == best_b["size"]:
        title_entry = best_a["entry"]
        reason = "Both group A and B match: precedence to recurring family (A), with required position."
    else:
        return {
            "title": None,
            "reason": "No title candidate matches algorithm and position rule.",
            "debug": {"group_a": group_a_final, "group_b": group_b_candidates}
        }

    return {
        "title": title_entry.get("text", "").strip(),
        "reason": reason,
        "title_entry": title_entry
    }

def process_title_extraction(json_path, output_dir=None):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        result = extract_title_precise(data)
        title_entry = result.get("title_entry")

        if title_entry:
            matched_text = title_entry.get("text", "").strip()
            matched_bbox = title_entry.get("bbox", [])
            matched_page = title_entry.get("page_number", 1)

            matched = False
            for entry in data:
                if (
                    entry.get("text", "").strip() == matched_text and
                    entry.get("bbox") == matched_bbox and
                    entry.get("page_number", 1) == matched_page
                ):
                    entry["is_title"] = True
                    matched = True
                    break

            if not matched:
                title_entry["is_title"] = True
                data.insert(0, title_entry)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    except Exception:
        raise
