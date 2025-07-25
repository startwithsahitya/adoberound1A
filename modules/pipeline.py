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
from modules.indexer import add_indexing        # ✅ NEW: indexing module
from modules.h1_refiner import refine_h1_headers_regionally   # ✅ NEW: region-based H1 refiner

def prompt_continue(step_name):
    response = input(f"👉 Step: {step_name} — Execute this step? (y/n): ").strip().lower()
    return response == 'y'

def clean_and_merge(data):
    from modules.cleaner import merge_duplicates_same_page, remove_cross_page_duplicates
    step1 = merge_duplicates_same_page(data)
    step2 = remove_cross_page_duplicates(step1)
    return step2

def process_single_pdf(pdf_filename, input_dir, output_dir,
                      execute_extraction, execute_cleaning,
                      execute_yaxis_merge, execute_line_merge,
                      execute_line_consolidation,
                      execute_filtering,
                      execute_title_extraction, execute_h1_extraction):
    """Process a single PDF file through all steps"""
    pdf_name = os.path.splitext(pdf_filename)[0]
    input_path = os.path.join(input_dir, pdf_filename)
    output_path = os.path.join(output_dir, f"{pdf_name}.json")

    print(f"\n🔍 Processing: {pdf_filename}")

    # STEP 1: Extract PDF Content
    if execute_extraction:
        print(f"   📤 Extracting content from {pdf_filename}")
        extracted = extract_pdf_content(input_path)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(extracted, f, indent=2)
        print(f"   ✅ Extraction complete: {len(extracted)} spans found")
    else:
        if not os.path.exists(output_path):
            print(f"   ❌ No extracted data found for {pdf_filename}. Need to run extraction first.")
            return False
        print(f"   ⏭️ Skipped extraction for {pdf_filename}")

    # STEP 2: Clean and Merge Duplicates
    if execute_cleaning:
        print(f"   🔧 Cleaning and merging duplicates for {pdf_filename}")
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        original_count = len(data)
        cleaned_data = clean_and_merge(data)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, indent=2)
        final_count = len(cleaned_data)
        merged_count = original_count - final_count
        print(f"   ✅ Cleaning complete: Merged {merged_count} duplicates/fragments, {final_count} spans final")
    else:
        print(f"   ⏭️ Skipped cleaning for {pdf_filename}")

    # STEP 3: Y-Axis Font Size Merging
    if execute_yaxis_merge:
        print(f"   📏 Merging spans on same Y-axis with same font size for {pdf_filename}")
        process_yaxis_merge(output_path)
    else:
        print(f"   ⏭️ Skipped Y-axis font-size merging for {pdf_filename}")

    # STEP 4: Line Attribute Merging
    if execute_line_merge:
        print(f"   📝 Merging lines based on attribute rules for {pdf_filename}")
        process_line_merging(output_path)
    else:
        print(f"   ⏭️ Skipped line attribute merging for {pdf_filename}")

    # STEP 5: Consolidate Similar Consecutive Lines
    if execute_line_consolidation:
        print(f"   🔗 Consolidating similar lines for {pdf_filename}")
        process_line_consolidation(output_path)
    else:
        print(f"   ⏭️ Skipped line consolidation for {pdf_filename}")

    # STEP 6: Filter Garbage
    if execute_filtering:
        print(f"   🧹 Filtering garbage text from {pdf_filename}")
        with open(output_path, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
        original_count = len(extracted_data)
        filtered_data = [span for span in extracted_data if not is_garbage(span["text"])]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(filtered_data, f, indent=2)
        filtered_count = len(filtered_data)
        removed_count = original_count - filtered_count
        print(f"   ✅ Filtering complete: Removed {removed_count} garbage spans, {filtered_count} spans remaining")
    else:
        print(f"   ⏭️ Skipped garbage filtering for {pdf_filename}")

    # STEP 6.5: Add Indexing
    print(f"   🔢 Adding indexing to cleaned data for {pdf_filename}")
    add_indexing(output_path)

    # STEP 7: Title Extraction
    if execute_title_extraction:
        print(f"   👑 Extracting title for {pdf_filename}")
        process_title_extraction(output_path, output_dir)
    else:
        print(f"   ⏭️ Skipped title extraction for {pdf_filename}")

    # STEP 8: H1 Header Extraction and REFINE (regional)
    if execute_h1_extraction:
        print(f"   🏷️  Extracting H1 headers for {pdf_filename}")
        process_header_extraction(output_path, output_dir)
        # --- Regional H1 Refinement Step ---
        base_pdf = os.path.splitext(pdf_filename)[0]
        h1_json_path = os.path.join(output_dir, f"h1_{base_pdf}.json")
        refine_h1_headers_regionally(output_path, h1_json_path)  # <--- The new regional logic
    else:
        print(f"   ⏭️ Skipped H1 header extraction for {pdf_filename}")

    print(f"   💾 Final output saved: {output_path}")
    return True

def run_pipeline():
    input_dir = "Data/Input"
    output_dir = "Data/Output"

    os.makedirs(output_dir, exist_ok=True)
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print("❌ No PDF files found in Data/Input directory")
        return

    print(f"📁 Found {len(pdf_files)} PDF file(s): {', '.join(pdf_files)}")

    # Ask user which steps to execute
    execute_extraction = prompt_continue("Extract PDF content")
    execute_cleaning = prompt_continue("Clean duplicates & merge substrings")
    execute_yaxis_merge = prompt_continue("Merge spans on same Y-axis with same font size")
    execute_line_merge = prompt_continue("Merge lines based on attribute rules")
    execute_line_consolidation = prompt_continue("Consolidate similar consecutive lines")
    execute_filtering = prompt_continue("Filter garbage text")
    execute_title_extraction = prompt_continue("Extract title from PDF")
    execute_h1_extraction = prompt_continue("Extract H1 headers")

    if not any([
        execute_extraction, execute_cleaning,
        execute_yaxis_merge, execute_line_merge,
        execute_line_consolidation, execute_filtering,
        execute_title_extraction, execute_h1_extraction
    ]):
        print("⏭️ No steps selected. Exiting.")
        return

    successful_count = 0
    failed_count = 0

    for pdf_filename in pdf_files:
        try:
            success = process_single_pdf(
                pdf_filename, input_dir, output_dir,
                execute_extraction, execute_cleaning,
                execute_yaxis_merge, execute_line_merge,
                execute_line_consolidation,
                execute_filtering,
                execute_title_extraction, execute_h1_extraction
            )
            if success:
                successful_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"   ❌ Error processing {pdf_filename}: {str(e)}")
            failed_count += 1

    print(f"\n📊 Processing Summary:")
    print(f"   ✅ Successfully processed: {successful_count} files")
    print(f"   ❌ Failed to process: {failed_count} files")
    print(f"   📁 Output directory: {output_dir}")

    if successful_count > 0:
        print(f"\n📄 Generated Files:")
        for filename in os.listdir(output_dir):
            if filename.endswith('.json'):
                print(f"   📝 {filename}")

if __name__ == "__main__":
    run_pipeline()
