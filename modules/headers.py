import os
import json
from collections import Counter, defaultdict

def get_font_sequence(entry):
    """Extract the sequence of fonts (as a tuple) for the entry."""
    return tuple(style.get("font", "") for style in entry.get("styles_used", []))

def process_header_extraction(input_json_path, output_dir):
    with open(input_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data or not isinstance(data, list):
        print("⚠️ No data found.")
        return []

    # 1. --- Find the Title, Get its index and font sequence ---
    title_index = None
    title_fonts_seq = ()
    title_entry = None
    for entry in data:
        if entry.get("is_title", False):
            title_index = entry.get("index", None)
            title_entry = entry
            title_fonts_seq = get_font_sequence(entry)
            break

    # All header logic ONLY after the title (by index)
    if title_index is not None:
        candidate_entries = [entry for entry in data if entry.get("index", 0) > title_index]
    else:
        candidate_entries = data

    if not candidate_entries:
        print('⚠️ No header candidates after title!')
        return []

    # 2. --- Compute most frequent body size (typical body text size) ---
    all_sizes = [
        style.get("size", 0)
        for entry in candidate_entries
        for style in entry.get("styles_used", [])
    ]
    if not all_sizes:
        print("⚠️ No font sizes in candidates.")
        return []
    body_size = Counter(all_sizes).most_common(1)[0][0]

    # 3. --- Filter: Only entries with any style > body_size ---
    filtered_candidates = [
        entry
        for entry in candidate_entries
        if any(style.get("size", 0) > body_size for style in entry.get("styles_used", []))
    ]
    if not filtered_candidates:
        print("No header-size entries found.")
        header_json = []
    else:
        # 4. --- Find rarest font(s) among header-size candidates ---
        font_counts = Counter()
        font_size_map = defaultdict(list)
        for entry in filtered_candidates:
            for style in entry.get("styles_used", []):
                font = style.get("font", "")
                size = style.get("size", 0)
                font_counts[font] += 1
                font_size_map[font].append(size)
        rarest_count = min(font_counts.values())
        rarest_fonts = [font for font, cnt in font_counts.items() if cnt == rarest_count]
        h1_font_size_pairs = [(font, max(font_size_map[font])) for font in rarest_fonts]
        group_max_size = max(max_size for font, max_size in h1_font_size_pairs)

        # ---- X-position set for main header group
        main_h1_x_positions = set()
        for entry in filtered_candidates:
            for style in entry.get("styles_used", []):
                if (style.get("font", ""), style.get("size", 0)) in h1_font_size_pairs:
                    x = entry.get("position", {}).get("x", None)
                    if x is not None:
                        main_h1_x_positions.add(x)

        # 5. --- Find entries for H1
        h1_reason = dict()  # index -> reason
        idx_to_entry = {entry["index"]: entry for entry in filtered_candidates}

        # (a) rarest font & max size
        for entry in filtered_candidates:
            for style in entry.get("styles_used", []):
                if (style.get("font", ""), style.get("size", 0)) in h1_font_size_pairs:
                    h1_reason[entry["index"]] = "rarest font and max size"
                    break

        # (b) size >= group_max_size, any font, but must match main H1 x-position
        for entry in filtered_candidates:
            if entry["index"] in h1_reason:
                continue
            entry_x = entry.get("position", {}).get("x", None)
            if entry_x not in main_h1_x_positions:
                continue
            for style in entry.get("styles_used", []):
                if style.get("size", 0) >= group_max_size:
                    h1_reason[entry["index"]] = "has size equal or greater than H1 group max size (and matches H1 x-position)"
                    break

        # (c, d) title logic (after the decided title only!)
        sizes_for_median = [
            style.get("size", 0)
            for entry in filtered_candidates
            for style in entry.get("styles_used", [])
        ]
        merged_seq_entries = set()
        if sizes_for_median and title_fonts_seq:
            median_size = sorted(sizes_for_median)[len(sizes_for_median) // 2]
            for entry in filtered_candidates:
                fonts_seq = get_font_sequence(entry)
                # Single-font: match title font and >= median size
                if len(title_fonts_seq) == 1 and title_fonts_seq[0] in fonts_seq:
                    if entry["index"] in h1_reason:
                        continue
                    for style in entry.get("styles_used", []):
                        if (style.get("font", "") == title_fonts_seq[0]
                                and style.get("size", 0) >= median_size):
                            h1_reason[entry["index"]] = "matches title font and size"
                            break
                # Multi-font: only accept if sequence matches exactly (after title)
                elif (len(title_fonts_seq) > 1
                      and fonts_seq == title_fonts_seq
                      and len(fonts_seq) == len(title_fonts_seq)):
                    merged_seq_entries.add(entry["index"])
                    h1_reason[entry["index"]] = "matches title font sequence exactly"

        # 6. --- Only single-fonts or exact merged-sequences as H1 ---
        final_h1_entries = []
        seen = set()
        for idx in list(h1_reason) + list(merged_seq_entries):
            entry = idx_to_entry.get(idx)
            if not entry or idx in seen:
                continue
            fonts_seq = get_font_sequence(entry)
            if (len(fonts_seq) == 1 or
                    (idx in merged_seq_entries and fonts_seq == title_fonts_seq and len(fonts_seq) == len(set(fonts_seq)))):
                final_h1_entries.append((entry, h1_reason.get(idx, "matches title font sequence exactly")))
                seen.add(idx)
        final_h1_entries = sorted(final_h1_entries, key=lambda e: e[0]["index"])

        # Output: add the reason!
        header_json = [{
            "index": entry.get("index", 0),
            "text": entry.get("text", ""),
            "style": max(entry.get("styles_used", []), key=lambda s: s.get("size", 0)) if entry.get("styles_used") else {},
            "reason": reason
        } for entry, reason in final_h1_entries]

    base_pdf = os.path.splitext(os.path.basename(input_json_path))[0]
    output_path = os.path.join(output_dir, f"h1_{base_pdf}.json")
    with open(output_path, "w", encoding="utf-8") as f_out:
        json.dump(header_json, f_out, indent=2)
    print(f"🏷️ H1 header(s) saved to: h1_{base_pdf}.json")
    return header_json
