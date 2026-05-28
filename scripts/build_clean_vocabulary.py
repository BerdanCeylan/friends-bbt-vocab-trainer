#!/usr/bin/env python3
"""
Build Clean Vocabulary Database (Lemma + Variants + OCR Corrections)

Bu script, mevcut ham vocabulary.db'yi alarak:
1. OCR / transkripsiyon hatalarını temizler
2. Lemmatization uygular
3. Varyasyonları gruplayarak yüksek kaliteli bir veritabanı üretir

Çıktı:
- data/db/vocabulary_clean.db  (ana temiz veritabanı)
  - lemmas tablosu
  - variants tablosu
  - corrections tablosu (yapılan düzeltmelerin kaydı)

Kullanım:
    python3 scripts/build_clean_vocabulary.py
"""

import os
import re
import sqlite3
import time
import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

# Kendi modüllerimiz
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.append(os.path.join(PROJECT_ROOT, "scripts"))

from lemmatizer import lemmatize
from ocr_corrections import correct_word

# =============================================================================
# PATHS
# =============================================================================
RAW_DB = os.path.join(PROJECT_ROOT, "data/db/vocabulary.db")
CLEAN_DB = os.path.join(PROJECT_ROOT, "data/db/vocabulary_clean.db")

# =============================================================================
# YENİ ŞEMA (Temiz ve Profesyonel)
# =============================================================================

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- Ana öğrenme kartları (lemma bazlı)
CREATE TABLE lemmas (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma               TEXT    UNIQUE NOT NULL COLLATE NOCASE,
    total_frequency     INTEGER DEFAULT 0,
    max_spread          INTEGER DEFAULT 0,
    variant_count       INTEGER DEFAULT 0,
    tier                INTEGER,
    usefulness          REAL,
    sources             TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Her lemma'nın varyasyonları
CREATE TABLE variants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma_id        INTEGER NOT NULL,
    surface         TEXT NOT NULL,
    frequency       INTEGER DEFAULT 0,
    spread          INTEGER DEFAULT 0,
    is_base         BOOLEAN DEFAULT 0,
    correction_from TEXT,                    -- Eğer OCR düzeltmesi yapıldıysa orijinal hali
    FOREIGN KEY (lemma_id) REFERENCES lemmas(id) ON DELETE CASCADE
);

-- Yapılan düzeltmelerin kaydı (şeffaflık için)
CREATE TABLE corrections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original_word   TEXT NOT NULL,
    corrected_to    TEXT NOT NULL,
    correction_type TEXT,                    -- 'ocr', 'manual', etc.
    frequency       INTEGER,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Çok düşük kaliteli / atılan kelimeler (opsiyonel, log için)
CREATE TABLE discarded (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    word            TEXT NOT NULL,
    reason          TEXT,
    frequency       INTEGER,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_lemmas_lemma ON lemmas(lemma);
CREATE INDEX idx_variants_lemma ON variants(lemma_id);
CREATE INDEX idx_variants_surface ON variants(surface);
CREATE INDEX idx_corrections_original ON corrections(original_word);
"""


def init_clean_db(conn: sqlite3.Connection):
    conn.executescript(SCHEMA)
    conn.commit()
    print("✓ Clean database schema created")


# =============================================================================
# ANA İŞLEM
# =============================================================================

def build_clean_database():
    start_time = time.time()
    print("=" * 70)
    print("TV ENGLISH - CLEAN VOCABULARY BUILDER")
    print("=" * 70)

    if not os.path.exists(RAW_DB):
        print(f"ERROR: Raw database not found at {RAW_DB}")
        return

    # Bağlantılar
    raw_conn = sqlite3.connect(RAW_DB)
    raw_conn.row_factory = sqlite3.Row

    if os.path.exists(CLEAN_DB):
        os.remove(CLEAN_DB)
    clean_conn = sqlite3.connect(CLEAN_DB)
    init_clean_db(clean_conn)

    # 1. Ham veriyi oku
    print("\n[1/5] Loading raw vocabulary data...")
    raw_data = []
    for row in raw_conn.execute("""
        SELECT w.word, w.frequency, w.doc_count, w.tier, w.usefulness, w.sources
        FROM words w
        ORDER BY w.frequency DESC
    """):
        raw_data.append({
            "word": row["word"],
            "frequency": row["frequency"],
            "spread": row["doc_count"],
            "tier": row["tier"],
            "usefulness": row["usefulness"],
            "sources": row["sources"]
        })
    print(f"      Loaded {len(raw_data):,} raw surface forms")

    # 2. OCR düzeltmeleri + Lemmatization + Gruplama
    print("\n[2/5] Applying OCR corrections + lemmatization + grouping...")

    lemma_groups: Dict[str, List[dict]] = defaultdict(list)
    corrections_log: List[Tuple] = []

    for item in raw_data:
        original = item["word"]

        # OCR düzeltmesi
        corrected, was_corrected = correct_word(original)

        if was_corrected:
            corrections_log.append((
                original,
                corrected,
                "ocr",
                item["frequency"]
            ))

        # Lemmatization
        lemma = lemmatize(corrected)

        # Varyant bilgisi
        variant_info = {
            "surface": corrected,
            "original_surface": original if was_corrected else None,
            "frequency": item["frequency"],
            "spread": item["spread"],
            "tier": item["tier"],
            "usefulness": item["usefulness"]
        }

        lemma_groups[lemma].append(variant_info)

    print(f"      Found {len(lemma_groups):,} unique lemmas after cleaning")

    # 3. Düzeltmeleri kaydet
    print("\n[3/5] Recording corrections...")
    clean_conn.executemany("""
        INSERT INTO corrections (original_word, corrected_to, correction_type, frequency)
        VALUES (?, ?, ?, ?)
    """, corrections_log)
    clean_conn.commit()
    print(f"      Recorded {len(corrections_log):,} corrections")

    # 4. Lemmas ve Variants tablolarını doldur
    print("\n[4/5] Building lemmas and variants tables...")

    lemma_records = []
    variant_records = []

    for lemma, variants in lemma_groups.items():
        # Agregasyon
        total_freq = sum(v["frequency"] for v in variants)
        max_spread = max(v["spread"] for v in variants)
        best_tier = min(v["tier"] for v in variants)
        total_useful = sum(v["usefulness"] for v in variants)
        sources = "friends,bigbang"  # şimdilik basit

        # En iyi varyantı base form olarak işaretle (lemma ile aynı olan veya en yüksek freq)
        variants_sorted = sorted(variants, key=lambda x: -x["frequency"])
        base_surface = lemma
        for v in variants_sorted:
            if v["surface"] == lemma:
                base_surface = lemma
                break
        if not any(v["surface"] == lemma for v in variants):
            base_surface = variants_sorted[0]["surface"]

        lemma_records.append((
            lemma,
            total_freq,
            max_spread,
            len(variants),
            best_tier,
            round(total_useful, 2),
            sources
        ))

        # Variants
        for v in variants_sorted:
            is_base = 1 if v["surface"] == base_surface else 0
            variant_records.append((
                None,  # lemma_id sonra set edilecek
                v["surface"],
                v["frequency"],
                v["spread"],
                is_base,
                v["original_surface"]
            ))

    # Lemmas'ı insert et
    clean_conn.executemany("""
        INSERT INTO lemmas (lemma, total_frequency, max_spread, variant_count, tier, usefulness, sources)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, lemma_records)

    # lemma_id'leri al
    lemma_id_map = {row[0]: row[1] for row in clean_conn.execute("SELECT lemma, id FROM lemmas")}

    # Variant'lara doğru lemma_id'leri ata
    final_variants = []
    for i, rec in enumerate(variant_records):
        # lemma_id'yi bulmak için lemma_groups'tan lemma'yı almamız lazım
        # Daha temiz bir yol: lemma_groups'u tekrar dolaş
        pass

    # Daha temiz versiyon:
    clean_conn.execute("DELETE FROM variants")  # temizle

    for lemma, variants in lemma_groups.items():
        lemma_id = lemma_id_map[lemma]
        variants_sorted = sorted(variants, key=lambda x: -x["frequency"])
        base_surface = lemma
        for v in variants_sorted:
            if v["surface"] == lemma:
                base_surface = lemma
                break
        if not any(v["surface"] == lemma for v in variants_sorted):
            base_surface = variants_sorted[0]["surface"]

        for v in variants_sorted:
            is_base = 1 if v["surface"] == base_surface else 0
            clean_conn.execute("""
                INSERT INTO variants (lemma_id, surface, frequency, spread, is_base, correction_from)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                lemma_id,
                v["surface"],
                v["frequency"],
                v["spread"],
                is_base,
                v["original_surface"]
            ))

    clean_conn.commit()

    print(f"      Inserted {len(lemma_records):,} lemmas and {len(variant_records):,} variants")

    # 5. Özet
    print("\n[5/5] Generating summary...")

    total_lemmas = clean_conn.execute("SELECT COUNT(*) FROM lemmas").fetchone()[0]
    total_variants = clean_conn.execute("SELECT COUNT(*) FROM variants").fetchone()[0]
    total_corrections = clean_conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]

    print("\n" + "=" * 70)
    print("CLEAN VOCABULARY DATABASE CREATED SUCCESSFULLY")
    print("=" * 70)
    print(f"""
    Output file: {CLEAN_DB}

    Statistics:
      - Unique Lemmas     : {total_lemmas:,}
      - Total Variants    : {total_variants:,}
      - OCR Corrections   : {total_corrections:,}

    This database is significantly cleaner and more suitable for
    language learning applications than the raw surface-form version.
    """)

    raw_conn.close()
    clean_conn.close()

    print(f"Total time: {time.time() - start_time:.1f} seconds")


if __name__ == "__main__":
    build_clean_database()
