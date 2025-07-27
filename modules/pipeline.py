import os
import json

from modules.scraper import extract_pdf_content
from modules.filter import is_garbage
from modules.cleaner import clean_and_merge
from modules.yaxis_merger import process_yaxis_merge
from modules.line_merger import process_line_merging
from modules.title_extractor import process_title_extraction
from modules.headers import process_header_extraction
from modules.line_consolidator import process_line_consolidation
from modules.indexer import add_indexing
from modules.h1_refiner import refine_h1_headers_regionally
from modules.hierarchy import process_header_hierarchy
from modules.hierarchy_merger import (
    merge_adjacent_headers,
    remove_index_attributes,
    remove_consecutive_same_level_headers,
    remove_illegal_header_jumps,
)


def clean_and_merge(data):
    from modules.cleaner import merge_duplicates_same_page, remove_cross_page_duplicates
    step1 = merge_duplicates_same_page(data)
    step2 = remove_cross_page_duplicates(step1)
    return step2


def generate_final_output(temp_dir, final_dir, filename):
    base_name = os.path.splitext(filename)[0]
    temp_path = os.path.join(temp_dir, f"{base_name}.json")
    hierarchy_path = os.path.join(temp_dir, f"hierarchy_{base_name}.json")
    final_output_path = os.path.join(final_dir, f"{base_name}.json")

    with open(temp_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    title = ""
    if data and data[0].get("is_title"):
        title = data[0]["text"]

    if os.path.exists(hierarchy_path):
        with open(hierarchy_path, 'r', encoding='utf-8') as f:
            hierarchy_data = json.load(f)
    else:
        hierarchy_data = []

    def flatten_hierarchy(items, result):
        for item in items:
            level = f"H{item['level']}"
            page = next((span.get("page_number", 1) for span in data if span.get("index") == item["index"]), 1)
            result.append({
                "level": level,
                "text": item["text"],
                "index": item["index"],
                "page": page
            })
            if item.get("children"):
                flatten_hierarchy(item["children"], result)

    outline = []
    flatten_hierarchy(hierarchy_data, outline)

    final_output = {
        "title": title,
        "outline": outline
    }

    os.makedirs(final_dir, exist_ok=True)
    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)


def process_single_pdf(pdf_filename, input_dir, output_dir):
    pdf_name = os.path.splitext(pdf_filename)[0]
    input_path = os.path.join(input_dir, pdf_filename)
    output_path = os.path.join(output_dir, f"{pdf_name}.json")

    extracted = extract_pdf_content(input_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2)

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cleaned_data = clean_and_merge(data)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2)

    process_yaxis_merge(output_path)
    process_line_merging(output_path)
    process_line_consolidation(output_path)

    with open(output_path, "r", encoding="utf-8") as f:
        extracted_data = json.load(f)
    filtered_data = [span for span in extracted_data if not is_garbage(span["text"])]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered_data, f, indent=2)

    add_indexing(output_path)
    process_title_extraction(output_path, output_dir)
    process_header_extraction(output_path, output_dir)

    h1_json_path = os.path.join(output_dir, f"h1_{pdf_name}.json")
    refine_h1_headers_regionally(output_path, h1_json_path)

    process_header_hierarchy(output_path, output_dir)
    generate_final_output(output_dir, "output", pdf_filename)

    return True


def decrement_page_numbers(output_dir):
    files = [f for f in os.listdir(output_dir) if f.endswith(".json")]

    for file in files:
        file_path = os.path.join(output_dir, file)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "outline" not in data:
            continue

        for item in data["outline"]:
            if "page" in item and isinstance(item["page"], int):
                item["page"] = max(0, item["page"] - 1)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def run_pipeline():
    input_dir = "input"
    output_dir = "Temp"
    final_dir = "output"

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(final_dir, exist_ok=True)

    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        return

    successful_count = 0
    failed_count = 0

    for pdf_filename in pdf_files:
        try:
            success = process_single_pdf(pdf_filename, input_dir, output_dir)
            if success:
                successful_count += 1
            else:
                failed_count += 1
        except Exception:
            failed_count += 1

    remove_illegal_header_jumps(final_dir)
    merge_adjacent_headers(final_dir)
    remove_consecutive_same_level_headers(final_dir)
    remove_index_attributes(final_dir)
    decrement_page_numbers(final_dir)  # ✅ New step




if __name__ == "__main__":
    run_pipeline()
