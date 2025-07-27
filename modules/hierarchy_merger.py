import os
import json


def merge_adjacent_headers(output_dir):
    files = [f for f in os.listdir(output_dir) if f.endswith(".json")]

    for file in files:
        file_path = os.path.join(output_dir, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        outline = data.get("outline", [])
        if not outline:
            continue

        blocks = []
        current_block = []

        for item in outline:
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
            if h2.get("index", -1) != h1.get("index", -2) + 1:
                should_promote_all = False
                break

        if not should_promote_all:
            continue

        for item in outline:
            level_num = int(item["level"][1])
            item["level"] = f"H{max(1, level_num - 1)}"

        data["outline"] = outline

        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2)


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


def remove_consecutive_same_level_headers(output_dir):
    files = [f for f in os.listdir(output_dir) if f.endswith(".json")]

    for file in files:
        file_path = os.path.join(output_dir, file)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        outline = data.get("outline", [])
        if not outline:
            continue

        cleaned_outline = []
        i = 0
        while i < len(outline):
            current = outline[i]
            cleaned_outline.append(current)
            j = i + 1

            while j < len(outline) and outline[j]["level"] == current["level"]:
                if outline[j]["index"] == outline[j - 1]["index"] + 1:
                    j += 1
                else:
                    cleaned_outline.append(outline[j])
                    j += 1
            i = j

        data["outline"] = cleaned_outline

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def remove_illegal_header_jumps(output_dir):
    files = [f for f in os.listdir(output_dir) if f.endswith(".json")]

    for file in files:
        file_path = os.path.join(output_dir, file)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        outline = data.get("outline", [])
        if not outline:
            continue

        cleaned_outline = []
        previous_level = 0

        for item in outline:
            current_level = int(item["level"][1])

            if previous_level == 0:
                cleaned_outline.append(item)
                previous_level = current_level
                continue

            if current_level == previous_level + 1:
                cleaned_outline.append(item)
                previous_level = current_level
            elif current_level <= previous_level:
                cleaned_outline.append(item)
                previous_level = current_level
            else:
                continue  # Skip illegal jump

        data["outline"] = cleaned_outline

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
