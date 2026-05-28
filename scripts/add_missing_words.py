#!/usr/bin/env python3
"""
add_missing_words.py

Adds the clean "real missing words" from missing_real_words.json into the vocabulary system.

Logic:
- Common contractions (he's, she's, they're, what's, who's, there's) are added as **variants** 
  of their base lemmas (he, she, they, what, who, there).
- Other words are added as new **lemmas** with proper frequency, usefulness and tier.
- Updates both vocabulary_v2.db and data/web/lemmas.json

Usage:
    python3 scripts/add_missing_words.py --dry-run          # See what would be added
    python3 scripts/add_missing_words.py                    # Actually add them
"""

import json
import sqlite3
import math
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data/db/vocabulary_v2.db"
LEMMAS_JSON = PROJECT_ROOT / "data/web/lemmas.json"
MISSING_WORDS_PATH = PROJECT_ROOT / "data/web/missing_real_words.json"

# Common contractions that should be variants of base lemmas
CONTRACTION_MAP = {
    "he's": "he",
    "she's": "she",
    "they're": "they",
    "what's": "what",
    "who's": "who",
    "there's": "there",
    "it's": "it",
    "that's": "that",
    "here's": "here",
    "let's": "let",
    "i'm": "i",
    "you're": "you",
    "we're": "we",
    "isn't": "is",
    "aren't": "are",
    "wasn't": "was",
    "weren't": "were",
    "doesn't": "does",
    "don't": "do",
    "didn't": "did",
    "can't": "can",
    "won't": "will",
    "wouldn't": "would",
    "couldn't": "could",
    "shouldn't": "should",
    "hasn't": "has",
    "haven't": "have",
    "hadn't": "had",
}

def compute_usefulness(frequency: int) -> float:
    return math.log2(frequency + 1)

def get_tier_from_usefulness(usefulness: float, quantiles: dict) -> int:
    """Simple tier assignment based on usefulness quantiles."""
    if usefulness >= quantiles.get(0.88, 4.46):
        return 1
    elif usefulness >= quantiles.get(0.75, 3.0):
        return 2
    elif usefulness >= quantiles.get(0.50, 1.58):
        return 3
    else:
        return 4

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be added, do not modify anything")
    parser.add_argument("--max-add", type=int, default=200, help="Maximum number of new words to add (safety limit)")
    args = parser.parse_args()

    print("=== Adding Missing Real Words to Vocabulary ===\n")

    # Load data
    with open(MISSING_WORDS_PATH, "r", encoding="utf-8") as f:
        missing_data = json.load(f)
    missing_words = missing_data["missing_real_words"]

    with open(LEMMAS_JSON, "r", encoding="utf-8") as f:
        current_lemmas = json.load(f)

    existing_lemmas = {l["lemma"].lower() for l in current_lemmas}
    existing_variants = set()
    for l in current_lemmas:
        for v in l.get("variants", []):
            existing_variants.add(v["surface"].lower())

    print(f"Current lemmas in system: {len(current_lemmas)}")
    print(f"Missing real words to process: {len(missing_words)}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get current max lemma id
    max_id = conn.execute("SELECT MAX(id) FROM lemmas").fetchone()[0] or 0

    # Get current usefulness quantiles for tier assignment (approximate)
    usefulness_scores = [row[0] for row in conn.execute("SELECT usefulness FROM lemmas WHERE usefulness > 0")]
    if usefulness_scores:
        usefulness_scores.sort(reverse=True)
        n = len(usefulness_scores)
        quantiles = {
            0.88: usefulness_scores[int(n * 0.12)] if n > 0 else 4.46,
            0.75: usefulness_scores[int(n * 0.25)] if n > 0 else 3.0,
            0.50: usefulness_scores[int(n * 0.50)] if n > 0 else 1.58,
        }
    else:
        quantiles = {0.88: 4.46, 0.75: 3.0, 0.50: 1.58}

    to_add_as_new_lemma = []
    to_add_as_variant = []

    for item in missing_words:
        word = item["word"].lower()
        freq = item["frequency"]

        if word in existing_lemmas:
            continue

        # Check if it's a known contraction
        if word in CONTRACTION_MAP:
            base = CONTRACTION_MAP[word]
            if base in existing_lemmas:
                to_add_as_variant.append({
                    "surface": word,
                    "frequency": freq,
                    "base_lemma": base
                })
            else:
                # Rare case: base not in system yet → treat as new lemma
                usefulness = compute_usefulness(freq)
                tier = get_tier_from_usefulness(usefulness, quantiles)
                to_add_as_new_lemma.append({
                    "lemma": word,
                    "total_frequency": freq,
                    "usefulness": usefulness,
                    "tier": tier,
                    "is_contraction": True
                })
        else:
            usefulness = compute_usefulness(freq)
            tier = get_tier_from_usefulness(usefulness, quantiles)
            to_add_as_new_lemma.append({
                "lemma": word,
                "total_frequency": freq,
                "usefulness": usefulness,
                "tier": tier,
                "is_contraction": False
            })

    print(f"\nWill add as new lemmas     : {len(to_add_as_new_lemma)}")
    print(f"Will add as variants       : {len(to_add_as_variant)}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        print("\nTop 15 new lemmas that would be added:")
        for item in sorted(to_add_as_new_lemma, key=lambda x: x["total_frequency"], reverse=True)[:15]:
            print(f"  {item['lemma']:15} freq={item['total_frequency']:5}  usefulness={item['usefulness']:.2f}  tier={item['tier']}")
        return

    # === ACTUAL UPDATE ===

    print("\nStarting database update...")

    conn.execute("BEGIN TRANSACTION")

    # Add new lemmas
    new_lemma_count = 0
    for item in to_add_as_new_lemma[:args.max_add]:
        max_id += 1
        conn.execute("""
            INSERT INTO lemmas (id, lemma, total_frequency, sentence_count, tier, usefulness, sources, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            max_id,
            item["lemma"],
            item["total_frequency"],
            0,  # sentence_count unknown for now
            item["tier"],
            item["usefulness"],
            "friends,bigbang",
            datetime.now().isoformat()
        ))
        new_lemma_count += 1

    # Add variants to existing lemmas
    variant_count = 0
    for item in to_add_as_variant:
        base_lemma = item["base_lemma"]
        # Find the lemma id
        row = conn.execute("SELECT id FROM lemmas WHERE lemma = ?", (base_lemma,)).fetchone()
        if row:
            lemma_id = row[0]
            # Check if variant already exists
            exists = conn.execute("""
                SELECT 1 FROM variants WHERE lemma_id = ? AND surface = ?
            """, (lemma_id, item["surface"])).fetchone()
            if not exists:
                conn.execute("""
                    INSERT INTO variants (lemma_id, surface, frequency)
                    VALUES (?, ?, ?)
                """, (lemma_id, item["surface"], item["frequency"]))
                variant_count += 1

    conn.commit()
    print(f"Added {new_lemma_count} new lemmas to database.")
    print(f"Added {variant_count} new variants to existing lemmas.")

    # Update lemmas.json
    print("Updating lemmas.json...")

    # Reload fresh data from DB for the new lemmas
    new_lemmas_from_db = {}
    for row in conn.execute("""
        SELECT lemma, total_frequency, sentence_count, tier, usefulness 
        FROM lemmas 
        WHERE lemma IN ({})
    """.format(",".join("?" * len(to_add_as_new_lemma))), 
    [x["lemma"] for x in to_add_as_new_lemma[:args.max_add]]):
        new_lemmas_from_db[row[0]] = {
            "lemma": row[0],
            "total_frequency": row[1],
            "sentence_count": row[2],
            "tier": row[3],
            "usefulness": row[4],
            "variants": [],
            "examples": []
        }

    # Add variants to the new lemmas structure if needed
    with open(LEMMAS_JSON, "r", encoding="utf-8") as f:
        json_lemmas = json.load(f)

    json_lemmas.extend(list(new_lemmas_from_db.values()))

    with open(LEMMAS_JSON, "w", encoding="utf-8") as f:
        json.dump(json_lemmas, f, ensure_ascii=False, indent=2)

    print(f"lemmas.json updated with {len(new_lemmas_from_db)} new lemmas.")

    print("\n✅ İşlem tamamlandı. Yeni kelimeler havuza eklendi.")
    print("Önerilen sonraki adım: `python3 scripts/recompute_usefulness.py --assign-tiers` çalıştırarak tier dağılımını güncellemek.")

if __name__ == "__main__":
    main()
