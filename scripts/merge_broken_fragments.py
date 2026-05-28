#!/usr/bin/env python3
"""
Systematic detection and merging of broken contraction fragments.

Goal (Option B):
- Detect fragments like "don", "doesn", "didn", "isn", "wouldn" etc.
- Merge their frequencies into the correct base lemma ("do", "be", "would" etc.)
- Keep the information as special variants with `is_broken_fragment = 1`
- This preserves spoken frequency data without polluting the learning pool with fake words.

Usage:
    python3 scripts/merge_broken_fragments.py
"""

import sqlite3
import time
from collections import defaultdict

CLEAN_DB = "/home/duffyduck/ingilizce-sitem/data/db/vocabulary_clean.db"

# =============================================================================
# HIGH-CONFIDENCE MAPPING: broken_fragment → target_lemma
# =============================================================================
BROKEN_FRAGMENT_MAP = {
    # do family
    "don": "do",
    "doesn": "do",
    "didn": "do",
    
    # be family
    "isn": "be",
    "aren": "be",
    "weren": "be",
    "wasn": "be",
    "ain": "be",          # ain't
    
    # have family
    "haven": "have",
    "hasn": "have",
    "hadn": "have",
    
    # modal family
    "wouldn": "would",
    "couldn": "could",
    "shouldn": "should",
    "won": "will",        # won't
    "mustn": "must",
    "needn": "need",
    "daren": "dare",
}

# Words that look like fragments but are actually legitimate (whitelist)
LEGITIMATE_SHORT_N_WORDS = {
    "can", "when", "then", "mean", "than", "person", "man", "woman",
    "down", "fun", "win", "turn", "own", "run", "plan", "reason", "learn",
    "open", "even", "again", "listen", "happen", "begin", "return", "common",
    "human", "certain", "sudden", "often", "between", "soon", "town", "skin",
    "brain", "train", "clean", "join", "mention", "explain", "concern",
    "fashion", "action", "station", "option", "million", "design", "button",
    "kitchen", "chicken", "indian", "london", "queen", "brown", "moon",
    "born", "grown", "shown", "known", "taken", "given", "spoken", "broken",
    "chosen", "driven", "written", "eaten", "beaten", "forgotten",
}

def get_target_lemma(fragment: str) -> str | None:
    """Return the correct lemma for a broken fragment, or None if not a fragment."""
    fragment = fragment.lower()
    
    if fragment in LEGITIMATE_SHORT_N_WORDS:
        return None
    
    if fragment in BROKEN_FRAGMENT_MAP:
        return BROKEN_FRAGMENT_MAP[fragment]
    
    # Heuristic rules for unknown cases
    if fragment.endswith("sn") or fragment.endswith("dn"):
        # doesn, hasn, hadn, wasn, couldn, etc. → usually "do" or modals
        if fragment in ["doesn", "didn", "hasn", "hadn"]:
            return "do" if fragment in ["doesn", "didn"] else "have"
        if fragment.endswith("dn"):
            return fragment[:-2] + "d"   # couldn → could (rough)
    
    if fragment.endswith("n") and len(fragment) <= 7:
        # Very low spread + high freq is strong signal
        pass
    
    return None

def merge_broken_fragments():
    start = time.time()
    print("=== Merging Broken Contraction Fragments (Option B) ===\n")

    conn = sqlite3.connect(CLEAN_DB)
    conn.row_factory = sqlite3.Row

    # Ensure we have the necessary columns
    conn.execute("ALTER TABLE variants ADD COLUMN is_broken_fragment INTEGER DEFAULT 0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fragment_merges (
            id INTEGER PRIMARY KEY,
            broken_fragment TEXT,
            target_lemma TEXT,
            frequency_merged INTEGER,
            spread_merged INTEGER,
            merged_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("DELETE FROM fragment_merges")  # fresh run
    conn.commit()

    # Get all current lemmas that might be fragments
    candidates = conn.execute("""
        SELECT id, lemma, total_frequency, max_spread
        FROM lemmas
        WHERE length(lemma) BETWEEN 3 AND 7
          AND lemma LIKE "%n"
        ORDER BY total_frequency DESC
    """).fetchall()

    print(f"Scanning {len(candidates)} short 'n-ending' lemmas...\n")

    merges_done = 0
    total_freq_merged = 0

    for row in candidates:
        fragment = row["lemma"]
        target = get_target_lemma(fragment)

        if not target:
            continue

        freq = row["total_frequency"]
        spread = row["max_spread"]

        # Find or create target lemma
        target_row = conn.execute(
            "SELECT id, total_frequency, max_spread FROM lemmas WHERE lemma = ?", 
            (target,)
        ).fetchone()

        if not target_row:
            # Create the target lemma if it doesn't exist (rare)
            conn.execute("""
                INSERT INTO lemmas (lemma, total_frequency, max_spread, tier, usefulness, sources)
                VALUES (?, 0, 0, 3, 0, 'merged')
            """, (target,))
            target_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            target_freq = 0
            target_spread = 0
        else:
            target_id = target_row["id"]
            target_freq = target_row["total_frequency"]
            target_spread = target_row["max_spread"]

        # Insert as special variant
        conn.execute("""
            INSERT INTO variants (lemma_id, surface, frequency, spread, is_base, is_broken_fragment)
            VALUES (?, ?, ?, ?, 0, 1)
        """, (target_id, f"{fragment} (broken token)", freq, spread))

        # Update target lemma totals
        new_total = target_freq + freq
        new_spread = max(target_spread, spread)
        conn.execute("""
            UPDATE lemmas 
            SET total_frequency = ?, max_spread = ?
            WHERE id = ?
        """, (new_total, new_spread, target_id))

        # Log the merge
        conn.execute("""
            INSERT INTO fragment_merges (broken_fragment, target_lemma, frequency_merged, spread_merged)
            VALUES (?, ?, ?, ?)
        """, (fragment, target, freq, spread))

        # Remove the broken lemma (we've already extracted its value)
        conn.execute("DELETE FROM variants WHERE lemma_id = ?", (row["id"],))
        conn.execute("DELETE FROM lemmas WHERE id = ?", (row["id"],))

        print(f"  Merged '{fragment}' ({freq}) → '{target}'")
        merges_done += 1
        total_freq_merged += freq

    conn.commit()

    print(f"\n✅ Done. Merged {merges_done} fragments.")
    print(f"   Total frequency salvaged: {total_freq_merged:,}")

    # Show summary
    print("\n=== Merge Summary ===")
    for row in conn.execute("""
        SELECT broken_fragment, target_lemma, frequency_merged 
        FROM fragment_merges 
        ORDER BY frequency_merged DESC
    """):
        print(f"  {row['broken_fragment']:10} → {row['target_lemma']:8} (+{row['frequency_merged']})")

    conn.close()
    print(f"\nTotal time: {time.time() - start:.1f}s")

if __name__ == "__main__":
    merge_broken_fragments()
