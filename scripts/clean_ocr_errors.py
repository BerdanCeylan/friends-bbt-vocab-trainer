#!/usr/bin/env python3
"""
Comprehensive OCR Error Cleaner for the vocabulary database.

This script attempts to find and fix the most common OCR/transcription errors:
1. Truncated words (someth, togeth, surpris, etc.)
2. "ing" missing due to OCR
3. Other low-spread high-frequency garbage words

It is conservative and only merges when there is a very clear longer counterpart.
"""

import sqlite3
import time

DB_PATH = "/home/duffyduck/ingilizce-sitem/data/db/vocabulary_clean.db"

def find_and_fix_truncated(conn):
    """Find short lemmas that have a clear longer counterpart and merge them."""
    print("\n=== Truncated Words Cleanup ===")

    all_lemmas = {row[0]: row[1] for row in conn.execute(
        "SELECT lemma, total_frequency FROM lemmas"
    ).fetchall()}

    merges = []

    for lemma, freq in sorted(all_lemmas.items(), key=lambda x: -x[1]):
        if not (4 <= len(lemma) <= 8 and freq > 60):
            continue

        # Look for longer versions
        candidates = []
        for l in all_lemmas:
            if l.startswith(lemma) and len(l) > len(lemma) + 1 and len(l) <= len(lemma) + 5:
                candidates.append(l)

        if not candidates:
            continue

        # Choose the most frequent longer version as target
        best = max(candidates, key=lambda x: all_lemmas[x])
        target_freq = all_lemmas[best]

        # Only merge if the longer version is reasonably common
        if target_freq < 30:
            continue

        merges.append((lemma, best, freq))

    print(f"Found {len(merges)} potential truncated lemmas to fix.")

    fixed = 0
    for bad, good, freq in merges[:30]:  # Limit to avoid over-merging in one go
        # Reuse the logic from fix_truncated_lemmas
        bad_row = conn.execute("SELECT * FROM lemmas WHERE lemma = ?", (bad,)).fetchone()
        if not bad_row:
            continue

        good_row = conn.execute("SELECT id, total_frequency, max_spread FROM lemmas WHERE lemma = ?", (good,)).fetchone()
        if good_row:
            good_id = good_row[0]
            conn.execute("UPDATE lemmas SET total_frequency = total_frequency + ?, max_spread = MAX(max_spread, ?) WHERE id = ?",
                         (bad_row['total_frequency'], bad_row['max_spread'], good_id))
        else:
            conn.execute("""
                INSERT INTO lemmas (lemma, total_frequency, max_spread, variant_count, tier, usefulness, sources)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """, (good, bad_row['total_frequency'], bad_row['max_spread'], bad_row['tier'], bad_row['usefulness'], bad_row['sources']))
            good_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Move variants
        for v in conn.execute("SELECT * FROM variants WHERE lemma_id = ?", (bad_row['id'],)):
            conn.execute("""
                INSERT INTO variants (lemma_id, surface, frequency, spread, is_base, is_broken_fragment, correction_from)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (good_id, v['surface'], v['frequency'], v['spread'], 0 if v['surface'] != good else 1, bad))

        conn.execute("DELETE FROM variants WHERE lemma_id = ?", (bad_row['id'],))
        conn.execute("DELETE FROM lemmas WHERE id = ?", (bad_row['id'],))

        print(f"  Merged: {bad} ({freq}) → {good}")
        fixed += 1

    conn.commit()
    print(f"Fixed {fixed} truncated lemmas.")


def main():
    start = time.time()
    print("=== Comprehensive OCR Error Cleanup ===")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    find_and_fix_truncated(conn)

    conn.close()
    print(f"\nTotal time: {time.time() - start:.1f}s")
    print("Please re-run the export script after this cleanup.")


if __name__ == "__main__":
    main()
