import fitz  # PyMuPDF
import math


def extract_pdf_content(pdf_path):
    doc = fitz.open(pdf_path)
    all_spans = []

    for page_num, page in enumerate(doc, start=1):
        spans = page.get_text("dict")["blocks"]
        for block in spans:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    bbox = span["bbox"]
                    rounded_font_size = math.ceil(span["size"])
                    rounded_bbox = [math.ceil(coord) for coord in bbox]

                    x, y = rounded_bbox[0], rounded_bbox[1]
                    width = rounded_bbox[2] - rounded_bbox[0]
                    height = rounded_bbox[3] - rounded_bbox[1]

                    span_data = {
                        "text": span["text"].strip(),
                        "styles_used": [{
                            "font": span["font"],
                            "size": rounded_font_size,
                            "color": span["color"],
                            "font_flags": {
                                "bold": bool(span["flags"] & 2),
                                "italic": bool(span["flags"] & 1),
                                "serif": bool(span["flags"] & 4),
                            }
                        }],
                        "position": {
                            "x": x,
                            "y": y,
                            "width": width,
                            "height": height
                        },
                        "bbox": rounded_bbox,
                        "page_number": page_num
                    }
                    all_spans.append(span_data)

    doc.close()  # Added to close the document properly
    return all_spans
