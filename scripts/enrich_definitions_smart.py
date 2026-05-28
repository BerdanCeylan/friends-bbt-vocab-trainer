#!/usr/bin/env python3
"""
Smart enrichment for lemmas.json

Features:
- English definitions from free Dictionary API (dictionaryapi.dev)
- Turkish field stub (user can fill via the UI, or we can extend later)
- Resumable (skips already enriched words)
- Creates backup before starting
- Priority modes: --tiers 1,2  or  --only-marked marks.json
- Reasonable rate limiting + error handling

Usage examples:
    # Enrich only Tier 1 + Tier 2 (recommended first step)
    python3 scripts/enrich_definitions_smart.py --tiers 1,2

    # Enrich only the words you have marked as "bilmiyorum"
    # (export your wordMarks_v2 from browser console or localStorage)
    python3 scripts/enrich_definitions_smart.py --only-marked /path/to/marks.json

    # Enrich everything (will take many hours, not recommended)
    python3 scripts/enrich_definitions_smart.py --all
"""

import json
import os
import time
import argparse
import requests
import shutil
from datetime import datetime
from typing import List, Dict, Set

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEMMAS_PATH = os.path.join(PROJECT_ROOT, "data/web/lemmas.json")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "data/web/backups")

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
HEADERS = {"User-Agent": "TV-English-Learning-App/2.0 (smart-enrich)"}

def load_marks(marks_path: str) -> Set[str]:
    """Load lemmas that are marked as is_known=0 from a wordMarks_v2 JSON."""
    try:
        with open(marks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        unknown = {lemma for lemma, mark in data.items() if isinstance(mark, dict) and mark.get("is_known") == 0}
        print(f"Loaded {len(unknown)} unknown words from marks file.")
        return unknown
    except Exception as e:
        print(f"ERROR loading marks file: {e}")
        return set()

def fetch_definition(word: str) -> List[Dict]:
    """Fetch English definitions."""
    try:
        resp = requests.get(API_URL.format(word), headers=HEADERS, timeout=10)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()

        definitions = []
        for entry in data:
            for meaning in entry.get("meanings", []):
                pos = meaning.get("partOfSpeech", "")
                for d in meaning.get("definitions", []):
                    item = {
                        "partOfSpeech": pos,
                        "definition": d.get("definition", "").strip()
                    }
                    if d.get("example"):
                        item["example"] = d["example"].strip()
                    definitions.append(item)
                    if len(definitions) >= 3:
                        break
                if len(definitions) >= 3:
                    break
        return definitions
    except Exception as e:
        print(f"    [WARN] API error for '{word}': {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Smart definition enrichment for TV English")
    parser.add_argument("--tiers", help="Comma separated tiers to enrich, e.g. 1,2")
    parser.add_argument("--only-marked", help="Path to wordMarks_v2.json - only enrich these unknown words")
    parser.add_argument("--all", action="store_true", help="Enrich every single word (very slow)")
    parser.add_argument("--max", type=int, default=0, help="Maximum number of words to process this run")
    args = parser.parse_args()

    print("Loading lemmas.json...")
    with open(LEMMAS_PATH, "r", encoding="utf-8") as f:
        lemmas = json.load(f)

    # Determine target set
    target_lemmas: Set[str] = set()

    if args.only_marked:
        target_lemmas = load_marks(args.only_marked)
    elif args.tiers:
        wanted_tiers = {int(t.strip()) for t in args.tiers.split(",")}
        target_lemmas = {item["lemma"] for item in lemmas if item.get("tier") in wanted_tiers}
        print(f"Targeting Tier(s) {wanted_tiers} → {len(target_lemmas)} words")
    elif args.all:
        target_lemmas = {item["lemma"] for item in lemmas}
        print("Targeting ALL words (this will take a very long time)")
    else:
        print("No target specified. Use --tiers 1,2  or --only-marked marks.json")
        return

    # Backup
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"lemmas_before_enrich_{timestamp}.json")
    shutil.copy2(LEMMAS_PATH, backup_path)
    print(f"Backup created: {backup_path}\n")

    enriched = 0
    skipped = 0
    failed = []
    processed = 0

    for i, item in enumerate(lemmas):
        lemma = item["lemma"]
        if lemma not in target_lemmas:
            continue

        # Skip if already has decent definitions
        existing = item.get("definitions")
        if existing and len(existing) > 0:
            skipped += 1
            continue

        print(f"[{processed+1}] {lemma} ... ", end="", flush=True)
        defs = fetch_definition(lemma)

        if defs:
            item["definitions"] = defs
            item["turkish"] = item.get("turkish", "")  # ensure field exists
            enriched += 1
            print(f"OK ({len(defs)} defs)")
        else:
            item["definitions"] = []
            item["turkish"] = item.get("turkish", "")
            failed.append(lemma)
            print("no result")

        processed += 1

        # Rate limit - be respectful
        time.sleep(0.35)

        if args.max > 0 and processed >= args.max:
            print(f"\nReached --max limit of {args.max}")
            break

        if processed % 100 == 0:
            # Save progress periodically
            with open(LEMMAS_PATH, "w", encoding="utf-8") as f:
                json.dump(lemmas, f, indent=2, ensure_ascii=False)
            print(f"   (progress saved, {processed} processed so far)")

    # Final save
    with open(LEMMAS_PATH, "w", encoding="utf-8") as f:
        json.dump(lemmas, f, indent=2, ensure_ascii=False)

    print("\n" + "="*50)
    print(f"Done! Processed: {processed}")
    print(f"Newly enriched: {enriched}")
    print(f"Already had definitions: {skipped}")
    print(f"No definition found: {len(failed)}")
    print(f"Backup: {backup_path}")
    print(f"Updated: {LEMMAS_PATH}")

if __name__ == "__main__":
    main()