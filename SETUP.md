# Arkadaşların İçin Kolay Kurulum (Option B)

Bu proje **Option B** mantığıyla çalışıyor:

Herkes altyazıları **senin orijinal verini aldığın aynı public GitHub repolardan** otomatik olarak indiriyor. Böylece kelime kartları, örnek cümleler ve eşleştirmeler büyük oranda aynı kalıyor.

## En Kolay Kurulum (Arkadaşların İçin)

1. Projeyi GitHub'dan klonla veya zip olarak indir:
   ```bash
   git clone <repo-url>
   cd tv-english-vocab
   ```

2. Altyazıları otomatik indir (Friends + BBT):
   ```bash
   python3 scripts/download_subtitles.py --all
   ```

3. Siteyi başlat:
   ```bash
   python3 -m http.server 8000
   ```

4. Tarayıcıda aç: `http://localhost:8000`

## Ne İndiriliyor?

- **Friends**: VocabLevel reposundan (https://github.com/hossein-amirkhani/VocabLevel)
- **Big Bang Theory**: Yulatu reposundan (https://github.com/Yulatu/TBBT-transcripts-wordcloud-NLP)

Bu repolar senin verini oluştururken kullandığın kaynaklarla aynıdır.

## Önemli Not

VocabLevel reposu şu anda en temiz şekilde sadece Season 5'i içeriyor. 
Diğer sezonlar için script sana bilgi verecek ve gerekirse manuel eklemen gerekebilir.

Tam veri kalitesini korumak için ileride "Processed Data Package" da paylaşmayı düşünebiliriz.

## Geri Bildirim

Uygulamayı kullanırken şüpheli kelime, eksik örnek veya hata bulurlarsa:
- Turuncu kelimelere tıklasınlar
- "⚠️ Bu kelimeyi şüpheli listesine ekle" butonuna bassınlar
- Not yazsınlar
- Ana sayfadaki turuncu butondan "GitHub Issue için Kopyala"yı kullansınlar

Bu sayede kolayca geri bildirim toplayabilirsin.
