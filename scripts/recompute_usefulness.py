#!/usr/bin/env python3
"""
Recomputes automatic usefulness scores for lemmas (replaces old manual Tier system).

Formula (tek seferlik statik hesaplama):
    usefulness = log2(total_frequency + 1)

Kullanım:
- Bir kere çalıştırıp bırakacaksın (yeni bölüm eklenmeyeceği için skor statik kalacak).
- Skor dağılımını gördükten sonra tier kesim noktalarını (yüzdeleri) birlikte karar vereceğiz.
- Frontend'de usefulness skorunu da göstereceğiz.

Script hem veritabanını hem lemmas.json'ı günceller.
"""

import sqlite3
import json
import math
import argparse
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data/db/vocabulary_v2.db"
LEMMAS_JSON = PROJECT_ROOT / "data/web/lemmas.json"


def compute_usefulness(total_frequency: int) -> float:
    """Main usefulness formula. log2 works very well for language frequency distributions."""
    return math.log2(total_frequency + 1)


def main():
    parser = argparse.ArgumentParser(description="Recompute automatic usefulness scores (one-time static calculation)")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would change, don't write anything")
    parser.add_argument("--assign-tiers", action="store_true",
                        help="Ayrıca tier ataması da yapsın (şu an önermiyoruz, skor dağılımını gördükten sonra karar vereceğiz)")
    parser.add_argument("--tier-percentages", nargs=3, type=float, default=[0.12, 0.35, 0.65],
                        help="Tier kesim noktaları (sadece --assign-tiers ile kullanılır)")
    args = parser.parse_args()

    print("=== Recomputing Usefulness Scores & Tiers ===\n")

    conn = sqlite3.connect(DB_PATH)

    # Load all lemmas as mutable dicts
    lemmas = []
    for row in conn.execute("""
        SELECT id, lemma, total_frequency, sentence_count, tier as old_tier
        FROM lemmas
    """):
        lemmas.append({
            'id': row[0],
            'lemma': row[1],
            'total_frequency': row[2],
            'sentence_count': row[3],
            'old_tier': row[4]
        })
    print(f"Loaded {len(lemmas)} lemmas from database")

    # Compute usefulness
    for lem in lemmas:
        lem['usefulness'] = compute_usefulness(lem['total_frequency'])

    # Sort by usefulness (descending)
    sorted_lemmas = sorted(lemmas, key=lambda x: x['usefulness'], reverse=True)
    n = len(sorted_lemmas)

    print(f"\nUsefulness score range: {sorted_lemmas[-1]['usefulness']:.2f} → {sorted_lemmas[0]['usefulness']:.2f}")

    # Kullanıcıya tier karar vermesi için güzel quantile raporu
    print("\n=== Usefulness Skor Dağılımı (Tier kesim noktası seçmen için) ===")
    quantiles = [0.01, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 0.80, 0.90, 0.95, 0.99]
    for q in quantiles:
        idx = int(n * q)
        print(f"  {int(q*100):2}%  →  usefulness = {sorted_lemmas[idx]['usefulness']:.2f}   (örnek: {sorted_lemmas[idx]['lemma']})")

    # Tier ataması sadece --assign-tiers ile yapılsın
    if args.assign_tiers:
        p1, p2, p3 = args.tier_percentages
        tier1_cutoff = int(n * p1)
        tier2_cutoff = int(n * p2)
        tier3_cutoff = int(n * p3)

        print(f"\nTier ataması yapılıyor ({p1*100:.0f}% / {p2*100:.0f}% / {p3*100:.0f}%)")

        for i, lem in enumerate(sorted_lemmas):
            if i < tier1_cutoff:
                lem['new_tier'] = 1
            elif i < tier2_cutoff:
                lem['new_tier'] = 2
            elif i < tier3_cutoff:
                lem['new_tier'] = 3
            else:
                lem['new_tier'] = 4

        tier_counts = defaultdict(int)
        for lem in sorted_lemmas:
            tier_counts[lem['new_tier']] += 1

        print("\nYeni Tier Dağılımı:")
        for t in [1, 2, 3, 4]:
            print(f"  Tier {t}: {tier_counts[t]} lemmas")
    else:
        print("\n[Tier ataması yapılmadı]  --assign-tiers ile istersen sonradan atayabiliriz.")
        for lem in lemmas:
            lem['new_tier'] = lem.get('old_tier', 3)

    # Örnekler
    print("\n--- Örnekler ---")
    print("En yüksek usefulness:")
    for lem in sorted_lemmas[:8]:
        tier_str = f"tier={lem.get('new_tier', '?')}" if args.assign_tiers else ""
        print(f"  {lem['lemma']:15} freq={lem['total_frequency']:6}  usefulness={lem['usefulness']:.2f}  {tier_str}")

    if args.assign_tiers:
        print("\nAround Tier 3→4 boundary:")
        for i in range(tier3_cutoff-2, tier3_cutoff+3):
            lem = sorted_lemmas[i]
            print(f"  {lem['lemma']:18} freq={lem['total_frequency']:6}  usefulness={lem['usefulness']:.2f}  tier={lem['new_tier']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes written.")
        return

    # Update database
    print("\nUpdating database...")
    conn.execute("BEGIN TRANSACTION")
    for lem in lemmas:
        conn.execute("""
            UPDATE lemmas 
            SET usefulness = ?, tier = ?
            WHERE id = ?
        """, (lem['usefulness'], lem['new_tier'], lem['id']))
    conn.commit()
    print("Database updated.")

    # Update lemmas.json (the one used by the web UI)
    print("Updating lemmas.json...")
    with open(LEMMAS_JSON, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    lookup = {l['lemma']: l for l in lemmas}

    updated = 0
    for jlem in json_data:
        if jlem['lemma'] in lookup:
            db = lookup[jlem['lemma']]
            jlem['usefulness'] = round(db['usefulness'], 4)
            jlem['tier'] = db['new_tier']
            updated += 1

    with open(LEMMAS_JSON, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print(f"Updated {updated} lemmas in lemmas.json")

    print("\n✅ Usefulness + Tier recomputation complete!")
    print("   The new system is now fully automatic and data-driven.")


if __name__ == "__main__":
    main()
EOF