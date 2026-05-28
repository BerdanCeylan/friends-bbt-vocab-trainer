#!/usr/bin/env python3
"""
analyze_unlinked_words.py

Bu script, bir bölüm veya birden fazla bölümdeki "eşleşmeyen" (unlinked) kelimeleri bulur.
Amacı: Kelime haritamızda (lemmas.json) olmayan ama sık geçen kelimeleri tespit etmek.

Kullanım örnekleri:
    python scripts/analyze_unlinked_words.py --episode "data/subtitles/friends/Friends - 1x01 - The One Where Monica Gets a Roommate - [arsenaloyal].srt"
    python scripts/analyze_unlinked_words.py --top 50
    python scripts/analyze_unlinked_words.py --friends --limit 5   # ilk 5 Friends bölümü
"""

import os
import json
import re
import argparse
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LEMMAS_PATH = PROJECT_ROOT / "data/web/lemmas.json"
FRIENDS_DIR = PROJECT_ROOT / "data/subtitles/friends"
BBT_DIR = PROJECT_ROOT / "data/subtitles/bigbangtheory/episodes"


def clean_word(text: str) -> str:
    """Geliştirilmiş temizleme: tırnak kirliliğini de yakalar (''grab → grab)"""
    try:
        from lemmatizer import clean_surface
        return clean_surface(text)
    except ImportError:
        # Fallback (eski davranış + quote strip)
        s = re.sub(r"^['\"‘’“”«»]+|['\"‘’“”«»]+$", "", text)
        return re.sub(r"[^a-zA-ZçğıöşüÇĞİÖŞÜ']", "", s).lower()


def load_variant_map():
    """lemmas.json'dan surface → lemma haritası oluşturur"""
    with open(LEMMAS_PATH, "r", encoding="utf-8") as f:
        lemmas = json.load(f)

    variant_map = {}
    for lem in lemmas:
        lemma_name = lem["lemma"]
        variant_map[lemma_name] = lemma_name
        for v in lem.get("variants", []):
            surf = v["surface"].lower()
            if surf not in variant_map:
                variant_map[surf] = lemma_name
    return variant_map


def extract_words_from_text(text: str):
    """Metinden kelimeleri temizleyip listeler"""
    # Python re \p{} desteklemediği için daha geniş ama pratik bir pattern
    words = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9']+", text)
    cleaned = []
    for w in words:
        c = clean_word(w)
        if len(c) >= 1:
            cleaned.append(c)
    return cleaned


def analyze_file(filepath: Path, variant_map: dict):
    """Tek bir dosya için unlinked kelimeleri sayar"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
    except Exception as e:
        print(f"[HATA] Dosya okunamadı: {filepath} → {e}")
        return Counter(), 0

    words = extract_words_from_text(raw)

    linked = []
    unlinked = []

    for w in words:
        if w in variant_map:
            linked.append(w)
        else:
            unlinked.append(w)

    return Counter(unlinked), len(words)


def main():
    parser = argparse.ArgumentParser(description="Eşleşmeyen kelimeleri analiz et")
    parser.add_argument("--episode", help="Tek bir dosyanın yolu")
    parser.add_argument("--top", type=int, default=150, help="Gösterilecek en sık unlinked kelime sayısı")
    parser.add_argument("--friends", action="store_true", help="Friends klasöründeki bölümleri tara")
    parser.add_argument("--bbt", action="store_true", help="Big Bang Theory klasöründeki bölümleri tara")
    parser.add_argument("--limit", type=int, default=None, help="Kaç bölüm taransın (sıralı). Belirtilmezse hepsini tarar.")
    args = parser.parse_args()

    print("Kelime haritası yükleniyor...")
    variant_map = load_variant_map()
    print(f"  {len(variant_map):,} yüzey form yüklendi.\n")

    all_unlinked = Counter()
    total_words = 0
    files_scanned = 0

    targets = []

    if args.episode:
        targets.append(Path(args.episode))

    if args.friends:
        files = sorted(FRIENDS_DIR.glob("*.srt"))
        if args.limit:
            files = files[:args.limit]
        targets.extend(files)

    if args.bbt:
        files = sorted(BBT_DIR.glob("*.txt"))
        if args.limit:
            files = files[:args.limit]
        targets.extend(files)

    if not targets:
        print("Hiç dosya belirtilmedi. Örnek kullanım için --help bak.")
        print("Hızlı deneme: --friends --limit 2")
        return

    for fp in targets:
        print(f"Taranıyor: {fp.name}")
        unlinked_counter, word_count = analyze_file(fp, variant_map)
        all_unlinked += unlinked_counter
        total_words += word_count
        files_scanned += 1

    print(f"\n{'='*60}")
    print(f"Taranan dosya: {files_scanned}")
    print(f"Toplam kelime (temizlenmiş): {total_words:,}")
    print(f"Eşleşmeyen kelime türü (unique): {len(all_unlinked):,}")
    print(f"Eşleşmeyen toplam geçiş: {sum(all_unlinked.values()):,}")
    print(f"{'='*60}\n")

    top_list = all_unlinked.most_common(args.top)
    print(f"En sık {len(top_list)} eşleşmeyen kelime:\n")
    for word, freq in top_list:
        print(f"  {freq:6d}  →  {word}")

    # JSON olarak kaydet (ileride kullanmak için)
    report = {
        "total_files_scanned": files_scanned,
        "total_cleaned_words": total_words,
        "unique_unlinked_words": len(all_unlinked),
        "total_unlinked_occurrences": sum(all_unlinked.values()),
        "top_unlinked": [{"word": w, "frequency": f} for w, f in top_list]
    }

    output_path = PROJECT_ROOT / "data/web/unlinked_words_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Rapor kaydedildi: {output_path}")
    print("\n--- Özet ---")
    print(f"Toplam {len(all_unlinked):,} farklı kelime sistemdeki kelime haritasında (lemmas.json) yok.")
    print("Bunların en sık geçenlerini lemmas.json'a ekleyerek kapsama oranını ciddi şekilde artırabiliriz.")


if __name__ == "__main__":
    main()
