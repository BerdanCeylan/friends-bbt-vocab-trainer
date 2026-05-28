#!/usr/bin/env python3
"""
Fix truncated lemmas caused by OCR (e.g. "someth" → "something", "sometim" → "sometimes", "togeth" → "together").

This is a common OCR pattern where the end of the word is cut off or misread.
"""

import sqlite3

DB_PATH = "/home/duffyduck/ingilizce-sitem/data/db/vocabulary_clean.db"

# Manual high-confidence mappings for now
# Format: bad_truncated_lemma → correct_full_lemma
TRUNCATED_FIXES = {
    "someth": "something",
    "sometim": "sometimes",
    # Add more as we discover them
}

def fix_truncated_lemma(bad_lemma: str, good_lemma: str, conn):
    """Merge a bad truncated lemma into the correct one."""
    bad_row = conn.execute(
        "SELECT id, total_frequency, max_spread, tier, usefulness, sources FROM lemmas WHERE lemma = ?",
        (bad_lemma,)
    ).fetchone()

    if not bad_row:
        print(f"  {bad_lemma} not found, skipping.")
        return False

    bad_id, bad_freq, bad_spread, bad_tier, bad_useful, bad_sources = bad_row

    # Find or create the good lemma
    good_row = conn.execute(
        "SELECT id, total_frequency, max_spread FROM lemmas WHERE lemma = ?",
        (good_lemma,)
    ).fetchone()

    if good_row:
        good_id, good_freq, good_spread = good_row
        new_freq = good_freq + bad_freq
        new_spread = max(good_spread, bad_spread)
        conn.execute(
            "UPDATE lemmas SET total_frequency = ?, max_spread = ? WHERE id = ?",
            (new_freq, new_spread, good_id)
        )
    else:
        conn.execute("""
            INSERT INTO lemmas (lemma, total_frequency, max_spread, variant_count, tier, usefulness, sources)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (good_lemma, bad_freq, bad_spread, 1, bad_tier, bad_useful, bad_sources))
        good_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Move variants from bad to good
    variants = conn.execute("SELECT * FROM variants WHERE lemma_id = ?", (bad_id,)).fetchall()
    for v in variants:
        conn.execute("""
            INSERT INTO variants (lemma_id, surface, frequency, spread, is_base, is_broken_fragment, correction_from)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            good_id,
            v["surface"],
            v["frequency"],
            v["spread"],
            1 if v["surface"] == good_lemma else 0,
            1,
            v["correction_from"] or bad_lemma
        ))

    # Delete the bad lemma and its variants
    conn.execute("DELETE FROM variants WHERE lemma_id = ?", (bad_id,))
    conn.execute("DELETE FROM lemmas WHERE id = ?", (bad_id,))

    print(f"  Fixed: {bad_lemma} ({bad_freq}) → {good_lemma}")
    return True


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=== Fixing Truncated OCR Lemmas ===\n")

    fixed_count = 0
    for bad, good in TRUNCATED_FIXES.items():
        if fix_truncated_lemma(bad, good, conn):
            fixed_count += 1

    conn.commit()
    conn.close()

    print(f"\n✅ Fixed {fixed_count} truncated lemmas.")
    print("Please re-run the export script after this.")


if __name__ == "__main__":
    main()
