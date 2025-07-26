import os
import json
from collections import Counter


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


########## KEY HEADER INTERVAL LOGIC ##########


def get_title_index(data):
    for entry in data:
        if entry.get("is_title", False):
            return entry["index"]
    return -1


def extract_headers_local(entries, header_level_name):
    """Find headers in region based on local font stats (just like before)."""
    if not entries:
        return []
    all_sizes = [
        style.get("size", 0)
        for entry in entries for style in entry.get("styles_used", [])
    ]
    if not all_sizes:
        return []
    body_size = Counter(all_sizes).most_common(1)[0][0]
    header_candidates = [
        entry for entry in entries
        if any(style.get("size", 0) > body_size for style in entry.get("styles_used", []))
    ]
    if not header_candidates:
        return []
    font_counts = Counter()
    for entry in header_candidates:
        for style in entry.get("styles_used", []):
            font_counts[style.get("font", "")] += 1
    if not font_counts:
        return []
    rarest_count = min(font_counts.values())
    rarest_fonts = [font for font, cnt in font_counts.items() if cnt == rarest_count]
    seen = set()
    headers = []
    for entry in sorted(header_candidates, key=lambda x: x.get("index", 0)):
        for style in entry.get("styles_used", []):
            if style.get("font", "") in rarest_fonts:
                idx = entry.get("index", 0)
                if idx not in seen:
                    headers.append({
                        "index": idx,
                        "text": entry.get("text", ""),
                        "style": style,
                        "reason": f"{header_level_name}: rarest font '{style.get('font', '')}' > local body size"
                    })
                    seen.add(idx)
    return headers


def discover_headers_intervals(data, region_start, region_end, level=1, max_level=10):
    """
    Main logic: For the region, finds all headers at this level,
    then recurses into each subregion with next level headers.
    Returns a list of header dicts (not tree of subregions, but path-like).
    """
    if level > max_level:
        return []


    header_level_name = f"H{level}"


    # Limit candidates to given region
    region_entries = [
        entry for entry in data
        if entry.get("index", -1) > region_start and (entry.get("index", float('inf')) < region_end)
    ]


    headers_this_level = extract_headers_local(region_entries, header_level_name=header_level_name)
    if not headers_this_level:
        return []


    header_indices = [h['index'] for h in headers_this_level]
    interval_starts = [region_start] + header_indices
    interval_ends = header_indices + [region_end]


    # The first item is not part of the output (start to first header),
    # so skip i=0 regions, only use regions [header_indices[i], interval_ends[i]]
    results = []
    for i, header in enumerate(headers_this_level):
        h_start = header_indices[i]
        h_end = interval_ends[i+1] if i+1 < len(interval_ends) else region_end
        # Recursively extract headers at next level in this subregion
        children = discover_headers_intervals(
            data, h_start, h_end, level=level+1, max_level=max_level
        )
        results.append({
            "level": header_level_name,
            "index": header["index"],
            "text": header["text"],
            "style": header["style"],
            "reason": header["reason"],
            "children": children
        })
    return results


def discover_headers_intervals_with_reference(data, h1_reference_indices, region_start, region_end, level=1, max_level=10):
    """
    Modified logic: Uses full_data but references refined H1 indices for interval boundaries.
    For H1 level: uses the provided h1_reference_indices as the header positions
    For H2+ levels: uses the original logic within each H1 interval
    """
    if level > max_level:
        return []

    header_level_name = f"H{level}"
    
    if level == 1 and h1_reference_indices:
        # For H1: Use the refined H1 indices as reference, but get full data from original dataset
        results = []
        
        # Filter H1 indices to only those within our region
        relevant_h1_indices = [
            idx for idx in h1_reference_indices 
            if idx > region_start and (idx < region_end if region_end != float('inf') else True)
        ]
        
        if not relevant_h1_indices:
            return []
        
        # Create intervals based on H1 positions
        interval_ends = relevant_h1_indices[1:] + [region_end]
        
        for i, h1_index in enumerate(relevant_h1_indices):
            h1_end = interval_ends[i] if i < len(interval_ends) else region_end
            
            # Find the actual H1 entry from full_data
            h1_entry = None
            for entry in data:
                if entry.get("index") == h1_index:
                    h1_entry = entry
                    break
            
            if h1_entry:
                # Recursively extract H2+ headers in this H1 interval
                children = discover_headers_intervals_with_reference(
                    data, h1_reference_indices, h1_index, h1_end, level=2, max_level=max_level
                )
                
                results.append({
                    "level": header_level_name,
                    "index": h1_entry["index"],
                    "text": h1_entry.get("text", ""),
                    "style": h1_entry.get("styles_used", [{}])[0] if h1_entry.get("styles_used") else {},
                    "reason": f"{header_level_name}: from refined H1 reference",
                    "children": children
                })
        
        return results
    
    else:
        # For H2+ levels: Use original logic within the given region
        region_entries = [
            entry for entry in data
            if entry.get("index", -1) > region_start and (entry.get("index", float('inf')) < region_end)
        ]

        headers_this_level = extract_headers_local(region_entries, header_level_name=header_level_name)
        if not headers_this_level:
            return []

        header_indices = [h['index'] for h in headers_this_level]
        interval_starts = [region_start] + header_indices
        interval_ends = header_indices + [region_end]

        results = []
        for i, header in enumerate(headers_this_level):
            h_start = header_indices[i]
            h_end = interval_ends[i+1] if i+1 < len(interval_ends) else region_end
            # Recursively extract headers at next level in this subregion
            children = discover_headers_intervals_with_reference(
                data, h1_reference_indices, h_start, h_end, level=level+1, max_level=max_level
            )
            results.append({
                "level": header_level_name,
                "index": header["index"],
                "text": header["text"],
                "style": header["style"],
                "reason": header["reason"],
                "children": children
            })
        return results


########## REST OF PIPELINE ##########


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
    pdf_name = os.path.splitext(pdf_filename)[0]
    input_path = os.path.join(input_dir, pdf_filename)
    output_path = os.path.join(output_dir, f"{pdf_name}.json")


    print(f"\n🔍 Processing: {pdf_filename}")


    # Extraction
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


    # Clean/Merge
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


    # Y-Axis Merging
    if execute_yaxis_merge:
        print(f"   📏 Merging spans on same Y-axis with same font size for {pdf_filename}")
        process_yaxis_merge(output_path)
    else:
        print(f"   ⏭️ Skipped Y-axis font-size merging for {pdf_filename}")


    # Line Merge
    if execute_line_merge:
        print(f"   📝 Merging lines based on attribute rules for {pdf_filename}")
        process_line_merging(output_path)
    else:
        print(f"   ⏭️ Skipped line attribute merging for {pdf_filename}")


    # Line Consolidate
    if execute_line_consolidation:
        print(f"   🔗 Consolidating similar lines for {pdf_filename}")
        process_line_consolidation(output_path)
    else:
        print(f"   ⏭️ Skipped line consolidation for {pdf_filename}")


    # Garbage Filtering
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


    # Indexing
    print(f"   🔢 Adding indexing to cleaned data for {pdf_filename}")
    add_indexing(output_path)


    # Title Extraction
    if execute_title_extraction:
        print(f"   👑 Extracting title for {pdf_filename}")
        process_title_extraction(output_path, output_dir)
    else:
        print(f"   ⏭️ Skipped title extraction for {pdf_filename}")


    # Header region extraction after Title only
    if execute_h1_extraction:
        print(f"   🏷️ Extracting all headers after the title for {pdf_filename}")
        process_header_extraction(output_path, output_dir)
        base_pdf = os.path.splitext(pdf_filename)[0]
        h1_json_path = os.path.join(output_dir, f"h1_{base_pdf}.json")
        refine_h1_headers_regionally(output_path, h1_json_path)

        # Load the full original data (complete dataset)
        with open(output_path, "r", encoding="utf-8") as f:
            full_data = json.load(f)
        
        # Load the refined H1 headers as reference for interval boundaries
        h1_refined_path = os.path.join(output_dir, f"h1_{base_pdf}_refined.json")
        
        if os.path.exists(h1_refined_path):
            print(f"   📖 Loading refined H1 headers from {h1_refined_path} as interval reference")
            with open(h1_refined_path, "r", encoding="utf-8") as f:
                refined_h1_headers = json.load(f)
            print(f"   ✅ Using {len(refined_h1_headers)} refined H1 headers as interval boundaries")
            
            # Extract H1 indices from refined headers to use as interval boundaries
            h1_indices = [entry.get("index", -1) for entry in refined_h1_headers if entry.get("index", -1) != -1]
            h1_indices.sort()  # Ensure they're in order
            
            print(f"   📍 H1 interval boundaries at indices: {h1_indices}")
        else:
            print(f"   ⚠️ Refined H1 file not found, will calculate intervals without refined reference")
            h1_indices = []

        title_index = get_title_index(full_data)
        
        # Top-level: only after title, using full_data but guided by refined H1 intervals
        header_tree = discover_headers_intervals_with_reference(
            full_data,  # Use complete original data
            h1_indices,  # Use refined H1 positions as interval boundaries
            region_start=title_index,
            region_end=float('inf'),
            level=1,
            max_level=10
        )
        tree_path = os.path.join(output_dir, f"header_intervals_{base_pdf}.json")
        with open(tree_path, "w", encoding="utf-8") as f_tree:
            json.dump(header_tree, f_tree, indent=2, ensure_ascii=False)
        print(f"   🌳 ALL HEADER INTERVALS (full data + refined H1 boundaries) saved to {tree_path}")
    else:
        print(f"   ⏭️ Skipped header extraction for {pdf_filename}")


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
    execute_h1_extraction = prompt_continue("Extract all headers (H1/H2/H3/...) after title (interval-style)")


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
