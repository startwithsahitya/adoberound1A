import os
import json
from collections import Counter, defaultdict

def get_font_sequence(entry):
    """Extract the sequence of fonts (as a tuple) for the entry."""
    return tuple(style.get("font", "") for style in entry.get("styles_used", []))


def legacy_process_header_extraction(data, input_json_path, output_dir):
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
            if (
                len(fonts_seq) == 1 or
                (idx in merged_seq_entries and fonts_seq == title_fonts_seq and len(fonts_seq) == len(set(fonts_seq)))
            ):
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

def process_header_extraction(input_json_path, output_dir):
    with open(input_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data or not isinstance(data, list):
        print("⚠️ No data found.")
        return []

    # --- PRIMARY LOGIC: Most used size is the biggest, select rarest font in single-size/single-font entries ---
    size_counts = Counter()
    for entry in data:
        for style in entry.get("styles_used", []):
            size_counts[style.get("size", 0)] += 1

    if not size_counts:
        print("⚠️ No font sizes found.")
        return []

    most_used_size, _ = size_counts.most_common(1)[0]
    global_max_size = max(size_counts.keys())

    if most_used_size == global_max_size:
        print(f"🎯 Using 'most used size is the biggest' header logic: size={global_max_size}")

        # Filter to only entries that are single-size (all styles same size)
        size_entries = []
        for entry in data:
            sizes = {style.get("size", 0) for style in entry.get("styles_used", [])}
            if sizes == {global_max_size} and entry.get("styles_used", []):
                size_entries.append(entry)

        # Count fonts among these entries (only for single-font entries)
        font_counts = Counter()
        for entry in size_entries:
            fonts = {style.get("font", "") for style in entry.get("styles_used", [])}
            if len(fonts) == 1:
                font_counts[next(iter(fonts))] += 1

        if not font_counts:
            print("⚠️ No fonts found among single-size entries. Fallback to legacy.")
            return legacy_process_header_extraction(data, input_json_path, output_dir)

        # Pick rarest font (e.g., Bold if rarer than Regular at header size)
        rarest_font, _ = min(font_counts.items(), key=lambda x: x[1])

        print(f"🔎 Picking rarest font for header lines: '{rarest_font}'")

        headers = []
        for entry in size_entries:
            fonts = {style.get("font", "") for style in entry.get("styles_used", [])}
            if fonts == {rarest_font}:
                style_to_use = entry.get("styles_used", [])[0]
                headers.append({
                    "index": entry.get("index", 0),
                    "text": entry.get("text", ""),
                    "style": style_to_use,
                    "reason": f"H1: rarest font '{rarest_font}' among entries with size {global_max_size}"
                })

        # De-duplicate by index
        seen_indices = set()
        header_json = []
        for h in sorted(headers, key=lambda x: x["index"]):
            if h["index"] not in seen_indices:
                header_json.append(h)
                seen_indices.add(h["index"])

        base_pdf = os.path.splitext(os.path.basename(input_json_path))[0]
        output_path = os.path.join(output_dir, f"h1_{base_pdf}.json")
        with open(output_path, "w", encoding="utf-8") as f_out:
            json.dump(header_json, f_out, indent=2)
        print(f"🏷️ H1 header(s) saved to: h1_{base_pdf}.json")
        return header_json

    else:
        # ---- fallback to old logic here ----
        print("🔄 Most common size is NOT used at the document's largest size: using heuristic header logic.")
        return legacy_process_header_extraction(data, input_json_path, output_dir)

# CLI usage
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Extract H1 headers based on most-used size and rarest font variant, with fallback."
    )
    parser.add_argument('input_json', help="Input <filename>.json file path")
    parser.add_argument('--outdir', default=".", help="Output directory")
    args = parser.parse_args()
    process_header_extraction(args.input_json, args.outdir)