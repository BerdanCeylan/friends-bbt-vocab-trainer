# TV English Vocab

Interactive English vocabulary trainer built from real dialogue in **Friends** and **The Big Bang Theory**.

The goal is to learn natural, high-frequency English vocabulary the way native speakers actually use it — through TV dialogue.

## ⚠️ Important: About the Data

This repository does **not** contain any subtitle files or full processed datasets.

- Raw subtitles (Friends .srt and BBT transcripts) are copyrighted material and are **not** included.
- The large generated files (`lemmas.json`, episode samples, etc.) are also not committed.

### How to use the app

1. Clone this repo
2. Put your own subtitle files in `data/subtitles/` (following the expected structure)
3. Run the Python processing scripts to generate the web data
4. Serve the site locally (`python -m http.server`)

See the [Processing Guide](#processing-your-own-data) below.

## Features

- **Episode Reader** (`scripts.html`): Browse real episodes, click any word to see context + mark it
- **Smart Filtering**: Function words (blue), character names (purple), and real vocabulary (orange)
- **Suspect Words Feedback System**: Mark weird/unlinked words with notes → export clean JSON for contributors
- **Study Mode** (`review.html`): Your personal "Bilmiyorum" list with practice quiz + English/Turkish meaning support
- **Vocabulary Explorer** (`index.html`): Tiered word list with usefulness scores

## Quick Start (for using the app)

```bash
git clone https://github.com/yourusername/tv-english-vocab.git
cd tv-english-vocab

# Install Python dependencies (if processing data)
pip install -r requirements.txt   # (create this later if needed)

# Run locally
python -m http.server 8000
```

Then open: http://localhost:8000

## How to Send Feedback (Most Important Part)

The best way to help improve the vocabulary quality is through the **Şüpheli Kelimeler** (Suspect Words) system:

1. Open an episode in the **Senaryoları İncele** page
2. Click on words that look wrong, are names, OCR errors, or shouldn't be there
3. In the word card, click **⚠️ Bu kelimeyi şüpheli listesine ekle**
4. Add a short note (e.g. "character name", "OCR error", "should be 'laser' not 'las'")
5. Go to the main page → click the orange **⚠️ Şüpheli Kelimeler** button
6. Click **JSON İndir** and attach the file when opening a GitHub issue

This feedback loop is how we continuously clean function words, character names, and junk.

## Processing Your Own Data

If you have your own subtitle files and want to build the full dataset:

```bash
# 1. Place your subtitles in the correct folders
# 2. Run the processing pipeline (example)
python scripts/build_episodes_index.py
python scripts/enrich_definitions_smart.py --tiers 1,2
```

Detailed instructions will be added in `docs/PROCESSING.md`.

## Tech Stack

- Pure static frontend (HTML + vanilla JS + CSS)
- Python scripts for data processing and enrichment
- localStorage for user progress and feedback
- Free Dictionary API for on-demand definitions

## Contributing

We especially welcome contributions in these areas:

- **Vocabulary quality** (the #1 goal) → Use the suspect words system
- Improving the lemmatizer and cleaning rules
- UI/UX improvements for the study experience
- Adding more shows in the future

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

The code is MIT licensed.  
All subtitle content remains the property of its respective copyright holders.

---

**Made for serious English learners who want natural vocabulary from real TV dialogue.**