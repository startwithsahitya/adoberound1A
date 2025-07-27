from collections import defaultdict
import json

def _merge_text_overlap(a: str, b: str) -> tuple[str, int]:
    """
    Merge two strings, removing overlap between end of `a` and start of `b`.
    """
    max_ov = min(len(a), len(b))
    for j in range(max_ov, 0, -1):
        if a.endswith(b[:j]):
            return a + b[j:], j
    return a + b, 0

def merge_on_yaxis_preserve_styles(data):
    """
    Merge spans line-by-line on the same Y position, combining only those
    with the same font (font size can differ).
    """
    lines = defaultdict(list)
    for span in data:
        key = (span['page_number'], round(span['position']['y']))
        lines[key].append(span)

    merged = []
    for (page, y), spans in lines.items():
        spans = sorted(spans, key=lambda e: e['position']['x'])

        run = [spans[0]]
        for span in spans[1:]:
            prev_font = run[-1]['styles_used'][0]['font']
            curr_font = span['styles_used'][0]['font']
            if curr_font == prev_font:
                run.append(span)
            else:
                # Merge current run
                merged_text = run[0]['text']
                for r in run[1:]:
                    merged_text, _ = _merge_text_overlap(merged_text, r['text'])

                style = run[0]['styles_used'][0]
                base = run[0].copy()
                base.update({
                    'text': merged_text,
                    'styles_used': [style],
                    'lines': len(run),
                })
                xs = [r['position']['x'] for r in run]
                ws = [r['position']['width'] for r in run]
                xmin = min(xs)
                xmax = max(x + w for x, w in zip(xs, ws))
                base['position']['x'] = xmin
                base['position']['width'] = xmax - xmin
                base['bbox'][0] = xmin
                base['bbox'][2] = xmax
                merged.append(base)

                run = [span]

        # Final flush
        merged_text = run[0]['text']
        for r in run[1:]:
            merged_text, _ = _merge_text_overlap(merged_text, r['text'])

        style = run[0]['styles_used'][0]
        base = run[0].copy()
        base.update({
            'text': merged_text,
            'styles_used': [style],
            'lines': len(run),
        })
        xs = [r['position']['x'] for r in run]
        ws = [r['position']['width'] for r in run]
        xmin = min(xs)
        xmax = max(x + w for x, w in zip(xs, ws))
        base['position']['x'] = xmin
        base['position']['width'] = xmax - xmin
        base['bbox'][0] = xmin
        base['bbox'][2] = xmax
        merged.append(base)

    return merged

def process_yaxis_merge(input_path, output_path=None):
    """
    Load spans from JSON, merge them by font on the same Y-axis line,
    and save output.
    """
    if output_path is None:
        output_path = input_path

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    before = len(data)
    merged = merge_on_yaxis_preserve_styles(data)
    after = len(merged)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2)

    
    return merged

def debug_merge_preview(entries, max_display=5):
    """
    Preview spans before and after merging.
    """
    if not entries:
        return "No spans provided."

    raw = sorted(entries, key=lambda e: e['position']['x'])
    out = ["Pre‑merge spans:"]
    for i, e in enumerate(raw[:max_display], 1):
        s = e['styles_used'][0]
        flags = []
        if s['font_flags'].get('bold'):   flags.append('Bold')
        if s['font_flags'].get('italic'): flags.append('Italic')
        out.append(f" {i}. '{e['text']}' @X={e['position']['x']} | {s['font']} {s['size']}pt {' '.join(flags)}")

    if len(raw) > max_display:
        out.append(f" ...and {len(raw) - max_display} more spans")

    merged = merge_on_yaxis_preserve_styles(entries)
    out.append("\nPost‑merge runs:")
    for i, e in enumerate(merged[:max_display], 1):
        s = e['styles_used'][0]
        out.append(f" {i}. '{e['text']}' | {s['font']} {s['size']}pt | spans={e['lines']}")

    if len(merged) > max_display:
        out.append(f" ...and {len(merged) - max_display} more runs")

    return "\n".join(out)
