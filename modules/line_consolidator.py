# modules/line_consolidator.py

import json


def are_styles_equal(style1, style2):
    return (
        style1["font"] == style2["font"] and
        style1["size"] == style2["size"] and
        style1["font_flags"] == style2["font_flags"]
    )


def can_merge(span1, span2):
    if span1["page_number"] != span2["page_number"]:
        return False
    return are_styles_equal(span1["styles_used"][0], span2["styles_used"][0])


def merge_spans(span1, span2):
    merged_text = span1["text"].rstrip() + " " + span2["text"].lstrip()

    new_bbox = [
        min(span1["bbox"][0], span2["bbox"][0]),
        min(span1["bbox"][1], span2["bbox"][1]),
        max(span1["bbox"][2], span2["bbox"][2]),
        max(span1["bbox"][3], span2["bbox"][3]),
    ]

    new_position = {
        "x": new_bbox[0],
        "y": new_bbox[1],
        "width": new_bbox[2] - new_bbox[0],
        "height": new_bbox[3] - new_bbox[1],
    }

    return {
        "text": merged_text,
        "styles_used": span1["styles_used"],
        "position": new_position,
        "bbox": new_bbox,
        "page_number": span1["page_number"]
    }


def consolidate_lines(spans):
    if not spans:
        return []

    consolidated = []
    current = spans[0]

    for next_span in spans[1:]:
        if can_merge(current, next_span):
            current = merge_spans(current, next_span)
        else:
            consolidated.append(current)
            current = next_span

    consolidated.append(current)
    return consolidated


def process_line_consolidation(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        spans = json.load(f)

    merged_spans = consolidate_lines(spans)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(merged_spans, f, indent=2)

    