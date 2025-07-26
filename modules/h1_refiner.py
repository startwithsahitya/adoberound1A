import os
import json


def get_size_from_style(style):
    return style.get('size', 0) if style else 0


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def font_signature(style):
    """Return a tuple of style attributes required for header merging.
    Adjust keys here to control merge requirements.
    """
    if not style:
        return ()
    return (
        style.get("font"),
        style.get("font_flags", {}).get("bold"),
        style.get("font_flags", {}).get("italic"),
        # style.get("color"),  # Uncomment to require color to match as well
    )


def refine_h1_headers_regionally(main_json_path, h1_json_path, output_path=None, save=True):
    main_data = load_json(main_json_path)
    h1_headers = load_json(h1_json_path)

    # Initial validity check
    if not h1_headers or not isinstance(h1_headers, list):
        print(f"⚠️ Skipping refinement: {os.path.basename(h1_json_path)} is empty or invalid.")
        return []

    # Filter out skipped headers
    filtered_input = [h for h in h1_headers if not h.get("h1_skip", False)]
    if len(filtered_input) == 0:
        print(f"⚠️ Skipping refinement: all headers in {os.path.basename(h1_json_path)} are marked as skipped.")
        return []

    h1_sorted = sorted(filtered_input, key=lambda x: x['index'])
    new_headers = h1_sorted.copy()

    seen_configs = set()
    iteration_count = 0
    max_iterations = 50  # High safety bound

    while True:
        replaced = False
        output_headers = []
        header_indices = set(h['index'] for h in new_headers)

        for idx, header in enumerate(new_headers):
            header_idx = header['index']
            header_size = get_size_from_style(header['style'])

            if idx + 1 < len(new_headers):
                next_header = new_headers[idx + 1]
                next_idx = next_header['index']
                next_size = get_size_from_style(next_header['style'])
                region_start = header_idx
                region_end = next_idx
                min_size = min(header_size, next_size)
            else:
                region_start = header_idx
                region_end = float('inf')
                min_size = header_size

            found_bigger = None
            for entry in main_data:
                idx_in = entry.get('index')
                if idx_in is not None and region_start <= idx_in < region_end:
                    for style in entry.get('styles_used', []):
                        entry_size = style.get('size', 0)
                        if entry_size > min_size and idx_in not in header_indices:
                            found_bigger = {
                                "index": idx_in,
                                "text": entry.get("text", ""),
                                "style": style,
                                "reason": f"Promoted: bigger font {entry_size}>{min_size} in region ({region_start}-{region_end})"
                            }
                            break
                if found_bigger:
                    break

            if found_bigger:
                print(
                    f"🚩 [Region {region_start}-{region_end}]: Replacing header at index {header_idx} "
                    f"with bigger font header at index {found_bigger['index']} (font size {get_size_from_style(found_bigger['style'])})"
                )
                output_headers.append(found_bigger)
                replaced = True
            else:
                output_headers.append(header)

        seen = set()
        deduped = []
        for h in sorted(output_headers, key=lambda x: x['index']):
            if h['index'] not in seen:
                deduped.append(h)
                seen.add(h['index'])

        config = tuple((h['index'], get_size_from_style(h['style'])) for h in deduped)
        if config in seen_configs:
            print("❗ Header configuration repeated once—stopping refinement loop!")
            break
        seen_configs.add(config)

        if not replaced:
            break
        iteration_count += 1
        if iteration_count > max_iterations:
            print("❗ Max header-refinement iterations reached—breaking loop!")
            break
        new_headers = sorted(deduped, key=lambda x: x['index'])

    # Remove decreasing-size headers
    filtered_headers = []
    last_size = None
    for h in sorted(new_headers, key=lambda x: x['index']):
        curr_size = get_size_from_style(h.get('style'))
        if last_size is not None and curr_size < last_size:
            print(f"⚠️ Removed header at index {h['index']} (size {curr_size}) because it is smaller than the previous header (size {last_size})")
            continue
        filtered_headers.append(h)
        last_size = curr_size
    new_headers = filtered_headers

    # Merge consecutive-index headers with matching font signature
    merged_headers = []
    buffer = []
    prev_idx = None
    prev_sig = None
    for h in new_headers:
        curr_sig = font_signature(h.get("style"))
        if (
            prev_idx is not None
            and h['index'] == prev_idx + 1
            and curr_sig == prev_sig
        ):
            buffer.append(h)
        else:
            if buffer:
                merged_text = " ".join(e['text'] for e in buffer)
                merged_header = {
                    "index": buffer[0]['index'],
                    "text": merged_text,
                    "style": buffer[0]['style'],
                    "reason": buffer[0].get('reason', 'Merged consecutive headers')
                }
                merged_headers.append(merged_header)
                buffer = []
            buffer = [h]
        prev_idx = h['index']
        prev_sig = curr_sig
    if buffer:
        merged_text = " ".join(e['text'] for e in buffer)
        merged_header = {
            "index": buffer[0]['index'],
            "text": merged_text,
            "style": buffer[0]['style'],
            "reason": buffer[0].get('reason', 'Merged consecutive headers')
        }
        merged_headers.append(merged_header)

    if not merged_headers:
        print(f"⚠️ No headers remained after refinement of {os.path.basename(h1_json_path)}.")
        return []

    if save:
        output_path = output_path or h1_json_path  # 👈 Overwrite original file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged_headers, f, indent=2)
        print(f"✅ Refined H1 headers saved to {output_path}")

    return merged_headers


# CLI usage
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Regionally refine H1 headers using font size scanning between header candidates."
    )
    parser.add_argument('main_json', help="Main <filename>.json file path")
    parser.add_argument('h1_json', help="h1_<filename>.json file path")
    parser.add_argument('--out', help="Output path (default: overwrite original file)")
    args = parser.parse_args()

    refine_h1_headers_regionally(args.main_json, args.h1_json, output_path=args.out)
