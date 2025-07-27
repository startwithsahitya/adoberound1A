from collections import defaultdict
import copy
import json

def same_style_attributes(style1, style2):
    keys = ["font", "size", "color", "font_flags"]
    for key in keys:
        val1 = style1.get(key) if key != "font_flags" else style1.get(key, {})
        val2 = style2.get(key) if key != "font_flags" else style2.get(key, {})
        if key == "font_flags":
            flags = ["bold", "italic", "serif"]
            for flag in flags:
                if val1.get(flag) != val2.get(flag):
                    return False
        else:
            if val1 != val2:
                return False
    return True

def deduplicate_styles(styles_list):
    if not styles_list:
        return {
            "unique_styles": [],
            "style_counts": [],
            "total_styles": 0
        }

    unique_styles = []
    style_counts = []

    for style in styles_list:
        found_index = -1
        for i, existing_style in enumerate(unique_styles):
            if same_style_attributes(style, existing_style):
                found_index = i
                break

        if found_index >= 0:
            style_counts[found_index] += 1
        else:
            unique_styles.append(style.copy())
            style_counts.append(1)

    return {
        "unique_styles": unique_styles,
        "style_counts": style_counts,
        "total_styles": len(styles_list)
    }

def lines_are_adjacent(line1, line2, max_gap=15.0):
    if not line1 or not line2:
        return False

    y1_max = max([entry["position"]["y"] + entry["position"]["height"] for entry in line1])
    y2_min = min([entry["position"]["y"] for entry in line2])

    gap = y2_min - y1_max
    return 0 <= gap <= max_gap

def has_single_attribute(line):
    if not line:
        return True

    first_style = line[0]["styles_used"][0]
    for span in line:
        for style in span["styles_used"]:
            if not same_style_attributes(style, first_style):
                return False
    return True

def has_multiple_attributes(line):
    return not has_single_attribute(line)

def get_line_primary_style(line):
    if not line:
        return None
    return line[0]["styles_used"][0]

def should_merge_lines(line1, line2):
    if not lines_are_adjacent(line1, line2):
        return False

    line1_single = has_single_attribute(line1)
    line2_single = has_single_attribute(line2)

    if line1_single and line2_single:
        style1 = get_line_primary_style(line1)
        style2 = get_line_primary_style(line2)
        return same_style_attributes(style1, style2)
    elif not line1_single and not line2_single:
        return True
    else:
        return False

def consolidate_merged_lines(merged_lines_group):
    if not merged_lines_group:
        return None

    all_spans = []
    for line in merged_lines_group:
        all_spans.extend(line)

    if not all_spans:
        return None

    all_spans.sort(key=lambda s: (s["page_number"], s["position"]["y"], s["position"]["x"]))

    consolidated_text = ""
    current_y = None

    for span in all_spans:
        span_y = round(span["position"]["y"])
        if current_y is not None and span_y != current_y:
            consolidated_text += " "
        consolidated_text += span["text"]
        current_y = span_y

    all_styles = []
    for span in all_spans:
        all_styles.extend(span["styles_used"])

    style_info = deduplicate_styles(all_styles)

    min_x = min(span["position"]["x"] for span in all_spans)
    max_x = max(span["position"]["x"] + span["position"]["width"] for span in all_spans)
    min_y = min(span["position"]["y"] for span in all_spans)
    max_y = max(span["position"]["y"] + span["position"]["height"] for span in all_spans)

    base_span = all_spans[0].copy()

    if len(style_info["unique_styles"]) == 1:
        styles_used = style_info["unique_styles"]
        style_optimization = {
            "optimized": True,
            "single_style": True,
            "style_occurrences": style_info["style_counts"][0],
            "original_styles_count": style_info["total_styles"]
        }
    else:
        styles_used = []
        for i, style in enumerate(style_info["unique_styles"]):
            optimized_style = style.copy()
            optimized_style["occurrences"] = style_info["style_counts"][i]
            styles_used.append(optimized_style)

        style_optimization = {
            "optimized": True,
            "single_style": False,
            "unique_styles_count": len(style_info["unique_styles"]),
            "original_styles_count": style_info["total_styles"]
        }

    base_span.update({
        "text": consolidated_text.strip(),
        "styles_used": styles_used,
        "style_optimization": style_optimization,
        "position": {
            "x": min_x,
            "y": min_y,
            "width": max_x - min_x,
            "height": max_y - min_y
        },
        "bbox": [min_x, min_y, max_x, max_y],
        "lines": len(merged_lines_group),
        "consolidation_info": {
            "original_lines_count": len(merged_lines_group),
            "original_spans_count": len(all_spans),
            "consolidated": True,
            "styles_optimized": True
        }
    })

    return base_span

def group_spans_into_lines(data, y_tolerance=3.0):
    pages = defaultdict(list)
    for span in data:
        pages[span["page_number"]].append(span)

    all_lines = []

    for page_num, page_spans in pages.items():
        page_spans.sort(key=lambda s: s["position"]["y"])

        lines = []
        current_line = []
        current_y = None

        for span in page_spans:
            span_y = span["position"]["y"]

            if current_y is None or abs(span_y - current_y) <= y_tolerance:
                current_line.append(span)
                if current_y is None:
                    current_y = span_y
            else:
                if current_line:
                    current_line.sort(key=lambda s: s["position"]["x"])
                    lines.append(current_line)
                current_line = [span]
                current_y = span_y

        if current_line:
            current_line.sort(key=lambda s: s["position"]["x"])
            lines.append(current_line)

        all_lines.extend(lines)

    return all_lines

def merge_lines_with_consolidation(lines):
    if not lines:
        return []

    consolidated_entries = []
    i = 0
    n = len(lines)

    while i < n:
        merge_group = [lines[i]]
        j = i + 1

        while j < n and should_merge_lines(merge_group[-1], lines[j]):
            merge_group.append(lines[j])
            j += 1

        if len(merge_group) == 1:
            for span in merge_group[0]:
                span["lines"] = 1
                if len(span["styles_used"]) > 1:
                    style_info = deduplicate_styles(span["styles_used"])
                    span["styles_used"] = style_info["unique_styles"]
                    if style_info["total_styles"] > len(style_info["unique_styles"]):
                        span["style_optimization"] = {
                            "optimized": True,
                            "original_styles_count": style_info["total_styles"],
                            "unique_styles_count": len(style_info["unique_styles"])
                        }
            consolidated_entries.extend(merge_group[0])
        else:
            consolidated_entry = consolidate_merged_lines(merge_group)
            if consolidated_entry:
                consolidated_entries.append(consolidated_entry)

        i = j

    return consolidated_entries

def process_line_merging(output_path):
    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        return

    lines = group_spans_into_lines(data)
    consolidated_data = merge_lines_with_consolidation(lines)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(consolidated_data, f, indent=2)

    return consolidated_data
