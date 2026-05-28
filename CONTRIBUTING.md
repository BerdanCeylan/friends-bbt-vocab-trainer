# Contributing to TV English Vocab

Thank you for wanting to help! The main goal of this project is building the **highest quality** English vocabulary list possible from real TV dialogue.

## The Most Valuable Contribution: Vocabulary Feedback

The biggest ongoing work is cleaning the word list:
- Removing character names
- Removing function words that pollute the list
- Fixing OCR / parsing errors
- Handling quote pollution from subtitles (`''grab`, `hero''`, etc.)

### How to Send High-Quality Feedback

1. Open `scripts.html` and load an episode.
2. While reading, click any word that looks suspicious.
3. In the popup, click the **⚠️ Bu kelimeyi şüpheli listesine ekle** button.
4. Write a short, clear note:
   - "character name - Ross"
   - "OCR error: carefuiiy → carefully"
   - "should be linked to 'laser', not standalone 'las'"
   - "quote pollution from SRT"
5. When you're done with a session, go to the main page and click the big orange **⚠️ Şüpheli Kelimeler** button.
6. Review your notes, then click **JSON İndir**.
7. Open a new issue on GitHub and attach the JSON file (or paste the content).

This system is specifically designed so we can quickly turn user reports into improvements in `function_words.json`, `character_names.json`, and `junk_words.json`.

## Other Ways to Contribute

- Improve the lemmatizer (`scripts/lemmatizer.py`)
- Make the quote/punctuation cleaning more robust
- Add better Turkish definition support
- UI improvements in the study mode (`review.html`)
- Documentation

## Running the Project Locally

```bash
git clone https://github.com/yourusername/tv-english-vocab.git
cd tv-english-vocab
python -m http.server 8000
```

Then open http://localhost:8000

## Processing Data (Advanced)

If you want to regenerate the vocabulary from subtitles:

1. Place your own subtitle files in `data/subtitles/`
2. Run the build scripts in `scripts/`

**Note**: We do not distribute subtitle files due to copyright.

## Code Style

- Keep the frontend as clean vanilla JS (no heavy frameworks)
- Python scripts should be well commented
- New features should consider the offline/local-first nature of the project

## Questions?

Open an issue or start a discussion. Feedback on the vocabulary quality is always welcome, even without code changes.

Thanks for helping make natural English vocabulary learning better!
