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
from modules.hierarchy_cleaner import refine_hierarchy_structure
from modules.hierarchy_merger import merge_adjacent_headers, remove_index_attributes


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
    print(f"   📘 Final structured output saved to {final_output_path}")


def process_single_pdf(pdf_filename, input_dir, output_dir):
    pdf_name = os.path.splitext(pdf_filename)[0]
    input_path = os.path.join(input_dir, pdf_filename)
    output_path = os.path.join(output_dir, f"{pdf_name}.json")

    print(f"\n🔍 Processing: {pdf_filename}")

    print(f"   📤 Extracting content from {pdf_filename}")
    extracted = extract_pdf_content(input_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2)
    print(f"   ✅ Extraction complete: {len(extracted)} spans found")

    print(f"   🔧 Cleaning and merging duplicates for {pdf_filename}")
    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    original_count = len(data)
    cleaned_data = clean_and_merge(data)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2)
    final_count = len(cleaned_data)
    print(f"   ✅ Cleaning complete: Merged {original_count - final_count} duplicates/fragments")

    print(f"   📏 Merging spans on same Y-axis with same font size for {pdf_filename}")
    process_yaxis_merge(output_path)

    print(f"   📝 Merging lines based on attribute rules for {pdf_filename}")
    process_line_merging(output_path)

    print(f"   🔗 Consolidating similar lines for {pdf_filename}")
    process_line_consolidation(output_path)

    print(f"   🧹 Filtering garbage text from {pdf_filename}")
    with open(output_path, "r", encoding="utf-8") as f:
        extracted_data = json.load(f)
    filtered_data = [span for span in extracted_data if not is_garbage(span["text"])]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered_data, f, indent=2)
    print(f"   ✅ Filtering complete: Removed {len(extracted_data) - len(filtered_data)} garbage spans")

    print(f"   🔢 Adding indexing to cleaned data for {pdf_filename}")
    add_indexing(output_path)

    print(f"   👑 Extracting title for {pdf_filename}")
    process_title_extraction(output_path, output_dir)

    print(f"   🏷️  Extracting H1 headers for {pdf_filename}")
    process_header_extraction(output_path, output_dir)

    h1_json_path = os.path.join(output_dir, f"h1_{pdf_name}.json")
    refine_h1_headers_regionally(output_path, h1_json_path)

    process_header_hierarchy(output_path, output_dir)

    hierarchy_path = os.path.join(output_dir, f"hierarchy_{pdf_name}.json")
    refine_hierarchy_structure(hierarchy_path)

    generate_final_output(output_dir, "Data/Output", pdf_filename)

    print(f"   💾 Final output saved.")
    return True


def run_pipeline():
    input_dir = "Data/Input"
    output_dir = "Data/Temp"
    final_dir = "Data/Output"

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(final_dir, exist_ok=True)

    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print("❌ No PDF files found in Data/Input directory")
        return

    print(f"📁 Found {len(pdf_files)} PDF file(s): {', '.join(pdf_files)}")

    successful_count = 0
    failed_count = 0

    for pdf_filename in pdf_files:
        try:
            success = process_single_pdf(pdf_filename, input_dir, output_dir)
            if success:
                successful_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"   ❌ Error processing {pdf_filename}: {str(e)}")
            failed_count += 1

    print(f"\n🔧 Post-processing final output for H1-H2 merging")
    merge_adjacent_headers(final_dir)
    remove_index_attributes(final_dir)

    print(f"\n🧹 Cleaning up Temp folder")
    for f in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, f))
    print("   ✅ Temp folder cleaned: Data/Temp")

    print(f"\n📊 Processing Summary:")
    print(f"   ✅ Successfully processed: {successful_count} files")
    print(f"   ❌ Failed to process: {failed_count} files")
    print(f"   📁 Temp directory: {output_dir}")
    print(f"   📁 Final output directory: {final_dir}")


if __name__ == "__main__":
    run_pipeline()
