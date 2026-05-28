#!/usr/bin/env python3
"""
generate_clean_missing_words.py

Takes unlinked words (from previous full scan report) and filters them into
a clean list of "real" missing vocabulary words.

Filtering applied:
- Remove Function Words (data/web/function_words.json)
- Remove Character Names (data/web/character_names.json)
- Remove obvious junk (very short words, numbers, single letters, punctuation-only, etc.)
- Keep only words that look like real English content words

Output:
- data/web/missing_real_words.json   → sorted by frequency (highest first)
- Also prints top N for quick review

Usage:
    python3 scripts/generate_clean_missing_words.py --top 100
"""

import json
import re
import argparse
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent
REPORT_PATH = PROJECT_ROOT / "data/web/unlinked_words_report.json"
FUNCTION_WORDS_PATH = PROJECT_ROOT / "data/web/function_words.json"
CHARACTER_NAMES_PATH = PROJECT_ROOT / "data/web/character_names.json"
OUTPUT_PATH = PROJECT_ROOT / "data/web/missing_real_words.json"


def is_junk(word: str) -> bool:
    """Basic heuristic to filter obvious garbage / non-words."""
    if not word or len(word) < 3:
        return True
    if word.isdigit():
        return True
    # Mostly punctuation or numbers
    if re.fullmatch(r"[\W\d]+", word):
        return True
    # Very short + weird combinations (common OCR artifacts)
    if len(word) <= 3 and not word.isalpha():
        return True
    # Common single letter + s/t/d/m artifacts from subtitles
    if word in {"s", "t", "m", "d", "ll", "re", "ve", "nt"}:
        return True
    return False


def load_json_list(path: Path) -> set:
    if not path.exists():
        print(f"Warning: {path} not found, using empty list.")
        return set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {item.lower() for item in data}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=150, help="How many top missing words to print")
    args = parser.parse_args()

    print("Loading data...")

    # Load previous full unlinked report
    if not REPORT_PATH.exists():
        print(f"ERROR: {REPORT_PATH} not found. Run analyze_unlinked_words.py first with --friends --bbt")
        return

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    # The report stores top_unlinked as list of {word, frequency}
    unlinked_items = report.get("top_unlinked", [])
    if not unlinked_items:
        print("No unlinked data found in report.")
        return

    # Load filter lists
    function_words = load_json_list(FUNCTION_WORDS_PATH)
    character_names = load_json_list(CHARACTER_NAMES_PATH)
    junk_words = load_json_list(PROJECT_ROOT / "data/web/junk_words.json")

    print(f"Loaded {len(function_words)} function words and {len(character_names)} character names for filtering.")

    # Filter
    clean_missing = []

    for item in unlinked_items:
        word = item["word"].lower()
        freq = item["frequency"]

        if word in function_words:
            continue
        if word in character_names:
            continue
        if word in junk_words:
            continue
        if is_junk(word):
            continue

        clean_missing.append({
            "word": word,
            "frequency": freq
        })

    # Sort by frequency (highest first)
    clean_missing.sort(key=lambda x: x["frequency"], reverse=True)

    # Save clean list
    output_data = {
        "total_unlinked_in_report": len(unlinked_items),
        "after_filtering": len(clean_missing),
        "filtered_as_function_words": len([x for x in unlinked_items if x["word"].lower() in function_words]),
        "filtered_as_character_names": len([x for x in unlinked_items if x["word"].lower() in character_names]),
        "missing_real_words": clean_missing
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\nSaved clean list to: {OUTPUT_PATH}")
    print(f"  Original unlinked in report : {len(unlinked_items)}")
    print(f"  Removed as function words   : {output_data['filtered_as_function_words']}")
    print(f"  Removed as character names  : {output_data['filtered_as_character_names']}")
    print(f"  Final real missing words    : {len(clean_missing)}")

    print(f"\n=== Top {args.top} Real Missing Words (by frequency) ===\n")
    for i, item in enumerate(clean_missing[:args.top], 1):
        print(f"{i:3}. {item['frequency']:6}  →  {item['word']}")

    if len(clean_missing) > args.top:
        print(f"\n... and {len(clean_missing) - args.top} more.")


if __name__ == "__main__":
    main()
