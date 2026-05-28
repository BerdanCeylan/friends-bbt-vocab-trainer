#!/usr/bin/env python3
"""
Export from the new clean vocabulary_v2.db (from-scratch pipeline)
into web-ready JSON files.

This version properly uses the occurrences table to attach real,
linked example sentences to each lemma.
"""

import sqlite3
import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data/db/vocabulary_v2.db")
WEB_DIR = os.path.join(PROJECT_ROOT, "data/web")
os.makedirs(WEB_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("Exporting from vocabulary_v2.db (clean pipeline)...")

# 1. Stats
total_lemmas = conn.execute("SELECT COUNT(*) FROM lemmas").fetchone()[0]
total_occurrences = conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0]
total_sentences = conn.execute("SELECT COUNT(*) FROM sentences").fetchone()[0]
total_discarded = conn.execute("SELECT COUNT(*) FROM discarded").fetchone()[0]

# Basic tier distribution (we can improve tier logic later)
tier_counts = {}
for t in [1, 2, 3, 4]:
    tier_counts[str(t)] = conn.execute(
        "SELECT COUNT(*) FROM lemmas WHERE tier = ?", (t,)
    ).fetchone()[0]

stats = {
    "total_unique_lemmas": total_lemmas,
    "total_occurrences": total_occurrences,
    "total_sentences": total_sentences,
    "total_discarded": total_discarded,
    "tier_counts": tier_counts,
    "sources": ["Friends (208 episodes)", "The Big Bang Theory (~200+ episodes)"],
    "note": "Generated from clean from-scratch pipeline (vocabulary_v2.db). Examples are properly linked via occurrences table."
}

with open(os.path.join(WEB_DIR, "stats.json"), "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2, ensure_ascii=False)
print(f"  ✓ stats.json ({total_lemmas:,} lemmas)")

# 2. Main lemmas data (top 800 by frequency for now)
# We will attach real examples using the occurrences table.
lemmas_data = []

for row in conn.execute("""
    SELECT id, lemma, total_frequency, sentence_count, tier
    FROM lemmas
    ORDER BY total_frequency DESC
    LIMIT 800
"""):
    lemma_id = row["id"]

    # Get some distinct surfaces (variants) for this lemma
    variants = conn.execute("""
        SELECT DISTINCT surface, COUNT(*) as freq
        FROM occurrences
        WHERE lemma_id = ?
        GROUP BY surface
        ORDER BY freq DESC
        LIMIT 8
    """, (lemma_id,)).fetchall()

    # Get real linked example sentences + which variants they match
    # This allows proper per-variant filtering in the UI
    example_rows = conn.execute("""
        SELECT DISTINCT s.text, s.source
        FROM occurrences o
        JOIN sentences s ON o.sentence_id = s.id
        WHERE o.lemma_id = ?
        ORDER BY LENGTH(s.text)
        LIMIT 6
    """, (lemma_id,)).fetchall()

    # Collect variant surfaces for matching
    variant_surfaces = [v["surface"] for v in variants]

    examples = []
    for ex in example_rows:
        text_lower = ex["text"].lower()
        matched = []
        for surf in variant_surfaces:
            if re.search(rf'\b{re.escape(surf.lower())}\b', text_lower):
                matched.append(surf)

        examples.append({
            "text": ex["text"],
            "source": ex["source"],
            "matched_variants": matched
        })

    lemmas_data.append({
        "lemma": row["lemma"],
        "total_frequency": row["total_frequency"],
        "sentence_count": row["sentence_count"],
        "tier": row["tier"],
        "variants": [
            {"surface": v["surface"], "frequency": v["freq"]} for v in variants
        ],
        "examples": examples
    })

with open(os.path.join(WEB_DIR, "lemmas.json"), "w", encoding="utf-8") as f:
    json.dump(lemmas_data, f, indent=2, ensure_ascii=False)
print(f"  ✓ lemmas.json (top {len(lemmas_data)} lemmas with real linked examples)")

# 3. Tier samples (for quick overview)
tier_samples = {}
for tier in [1, 2, 3]:
    tier_samples[tier] = []
    for row in conn.execute("""
        SELECT lemma, total_frequency, sentence_count
        FROM lemmas
        WHERE tier = ?
        ORDER BY total_frequency DESC
        LIMIT 40
    """, (tier,)):
        tier_samples[tier].append({
            "lemma": row["lemma"],
            "total_freq": row["total_frequency"],
            "sentence_count": row["sentence_count"]
        })

with open(os.path.join(WEB_DIR, "tier_samples.json"), "w", encoding="utf-8") as f:
    json.dump(tier_samples, f, indent=2, ensure_ascii=False)
print("  ✓ tier_samples.json")

conn.close()

print("\n✅ Export from vocabulary_v2.db complete.")
print("   Web files are ready in data/web/")
print("   You can now update the UI to use these new files.")