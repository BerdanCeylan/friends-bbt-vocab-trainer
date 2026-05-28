#!/usr/bin/env python3
"""
Remove obvious junk / character names / single-file OCR garbage from the clean vocabulary.

This is a controlled cleanup for the worst offenders (Category 1 + 4 from the scan).
"""

import sqlite3
import time

DB_PATH = "/home/duffyduck/ingilizce-sitem/data/db/vocabulary_clean.db"

# Conservative list of the most obvious junk to remove
JUNK_TO_REMOVE = [
    "wolowitz", "koothrappali", "hofstadt", "priya", "rajesh",
    "howie", "chandy", "chang", "christma", "spock", "zack",
    "physic", "physicist", "bert", "sheldon", "leonard", "penny", "amy"
]

def main():
    start = time.time()
    print("=== Removing Junk / Character Names from Clean DB ===\n")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Recreate discarded table cleanly
    conn.execute("DROP TABLE IF EXISTS discarded")
    conn.execute("""
        CREATE TABLE discarded (
            id INTEGER PRIMARY KEY,
            word TEXT,
            reason TEXT,
            total_frequency INTEGER,
            max_spread INTEGER,
            discarded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    removed_count = 0
    total_freq_removed = 0

    for word in JUNK_TO_REMOVE:
        row = conn.execute("""
            SELECT id, total_frequency, max_spread 
            FROM lemmas WHERE lemma = ?
        """, (word,)).fetchone()

        if not row:
            print(f"  {word:15} → not found (already removed?)")
            continue

        lemma_id, freq, spread = row

        # Move to discarded
        conn.execute("""
            INSERT INTO discarded (word, reason, total_frequency, max_spread)
            VALUES (?, ?, ?, ?)
        """, (word, "ocr_junk_or_character_name", freq, spread))

        # Delete variants
        conn.execute("DELETE FROM variants WHERE lemma_id = ?", (lemma_id,))

        # Delete lemma
        conn.execute("DELETE FROM lemmas WHERE id = ?", (lemma_id,))

        print(f"  Removed: {word:15} (freq={freq}, spread={spread})")
        removed_count += 1
        total_freq_removed += freq

    conn.commit()
    conn.close()

    print(f"\n✅ Done. Removed {removed_count} junk items.")
    print(f"   Total frequency removed: {total_freq_removed:,}")
    print(f"\nPlease re-run the export script to update the web data.")

    print(f"\nTotal time: {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
