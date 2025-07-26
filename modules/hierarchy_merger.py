import os
import json
import copy


def merge_adjacent_headers(output_dir):
    files = [f for f in os.listdir(output_dir) if f.endswith(".json")]

    for file in files:
        file_path = os.path.join(output_dir, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        outline = data.get("outline", [])
        if not outline:
            continue

        # Group by H1 blocks
        blocks = []
        current_block = []

        for i, item in enumerate(outline):
            level = int(item['level'][1])
            if level == 1:
                if current_block:
                    blocks.append(current_block)
                current_block = [item]
            else:
                current_block.append(item)
        if current_block:
            blocks.append(current_block)

        should_promote_all = True

        for block in blocks:
            if len(block) < 2:
                should_promote_all = False
                break
            h1 = block[0]
            h2 = block[1]
            if not (h1["level"] == "H1" and h2["level"] == "H2"):
                should_promote_all = False
                break
            if h2["index"] != h1["index"] + 1:
                should_promote_all = False
                break

        if not should_promote_all:
            continue

        # Promote levels: H2 → H1, H3 → H2, etc.
        for item in outline:
            level_num = int(item["level"][1])
            item["level"] = f"H{max(1, level_num - 1)}"

        data["outline"] = outline

        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f"   🔄 Merged H1-H2 headers in: {file}")


def remove_index_attributes(output_dir):
    files = [f for f in os.listdir(output_dir) if f.endswith(".json")]

    for file in files:
        file_path = os.path.join(output_dir, file)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "outline" not in data:
            continue

        for item in data["outline"]:
            if "index" in item:
                del item["index"]

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"   🧹 Removed 'index' from: {file}")


# ✅ New Function to filter out same-level headers with only +1 index difference
def remove_consecutive_same_level_headers(output_dir):
    files = [f for f in os.listdir(output_dir) if f.endswith(".json")]

    for file in files:
        file_path = os.path.join(output_dir, file)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        outline = data.get("outline", [])
        if not outline:
            continue

        result = []
        i = 0
        while i < len(outline):
            current = outline[i]
            result.append(current)

            j = i + 1
            while j < len(outline) and outline[j]["level"] == current["level"]:
                if outline[j]["index"] == outline[j - 1]["index"] + 1:
                    # If pair is exactly consecutive (e.g., 6-7), keep only the earlier one
                    # and skip the current j
                    j += 1
                else:
                    result.append(outline[j])
                    j += 1
            i = j

        data["outline"] = result

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"   ➖ Removed redundant consecutive same-level headers in: {file}")
