#!/usr/bin/env python3
"""
Export clean lemma-based vocabulary data for the web UI.
Uses the new vocabulary_clean.db (lemmas + variants structure).
"""

import sqlite3
import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data/db/vocabulary_clean.db")
WEB_DIR = os.path.join(PROJECT_ROOT, "data/web")
os.makedirs(WEB_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("Exporting clean lemma-based vocabulary for web...")

# Stats
total_lemmas = conn.execute("SELECT COUNT(*) FROM lemmas").fetchone()[0]
total_variants = conn.execute("SELECT COUNT(*) FROM variants").fetchone()[0]
total_corrections = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]

# Load ALL real example sentences from the original processing (35,985)
all_sentences = []
old_db_path = os.path.join(PROJECT_ROOT, "data/db/vocabulary.db")
try:
    old_conn = sqlite3.connect(old_db_path)
    all_sentences = [row[0] for row in old_conn.execute("SELECT sentence FROM examples")]
    old_conn.close()
    print(f"  {len(all_sentences):,} gerçek örnek cümle yüklendi.")
except Exception as e:
    print(f"  (Uyarı: Örnek cümleler yüklenemedi: {e})")

total_examples = len(all_sentences)

stats = {
    "total_unique_lemmas": total_lemmas,
    "total_variants": total_variants,
    "total_ocr_corrections": total_corrections,
    "total_examples": total_examples,
    "tier_counts": {
        str(t): conn.execute(f"SELECT COUNT(*) FROM lemmas WHERE tier = {t}").fetchone()[0]
        for t in [1, 2, 3, 4]
    },
    "sources": ["Friends (208 episodes)", "The Big Bang Theory (~200+ episodes)"],
    "note": "This data has been cleaned from OCR errors and grouped by lemma. Example sentences are from the original raw data."
}

with open(os.path.join(WEB_DIR, "stats.json"), "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2, ensure_ascii=False)
print(f"  ✓ stats.json ({total_lemmas:,} lemmas)")

# Main lemmas data for UI (top 800 by usefulness)
lemmas_data = []
for row in conn.execute("""
    SELECT id, lemma, total_frequency, max_spread, variant_count, tier, usefulness
    FROM lemmas
    ORDER BY usefulness DESC
    LIMIT 800
"""):
    # Get variants for this lemma
    variants = conn.execute("""
        SELECT surface, frequency, spread, is_base, correction_from
        FROM variants
        WHERE lemma_id = ?
        ORDER BY frequency DESC
        LIMIT 10
    """, (row["id"],)).fetchall()

    # === Varyant bazlı yüksek kaliteli örnek ataması ===
    # Her örnek cümleyi, içinde geçen varyantlarla ilişkilendiriyoruz.
    # Böylece varyasyona tıklayınca sadece o varyasyona ait gerçek örnekler çıkacak.
    examples = []
    if all_sentences:
        # Varyant yüzeylerini topla (temizlenmiş haliyle)
        variant_surfaces = []
        surface_to_variant = {}  # "running" -> "running"
        for v in variants:
            clean = v["surface"].split(" (")[0].strip()
            if clean and len(clean) > 1:
                variant_surfaces.append(clean.lower())
                surface_to_variant[clean.lower()] = v["surface"]

        # Lemma'yı da ekle
        lemma_lower = row["lemma"].lower()
        if lemma_lower not in variant_surfaces:
            variant_surfaces.append(lemma_lower)
            surface_to_variant[lemma_lower] = row["lemma"]

        if variant_surfaces:
            matched_examples = []  # (quality_score, sent, matched_variant_surfaces)

            for sent in all_sentences:
                sent_lower = sent.lower()
                matched_vars = []

                for term in variant_surfaces:
                    if re.search(rf'\b{re.escape(term)}\b', sent_lower):
                        matched_vars.append(surface_to_variant[term])

                if matched_vars:
                    # Kalite skoru
                    slen = len(sent)
                    if slen < 20 or slen > 160:
                        continue

                    length_score = 1 - abs(slen - 75) / 75
                    # Cümlede geçen varyant sayısına göre hafif bonus (daha zengin bağlam)
                    variety_bonus = min(len(matched_vars) * 0.05, 0.15)

                    quality = length_score + variety_bonus
                    matched_examples.append((quality, sent, matched_vars))

            # En kaliteli olanları al (en az 1 varyant geçen)
            matched_examples.sort(reverse=True, key=lambda x: x[0])

            seen_texts = set()
            for score, sent, matched_vars in matched_examples:
                if sent in seen_texts:
                    continue
                seen_texts.add(sent)

                # Bu cümlede geçen varyantlardan birini örnekte etiket olarak koy (tercihen en spesifik olanı)
                primary_variant = matched_vars[0] if matched_vars else row["lemma"]

                examples.append({
                    "text": sent,
                    "source": "dizi",
                    "matched_variants": matched_vars
                })

                if len(examples) >= 5:  # Her lemmaya maks 5 kaliteli örnek
                    break

            # En az 3 örnek olsun diye, gerekirse daha düşük kaliteli olanlardan da ekle
            if len(examples) < 3:
                for score, sent, matched_vars in matched_examples[len(examples):]:
                    if sent not in seen_texts:
                        examples.append({
                            "text": sent,
                            "source": "dizi",
                            "matched_variants": matched_vars
                        })
                        seen_texts.add(sent)
                    if len(examples) >= 3:
                        break

    lemmas_data.append({
        "lemma": row["lemma"],
        "total_frequency": row["total_frequency"],
        "max_spread": row["max_spread"],
        "variant_count": row["variant_count"],
        "tier": row["tier"],
        "usefulness": round(row["usefulness"], 1),
        "variants": [
            {
                "surface": v["surface"],
                "frequency": v["frequency"],
                "is_base": bool(v["is_base"]),
                "corrected_from": v["correction_from"]
            } for v in variants
        ],
        "examples": examples
    })

with open(os.path.join(WEB_DIR, "lemmas.json"), "w", encoding="utf-8") as f:
    json.dump(lemmas_data, f, indent=2, ensure_ascii=False)
print(f"  ✓ lemmas.json (top {len(lemmas_data)} lemmas with variants)")

# Tier samples
tier_samples = {}
for tier in [1, 2, 3]:
    tier_samples[tier] = []
    for row in conn.execute("""
        SELECT lemma, total_frequency, max_spread, variant_count
        FROM lemmas
        WHERE tier = ?
        ORDER BY usefulness DESC
        LIMIT 50
    """, (tier,)):
        tier_samples[tier].append({
            "lemma": row["lemma"],
            "total_freq": row["total_frequency"],
            "spread": row["max_spread"],
            "variants": row["variant_count"]
        })

with open(os.path.join(WEB_DIR, "tier_samples.json"), "w", encoding="utf-8") as f:
    json.dump(tier_samples, f, indent=2, ensure_ascii=False)
print("  ✓ tier_samples.json")

conn.close()
if old_conn:
    old_conn.close()

print("\n✅ Clean exports ready. Use data/web/lemmas.json in the UI.")
