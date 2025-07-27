import json
import os
import re
from collections import Counter, OrderedDict


def process_header_hierarchy(json_path, output_dir):
    filename = os.path.splitext(os.path.basename(json_path))[0]
    h1_path = os.path.join(output_dir, f"h1_{filename}.json")
    hierarchy_path = os.path.join(output_dir, f"hierarchy_{filename}.json")

    with open(json_path, "r", encoding="utf-8") as f:
        spans = json.load(f)
    with open(h1_path, "r", encoding="utf-8") as f:
        h1_headers = json.load(f)

    if not h1_headers:
        
        return

    h1_entries = []
    for h in h1_headers:
        h1_entries.append({
            "text": h["text"],
            "index": h["index"],
            "level": 1,
            "children": [],
            "fontSize": h["style"]["size"],
            "fontName": h["style"]["font"],
            "weight": h["style"].get("font_flags", {}).get("bold", False),
            "italic": h["style"].get("font_flags", {}).get("italic", False)
        })

    for i, h1 in enumerate(h1_entries):
        start = h1["index"]
        end = h1_entries[i + 1]["index"] if i + 1 < len(h1_entries) else float("inf")
        region = [s for s in spans if start < s.get("index", -1) < end]
        children = _build_hierarchy(region, parent_level=1)
        h1["children"] = _deduplicate_tree(children)

    with open(hierarchy_path, "w", encoding="utf-8") as f:
        json.dump(h1_entries, f, indent=2, ensure_ascii=False)
    


def _build_hierarchy(spans, parent_level):
    if not spans:
        return []

    plain_sizes = [st.get("size", 0)
                   for s in spans for st in s.get("styles_used", [])
                   if not st.get("font_flags", {}).get("bold", False)
                   and not st.get("font_flags", {}).get("italic", False)]
    if not plain_sizes:
        return []
    body_size = Counter(plain_sizes).most_common(1)[0][0]

    def is_candidate(s):
        for st in s.get("styles_used", []):
            sz = st.get("size", 0)
            font_name = st.get("font", "").lower()

            if sz > body_size:
                return True

            is_styled = (
                st.get("font_flags", {}).get("bold", False) or
                st.get("font_flags", {}).get("italic", False) or
                any(term in font_name for term in [
                    "bold", "black", "heavy", "oblique", "italic",
                    "narrow", "semi", "demi", "compressed", "condensed"
                ])
            )

            if sz == body_size and is_styled:
                return True
        return False

    def has_mixed_styles(span):
        styles = span.get("styles_used", [])
        if len(styles) <= 1:
            return False
        normalized = set()
        for st in styles:
            key = (
                st.get("size", 0),
                st.get("font", ""),
                st.get("font_flags", {}).get("bold", False),
                st.get("font_flags", {}).get("italic", False)
            )
            normalized.add(key)
        return len(normalized) > 1

    cands = [s for s in spans if is_candidate(s) and not has_mixed_styles(s)]
    if not cands:
        return []

    # New logic: assign level by font style precedence
    style_buckets = OrderedDict()
    for s in cands:
        for st in s.get("styles_used", []):
            style_key = (
                st.get("size", 0),
                st.get("font", ""),
                st.get("font_flags", {}).get("bold", False),
                st.get("font_flags", {}).get("italic", False)
            )
            if style_key not in style_buckets:
                style_buckets[style_key] = None  # preserve order

    style_to_level = {
        style: parent_level + 1 + i for i, style in enumerate(style_buckets)
    }

    this_level = []
    seen_idx = set()
    seen_keys = set()
    for s in cands:
        for st in s.get("styles_used", []):
            idx = s.get("index")
            key = (
                s.get("text", "").strip(),
                st.get("size", 0),
                st.get("font", ""),
                st.get("font_flags", {}).get("bold", False),
                st.get("font_flags", {}).get("italic", False)
            )
            if idx in seen_idx or key in seen_keys:
                continue
            seen_idx.add(idx)
            seen_keys.add(key)

            style_key = (
                st.get("size", 0),
                st.get("font", ""),
                st.get("font_flags", {}).get("bold", False),
                st.get("font_flags", {}).get("italic", False)
            )
            lvl = style_to_level.get(style_key, parent_level + 1)
            text = s.get("text", "").strip()

            if re.search(r"[^\d]\.$", text):
                continue
            if text.count(",") >= 2 or re.findall(r"(?<!\d)\.(?!\d)", text):
                continue

            this_level.append({
                "text": text,
                "index": idx,
                "level": lvl,
                "fontSize": st.get("size", 0),
                "fontName": st.get("font", ""),
                "weight": st.get("font_flags", {}).get("bold", False),
                "italic": st.get("font_flags", {}).get("italic", False),
                "children": []
            })
            break

    this_level.sort(key=lambda h: h["index"])
    result = []
    for i, hdr in enumerate(this_level):
        start = hdr["index"]
        end = float("inf")
        for j in range(i + 1, len(this_level)):
            if this_level[j]["level"] <= hdr["level"]:
                end = this_level[j]["index"]
                break
        region = [sp for sp in spans if start < sp.get("index", -1) < end]
        hdr["children"] = _build_hierarchy(region, parent_level=hdr["level"])
        result.append(hdr)

    return _truncate_repeats(result)


def _truncate_repeats(headers):
    cleaned = []
    i = 0
    while i < len(headers):
        group = [headers[i]]
        lvl = headers[i]["level"]
        style = (
            headers[i]["fontSize"],
            headers[i]["fontName"],
            headers[i]["weight"],
            headers[i]["italic"]
        )
        j = i + 1
        while j < len(headers):
            h = headers[j]
            if h["level"] == lvl and (
                h["fontSize"],
                h["fontName"],
                h["weight"],
                h["italic"]
            ) == style and _is_consecutive(headers[j - 1]["index"], h["index"]):
                group.append(h)
                j += 1
                continue
            break
        if lvl > 2 and len(group) >= 3:
            
            i = j
            continue
        headers[i]["children"] = _truncate_repeats(headers[i]["children"])
        cleaned.append(headers[i])
        i += 1
    return cleaned


def _is_consecutive(idx1, idx2):
    try:
        p1 = list(map(int, re.findall(r'\d+', str(idx1))))
        p2 = list(map(int, re.findall(r'\d+', str(idx2))))
        if len(p1) != len(p2):
            return False
        return all(a == b for a, b in zip(p1[:-1], p2[:-1])) and p2[-1] == p1[-1] + 1
    except:
        return False


def _deduplicate_tree(nodes):
    seen = set()

    def dedup(node):
        key = (
            node.get("text", "").strip(),
            node.get("fontSize"),
            node.get("fontName"),
            node.get("weight"),
            node.get("italic")
        )
        if key in seen:
            return None
        seen.add(key)
        node["children"] = [c for c in (dedup(child) for child in node.get("children", [])) if c]
        return node

    return [n for n in (dedup(node) for node in nodes) if n]
