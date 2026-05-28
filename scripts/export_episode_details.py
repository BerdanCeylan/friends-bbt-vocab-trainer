#!/usr/bin/env python3
"""
Her bölüm için detaylı veri export eder.
Bu, scripts.html için kullanılacak zengin veriyi üretir.

Her bölüm için şunları içerir:
- Bölüm adı
- Toplam cümle sayısı
- Eşsiz kelime (lemma) sayısı
- Örnek cümleler (ilk 50-60 tane)
- O bölümde geçen en sık 30 lemma
"""

import sqlite3
import json
import os
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data/db/vocabulary_v2.db")
WEB_DIR = os.path.join(PROJECT_ROOT, "data/web")
os.makedirs(WEB_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("Bölüm detaylarını export ediyorum...")

# Tüm bölümleri al
episodes = []
for row in conn.execute("""
    SELECT file, source, COUNT(*) as sentence_count
    FROM sentences
    GROUP BY file, source
    ORDER BY source, sentence_count DESC
"""):
    file_name = row["file"]
    source = row["source"]
    
    # Bu bölümdeki eşsiz lemma sayısını bul
    unique_lemmas = conn.execute("""
        SELECT COUNT(DISTINCT lemma_id) 
        FROM occurrences o
        JOIN sentences s ON o.sentence_id = s.id
        WHERE s.file = ? AND s.source = ?
    """, (file_name, source)).fetchone()[0]
    
    # Bu bölümdeki en sık geçen 25 lemma
    top_lemmas = conn.execute("""
        SELECT l.lemma, COUNT(*) as freq
        FROM occurrences o
        JOIN sentences s ON o.sentence_id = s.id
        JOIN lemmas l ON o.lemma_id = l.id
        WHERE s.file = ? AND s.source = ?
        GROUP BY l.lemma
        ORDER BY freq DESC
        LIMIT 25
    """, (file_name, source)).fetchall()
    
    # Bölümden örnek cümleler (ilk 60 tane)
    sample_sentences = conn.execute("""
        SELECT text 
        FROM sentences 
        WHERE file = ? AND source = ?
        ORDER BY id
        LIMIT 60
    """, (file_name, source)).fetchall()
    
    episodes.append({
        "file": file_name,
        "source": source,
        "label": file_name.replace(".srt", "").replace(" - [arsenaloyal]", ""),
        "sentence_count": row["sentence_count"],
        "unique_lemma_count": unique_lemmas,
        "top_lemmas": [{"lemma": r["lemma"], "frequency": r["freq"]} for r in top_lemmas],
        "sample_sentences": [r["text"] for r in sample_sentences]
    })

# Tüm bölümleri kaydet
with open(os.path.join(WEB_DIR, "episodes_detailed.json"), "w", encoding="utf-8") as f:
    json.dump(episodes, f, indent=2, ensure_ascii=False)

print(f"  ✓ episodes_detailed.json ({len(episodes)} bölüm)")

# Ayrıca her bölüm için ayrı küçük JSON'lar da oluşturabiliriz (daha iyi performans için)
# Şimdilik tek dosyada tutuyoruz.

conn.close()
print("\n✅ Bölüm detayları başarıyla export edildi.")