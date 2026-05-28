#!/usr/bin/env python3
"""
Export the FULL vocabulary from vocabulary_v2.db to web-ready lemmas.json.

This creates the complete public vocabulary (not limited to 800).
Includes the new automatic usefulness scores and data-driven tiers.
"""

import sqlite3
import json
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data/db/vocabulary_v2.db"
WEB_DIR = PROJECT_ROOT / "data/web"
WEB_DIR.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("Exporting FULL vocabulary from vocabulary_v2.db...")

# 1. Get all lemmas with new usefulness and tiers
lemmas = []
for row in conn.execute("""
    SELECT id, lemma, total_frequency, sentence_count, tier, usefulness
    FROM lemmas
    ORDER BY usefulness DESC
"""):
    lemma_id = row["id"]
    lemma_name = row["lemma"]

    # Variants (count frequency from occurrences)
    variants = []
    for v in conn.execute("""
        SELECT surface, COUNT(*) as freq
        FROM occurrences 
        WHERE lemma_id = ? 
        GROUP BY surface 
        ORDER BY freq DESC 
        LIMIT 10
    """, (lemma_id,)):
        variants.append({
            "surface": v["surface"],
            "frequency": v["freq"]
        })

    # Examples - Her varyasyon için ayrı ayrı ve adil şekilde cümle çek (daha agresif)
    examples = []
    seen_texts = set()

    # 1. Aşama: Her varyasyondan en az 3-4 örnek çekmeye çalış (eğer varsa)
    for variant in variants:
        surface = variant["surface"]

        variant_examples = conn.execute("""
            SELECT DISTINCT s.text, s.source
            FROM occurrences o
            JOIN sentences s ON s.id = o.sentence_id
            WHERE o.lemma_id = ? AND o.surface = ?
            ORDER BY LENGTH(s.text)
            LIMIT 4
        """, (lemma_id, surface)).fetchall()

        for ex in variant_examples:
            text = ex["text"]
            if text in seen_texts:
                continue
            seen_texts.add(text)

            text_lower = text.lower()
            matched = [v["surface"] for v in variants if v["surface"].lower() in text_lower]

            examples.append({
                "text": text,
                "source": ex["source"],
                "matched_variants": matched
            })

    # 2. Aşama: Kalan kotayı en sık varyasyonlara dağıt (toplam max 18 örnek)
    remaining_slots = 18 - len(examples)
    if remaining_slots > 0:
        for variant in variants:
            if len(examples) >= 18:
                break
            surface = variant["surface"]

            variant_examples = conn.execute("""
                SELECT DISTINCT s.text, s.source
                FROM occurrences o
                JOIN sentences s ON s.id = o.sentence_id
                WHERE o.lemma_id = ? AND o.surface = ?
                ORDER BY LENGTH(s.text)
                LIMIT 5
            """, (lemma_id, surface)).fetchall()

            for ex in variant_examples:
                if len(examples) >= 18:
                    break
                text = ex["text"]
                if text in seen_texts:
                    continue
                seen_texts.add(text)

                text_lower = text.lower()
                matched = [v["surface"] for v in variants if v["surface"].lower() in text_lower]

                examples.append({
                    "text": text,
                    "source": ex["source"],
                    "matched_variants": matched
                })

    # Güvenlik için max 18 ile sınırla
    examples = examples[:18]

    lemmas.append({
        "lemma": lemma_name,
        "total_frequency": row["total_frequency"],
        "sentence_count": row["sentence_count"],
        "tier": row["tier"],
        "usefulness": round(row["usefulness"], 4) if row["usefulness"] else 0.0,
        "variants": variants,
        "examples": examples
    })

print(f"  Exported {len(lemmas):,} lemmas")

# 2. Write the full lemmas.json
output_path = WEB_DIR / "lemmas.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(lemmas, f, ensure_ascii=False, indent=2)

print(f"  ✓ Full lemmas.json written ({output_path})")

# 3. Update stats.json with full numbers
tier_counts = {}
for t in [1, 2, 3, 4]:
    tier_counts[str(t)] = sum(1 for l in lemmas if l["tier"] == t)

stats = {
    "total_unique_lemmas": len(lemmas),
    "tier_counts": tier_counts,
    "sources": ["Friends (~208 episodes)", "The Big Bang Theory (~232 episodes)"],
    "note": "Full vocabulary export with automatic usefulness scores and data-driven tiers (recomputed).",
    "usefulness_formula": "log2(total_frequency + 1)",
    "tier_method": "Quantile-based on usefulness (12% / 25% / 50%)"
}

with open(WEB_DIR / "stats.json", "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print(f"  ✓ stats.json updated with full numbers")

print("\n✅ Full vocabulary successfully exported to web!")
print(f"   Total lemmas now available on web: {len(lemmas):,}")
EOF