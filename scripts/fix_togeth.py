#!/usr/bin/env python3
"""
"togeth" gibi yanlış OCR lemma'larını düzeltir.
Özellikle "togeth" → "together" dönüşümü için.

Bu script, hatalı lemma'yı silip doğru lemma'yı oluşturur veya mevcut olana taşır.
"""

import sqlite3

DB_PATH = "/home/duffyduck/ingilizce-sitem/data/db/vocabulary_clean.db"

def fix_togeth():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=== togeth → together düzeltme ===\n")

    # 1. togeth lemma'sını bul
    togeth = conn.execute("SELECT * FROM lemmas WHERE lemma = ?", ("togeth",)).fetchone()
    if not togeth:
        print("togeth lemma bulunamadı. Zaten düzeltilmiş olabilir.")
        conn.close()
        return

    print(f"togeth bulundu → id={togeth['id']}, freq={togeth['total_frequency']}")

    # 2. together lemma'sı var mı kontrol et
    together = conn.execute("SELECT * FROM lemmas WHERE lemma = ?", ("together",)).fetchone()

    if together:
        print(f"together zaten var → id={together['id']}")
        target_id = together['id']
        # together'ın mevcut frekansını güncelle
        new_freq = together['total_frequency'] + togeth['total_frequency']
        new_spread = max(together['max_spread'], togeth['max_spread'])
        conn.execute("UPDATE lemmas SET total_frequency=?, max_spread=? WHERE id=?",
                     (new_freq, new_spread, target_id))
    else:
        print("together lemma yok, yeni oluşturuluyor...")
        conn.execute("""
            INSERT INTO lemmas (lemma, total_frequency, max_spread, variant_count, tier, usefulness, sources)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "together",
            togeth['total_frequency'],
            togeth['max_spread'],
            togeth['variant_count'],
            togeth['tier'],
            togeth['usefulness'],
            togeth['sources']
        ))
        target_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 3. togeth'in varyantlarını together'a taşı
    variants = conn.execute("SELECT * FROM variants WHERE lemma_id = ?", (togeth['id'],)).fetchall()
    print(f"\n{togeth['id']} id'li lemma'dan {len(variants)} varyant taşınıyor...")

    for v in variants:
        # "together" zaten varyant olarak varsa güncelle, yoksa ekle
        existing = conn.execute("""
            SELECT id FROM variants 
            WHERE lemma_id = ? AND surface = ?
        """, (target_id, v['surface'])).fetchone()

        if existing:
            conn.execute("UPDATE variants SET frequency = frequency + ? WHERE id = ?",
                         (v['frequency'], existing['id']))
        else:
            conn.execute("""
                INSERT INTO variants (lemma_id, surface, frequency, spread, is_base, is_broken_fragment, correction_from)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                target_id, 
                v['surface'], 
                v['frequency'], 
                v['spread'], 
                1 if v['surface'] == 'together' else 0,  # together base olsun
                1 if v['surface'] == 'togeth' else v['is_broken_fragment'],
                v['correction_from'] or 'togeth'
            ))

    # 4. togeth lemma'sını ve varyantlarını sil
    conn.execute("DELETE FROM variants WHERE lemma_id = ?", (togeth['id'],))
    conn.execute("DELETE FROM lemmas WHERE id = ?", (togeth['id'],))

    conn.commit()
    print("\n✅ togeth başarıyla together'a taşındı.")

    # Son kontrol
    together_final = conn.execute("SELECT total_frequency FROM lemmas WHERE lemma = ?", ("together",)).fetchone()
    print(f"together yeni toplam frekans: {together_final[0]}")

    conn.close()

if __name__ == "__main__":
    fix_togeth()
