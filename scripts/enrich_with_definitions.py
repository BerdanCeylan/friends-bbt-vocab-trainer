#!/usr/bin/env python3
"""
Enrich lemmas.json with English definitions using the free Dictionary API.

https://dictionaryapi.dev/

This will add a "definitions" array to each lemma:
[
  {
    "partOfSpeech": "verb",
    "definition": "To move from one place to another.",
    "example": "I need to go to the store."
  },
  ...
]

Usage:
    python3 scripts/enrich_with_definitions.py
"""

import json
import os
import time
import requests
from typing import List, Dict, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(PROJECT_ROOT, "data/web/lemmas.json")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data/web/lemmas.json")  # overwrite for simplicity

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
HEADERS = {"User-Agent": "TV-English-Learning-App/1.0"}

def fetch_definition(word: str) -> List[Dict]:
    """Fetch definitions for a word from the free API."""
    url = API_URL.format(word)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code == 404:
            return []  # word not found (common for "gonna", "wanna", etc.)
        resp.raise_for_status()
        data = resp.json()

        definitions = []
        for entry in data:
            for meaning in entry.get("meanings", []):
                pos = meaning.get("partOfSpeech", "")
                for d in meaning.get("definitions", []):
                    defn = {
                        "partOfSpeech": pos,
                        "definition": d.get("definition", "").strip(),
                    }
                    if d.get("example"):
                        defn["example"] = d["example"].strip()
                    definitions.append(defn)
        return definitions[:4]  # max 4 definitions per word (to keep JSON light)
    except Exception as e:
        print(f"  [WARN] Could not fetch definition for '{word}': {e}")
        return []


def main():
    print("Loading current lemmas.json...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lemmas = json.load(f)

    print(f"Found {len(lemmas)} lemmas. Starting enrichment...\n")

    enriched_count = 0
    failed = []

    for i, item in enumerate(lemmas):
        lemma = item["lemma"]

        # Skip if already enriched
        if item.get("definitions"):
            continue

        defs = fetch_definition(lemma)

        if defs:
            item["definitions"] = defs
            enriched_count += 1
            print(f"[{i+1}/{len(lemmas)}] {lemma} → {len(defs)} definitions")
        else:
            failed.append(lemma)
            item["definitions"] = []  # empty so we know we tried

        # Be nice to the free API
        time.sleep(0.25)

        # Progress every 50 words
        if (i + 1) % 50 == 0:
            print(f"  ... progress: {i+1}/{len(lemmas)}")

    # Save back
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(lemmas, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done!")
    print(f"   Successfully enriched: {enriched_count}")
    print(f"   No definition found (or API failed): {len(failed)}")

    if failed:
        print("\nWords without definitions (you may want to handle manually later):")
        print(", ".join(failed[:30]) + ("..." if len(failed) > 30 else ""))

    print(f"\nUpdated file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
