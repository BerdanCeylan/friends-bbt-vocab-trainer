#!/usr/bin/env python3
"""
TV English - Clean Vocabulary Pipeline (From Scratch)

Bu script, Friends + Big Bang Theory altyazılarını baştan, temiz ve doğru bir şekilde işler.

Amaç:
- Her cümleyi kaliteli filtrelemeden geçirmek
- Her cümlede geçen kelimeleri (surface + lemma) doğru şekilde tespit etmek
- Her cümleyi, içerdiği kelimelerle **gerçek anlamda** ilişkilendirmek
- Yüksek kaliteli, öğrenmeye uygun bir kelime havuzu + örnek cümleler oluşturmak

Kullanım:
    python3 scripts/build_vocabulary_from_scratch.py
"""

import os
import re
import glob
import sqlite3
import time
from collections import defaultdict
from datetime import datetime

# --- Mevcut araçlarımızı import ediyoruz ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.append(os.path.join(PROJECT_ROOT, "scripts"))

from lemmatizer import lemmatize, clean_surface, strip_outer_quotes
from ocr_corrections import correct_word

# =============================================================================
# AYARLAR
# =============================================================================
RAW_FRIENDS_DIR = os.path.join(PROJECT_ROOT, "data/subtitles/friends")
RAW_BBT_FILE    = os.path.join(PROJECT_ROOT, "data/subtitles/bigbangtheory/transcripts.txt")
OUTPUT_DB       = os.path.join(PROJECT_ROOT, "data/db/vocabulary_v2.db")

# Kalite filtreleri (bunları ileride daha da güçlendireceğiz)
MIN_SENTENCE_LENGTH = 12
MIN_TOKEN_LENGTH    = 2
MAX_TOKEN_LENGTH    = 18

# =============================================================================
# VERİTABANI ŞEMASI (Temiz ve Doğru)
# =============================================================================
SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- 1. Ham cümleler (kaynak)
CREATE TABLE sentences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    source      TEXT NOT NULL,           -- 'friends' veya 'bigbang'
    file        TEXT,                    -- hangi dosya / bölüm
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 2. Ana kelime havuzu (lemma bazlı)
CREATE TABLE lemmas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma             TEXT UNIQUE NOT NULL COLLATE NOCASE,
    total_frequency   INTEGER DEFAULT 0,
    sentence_count    INTEGER DEFAULT 0,     -- bu kelimenin geçtiği cümle sayısı
    tier              INTEGER DEFAULT 3,
    usefulness        REAL DEFAULT 0,
    sources           TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 3. Cümle - Kelime bağlantısı (en önemli tablo)
-- Bu tablo sayesinde "bu cümle bu kelimeye gerçekten ait" diyebiliyoruz.
CREATE TABLE occurrences (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id     INTEGER NOT NULL,
    lemma_id        INTEGER NOT NULL,
    surface         TEXT NOT NULL,           -- cümlede nasıl geçmiş (running, gonna vs.)
    FOREIGN KEY (sentence_id) REFERENCES sentences(id) ON DELETE CASCADE,
    FOREIGN KEY (lemma_id)   REFERENCES lemmas(id)   ON DELETE CASCADE
);

-- 4. Çok düşük kaliteli kelimeler (log için)
CREATE TABLE discarded (
    id              INTEGER PRIMARY KEY,
    word            TEXT,
    reason          TEXT,
    total_frequency INTEGER,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_occurrences_lemma ON occurrences(lemma_id);
CREATE INDEX idx_occurrences_sentence ON occurrences(sentence_id);
CREATE INDEX idx_lemmas_lemma ON lemmas(lemma);
"""

def init_db(conn: sqlite3.Connection):
    conn.executescript(SCHEMA)
    conn.commit()
    print("✓ Temiz veritabanı şeması oluşturuldu")

# =============================================================================
# CÜMLE ÇIKARMA (Sağlam)
# =============================================================================

def clean_text(text: str) -> str:
    """Temel temizlik"""
    text = text.lower()
    text = correct_word(text)[0]  # OCR düzeltmeleri

    # Gürültü temizleme
    text = re.sub(r'\([^)]{2,40}\)', ' ', text)   # (laughs)
    text = re.sub(r'\[[^\]]{2,40}\]', ' ', text)
    text = re.sub(r'♪[^♪]*♪', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_friends_sentences(filepath: str):
    """Friends .srt dosyalarından temiz cümleler çıkarır"""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    content = content.replace("\ufeff", "")

    blocks = re.split(r"\n\s*\n", content)
    sentences = []

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue

        idx = 0
        if lines[0].isdigit():
            idx = 1
        if idx < len(lines) and "-->" in lines[idx]:
            idx += 1

        text = " ".join(lines[idx:])
        text = re.sub(r"^\s*-\s*", "", text)
        text = re.sub(r"\s+-\s+", " ", text)

        cleaned = clean_text(text)
        if len(cleaned) >= MIN_SENTENCE_LENGTH:
            sentences.append(cleaned)

    return sentences

def extract_bbt_sentences(raw_text: str):
    """BBT transcript'inden temiz cümleler çıkarır"""
    # Konuşmacı etiketlerini temizle
    text = re.sub(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?:\s*", "", raw_text, flags=re.MULTILINE)
    text = re.sub(r"\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?:\s+", " ", text)

    # Cümlelere böl
    raw_sentences = re.split(r"[.!?]\s+", text)
    sentences = []

    for s in raw_sentences:
        cleaned = clean_text(s)
        if len(cleaned) >= MIN_SENTENCE_LENGTH:
            sentences.append(cleaned)

    return sentences

# =============================================================================
# TOKENİZASYON + FİLTRELEME (Burayı çok güçlü yapacağız)
# =============================================================================

def tokenize_and_filter(text: str):
    """
    Geliştirilmiş kaliteli tokenizasyon + filtreleme.
    """
    # Tokenize et, sonra her token'ı quote temizliğinden geçir
    raw_tokens = re.findall(r"\b[a-zA-Z']+\b", text.lower())
    tokens = [clean_surface(t) for t in raw_tokens if t]

    good_tokens = []

    # Güçlü karakter ismi ve junk blacklist
    JUNK_WORDS = {
        "sheldon", "leonard", "penny", "amy", "bernadette", "howard", "raj", "stuart",
        "wolowitz", "koothrappali", "hofstadter", "rachel", "ross", "monica", "chandler",
        "joey", "phoebe", "chandy", "chang", "rach", "rachei", "sheld", "leon",
        "wolow", "kooth", "priya", "rajesh", "zack", "bert", "spock"
    }

    for tok in tokens:
        if len(tok) < MIN_TOKEN_LENGTH or len(tok) > MAX_TOKEN_LENGTH:
            continue

        # Karakter ismi ve bilinen junk
        if tok in JUNK_WORDS:
            continue

        # Basit stopword'ler (konuşma dili için hafif tuttuk)
        if tok in {"the", "a", "an", "to", "of", "and", "or", "but", "in", "on", "at", "for", "it", "is", "was", "be"}:
            continue

        # OCR / truncation şüphesi (çok kısa ve sonu garip kesilmiş)
        if len(tok) <= 6 and tok.endswith(("eth", "in", "im", "ng", "ch", "nd")):
            # Bunlar genellikle "something", "together", "chandler" gibi kelimelerin kırık halleri
            continue

        # Bariz OCR junk karakterleri
        if re.search(r'[^a-z\']', tok):
            continue

        # Tekrar eden harfler (çoğu OCR hatası)
        if re.search(r'(.)\1{2,}', tok):
            continue

        good_tokens.append(tok)

    return good_tokens

# =============================================================================
# ANA İŞLEM
# =============================================================================

def build_clean_database():
    start = time.time()
    print("=" * 70)
    print("TV ENGLISH - CLEAN PIPELINE FROM SCRATCH")
    print("=" * 70)

    if os.path.exists(OUTPUT_DB):
        os.remove(OUTPUT_DB)

    conn = sqlite3.connect(OUTPUT_DB)
    init_db(conn)

    # --- 1. Cümleleri topla ---
    print("\n[1/5] Ham cümleler toplanıyor...")

    friends_files = glob.glob(os.path.join(RAW_FRIENDS_DIR, "*.srt"))
    all_sentences = []  # (text, source, file)

    for f in friends_files:
        sents = extract_friends_sentences(f)
        for s in sents:
            all_sentences.append((s, "friends", os.path.basename(f)))

    with open(RAW_BBT_FILE, "r", encoding="utf-8", errors="ignore") as f:
        bbt_raw = f.read()
    bbt_sents = extract_bbt_sentences(bbt_raw)
    for s in bbt_sents:
        all_sentences.append((s, "bigbang", "transcripts.txt"))

    print(f"      Toplam {len(all_sentences):,} temiz cümle bulundu.")

    # --- 2. Cümleleri ve kelimeleri işle ---
    print("\n[2/5] Cümleler işleniyor ve kelimelerle ilişkilendiriliyor...")

    lemma_freq = defaultdict(int)
    lemma_sentences = defaultdict(set)   # lemma -> set of sentence_ids
    sentence_data = []                   # (text, source, file)

    for idx, (text, source, file) in enumerate(all_sentences):
        tokens = tokenize_and_filter(text)
        if not tokens:
            continue

        # Cümleyi kaydet
        sentence_data.append((text, source, file))

        # Bu cümlede geçen kelimeleri işle
        for tok in tokens:
            lemma = lemmatize(tok)
            lemma_freq[lemma] += 1
            # Bu cümleyi bu lemmaya bağla (şu an sentence_id'yi daha sonra vereceğiz)

        if (idx + 1) % 20000 == 0:
            print(f"      {idx+1:,} cümle işlendi...")

    print(f"      {len(lemma_freq):,} eşsiz lemma bulundu.")

    # --- 3. Veritabanına yaz ---
    print("\n[3/5] Veritabanına yazılıyor...")

    # Önce cümleleri yaz
    conn.executemany("""
        INSERT INTO sentences (text, source, file)
        VALUES (?, ?, ?)
    """, sentence_data)

    # Lemma'ları yaz
    lemma_rows = []
    for lemma, freq in sorted(lemma_freq.items(), key=lambda x: -x[1]):
        lemma_rows.append((lemma, freq, 0, 3, 0.0, "friends,bigbang"))

    conn.executemany("""
        INSERT INTO lemmas (lemma, total_frequency, sentence_count, tier, usefulness, sources)
        VALUES (?, ?, ?, ?, ?, ?)
    """, lemma_rows)

    conn.commit()
    print("      Temel veriler yazıldı.")

    # --- 4. İkinci geçiş: Her cümleyi kelimelerle ilişkilendir ---
    print("\n[4/5] Cümleler kelimelerle ilişkilendiriliyor (occurrences tablosu)...")

    # Lemma isim -> id mapping
    lemma_id_map = {row[0]: row[1] for row in conn.execute("SELECT lemma, id FROM lemmas")}

    occurrence_rows = []
    processed = 0

    # Tüm cümleleri tekrar gez
    for idx, (text, source, file) in enumerate(all_sentences):
        tokens = tokenize_and_filter(text)
        if not tokens:
            continue

        # Bu cümleyi veritabanından bul (id'sini al)
        sent_id = conn.execute(
            "SELECT id FROM sentences WHERE text = ? AND source = ? LIMIT 1",
            (text, source)
        ).fetchone()
        if not sent_id:
            continue
        sent_id = sent_id[0]

        seen_lemmas_in_sentence = set()

        for tok in tokens:
            lemma = lemmatize(tok)
            if lemma not in lemma_id_map:
                continue

            lemma_id = lemma_id_map[lemma]

            # Aynı cümlede aynı lemma'yı birden fazla yazmayalım
            if lemma_id in seen_lemmas_in_sentence:
                continue

            occurrence_rows.append((sent_id, lemma_id, tok))
            seen_lemmas_in_sentence.add(lemma_id)

        processed += 1
        if processed % 20000 == 0:
            print(f"      {processed:,} cümle ilişkilendirildi...")

    # Occurrences'ları toplu yaz
    conn.executemany("""
        INSERT INTO occurrences (sentence_id, lemma_id, surface)
        VALUES (?, ?, ?)
    """, occurrence_rows)

    # Lemma'ların sentence_count değerlerini güncelle
    conn.execute("""
        UPDATE lemmas
        SET sentence_count = (
            SELECT COUNT(DISTINCT sentence_id)
            FROM occurrences
            WHERE occurrences.lemma_id = lemmas.id
        )
    """)

    conn.commit()
    print(f"      {len(occurrence_rows):,} occurrence kaydı yazıldı.")

    # --- 5. Post-processing: Kalan bariz çöpleri temizle ---
    print("\n[5/5] Post-processing: Bariz düşük kaliteli lemmalar temizleniyor...")

    # Düşük çeşitlilik + şüpheli pattern
    bad_lemmas = conn.execute("""
        SELECT id, lemma, total_frequency, sentence_count
        FROM lemmas
        WHERE (total_frequency * 1.0 / MAX(sentence_count, 1) > 4.0 AND total_frequency > 80)
           OR length(lemma) <= 5 AND total_frequency > 300 AND sentence_count < 150
           OR lemma IN ('someth','togeth','sometim','chandl','rachei','chandy','wolow','kooth','hofst','priya','rajesh')
    """).fetchall()

    discarded_count = 0
    for lemma_id, lemma, freq, sent_count in bad_lemmas:
        conn.execute("""
            INSERT INTO discarded (word, reason, total_frequency)
            VALUES (?, ?, ?)
        """, (lemma, "low_quality_or_ocr_truncated", freq))

        # occurrences'lardan sil
        conn.execute("DELETE FROM occurrences WHERE lemma_id = ?", (lemma_id,))
        # lemma'yı sil
        conn.execute("DELETE FROM lemmas WHERE id = ?", (lemma_id,))
        discarded_count += 1

    conn.commit()
    print(f"      {discarded_count} düşük kaliteli lemma daha temizlendi.")

    # Final özet
    final_lemmas = conn.execute("SELECT COUNT(*) FROM lemmas").fetchone()[0]
    final_occ = conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0]

    conn.close()

    print(f"\n✅ TAM TEMİZ PIPELINE TAMAMLANDI!")
    print(f"   Veritabanı: {OUTPUT_DB}")
    print(f"   Kalan eşsiz lemma: {final_lemmas:,}")
    print(f"   Kalan occurrence: {final_occ:,}")
    print(f"   Süre: {time.time() - start:.1f} saniye")

    print("\nVeritabanı artık çok daha temiz. İstersen export aşamasına geçebiliriz.")

if __name__ == "__main__":
    build_clean_database()
