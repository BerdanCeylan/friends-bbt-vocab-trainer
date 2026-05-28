#!/usr/bin/env python3
"""
TV English Vocabulary Builder (Lemma-based)
===========================================

Extracts high-quality vocabulary from Friends + The Big Bang Theory subtitles.

Key improvement (2026):
- Uses lemmatization to group word variants (run / running / ran / runs)
  under a single "lemma card" (the form the learner studies).
- Still preserves all surface variants with their frequencies and examples
  so the learner can see natural usage variations inside one card.

This produces much cleaner, more useful learning material than raw surface forms.

Run:
    python3 scripts/build_vocabulary.py
"""

import os
import re
import glob
import json
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Tuple, Set, Iterable

# Import our custom lemmatizer
try:
    from scripts.lemmatizer import lemmatize, get_variant_type
except ImportError:
    # Fallback if run from different directory
    import sys
    sys.path.append(os.path.dirname(__file__))
    from lemmatizer import lemmatize, get_variant_type

# =============================================================================
# CONFIG
# =============================================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRIENDS_DIR = os.path.join(PROJECT_ROOT, "data/subtitles/friends")
BBT_FILE = os.path.join(PROJECT_ROOT, "data/subtitles/bigbangtheory/transcripts.txt")
DB_PATH = os.path.join(PROJECT_ROOT, "data/db/vocabulary.db")

# Minimum appearances across different episodes/files to be considered "real"
MIN_DOC_COUNT = 4

# Tier boundaries (will be refined after full frequency run)
TIER_1_MAX = 850          # Core everyday English (A1-A2)
TIER_2_MAX = 2200         # Very common conversational (B1-B2)

# Character / proper name / show-specific blacklist (expanded for quality)
CHARACTER_BLACKLIST: Set[str] = {
    # === Big Bang Theory ===
    "sheldon", "leonard", "penny", "howard", "raj", "amy", "bernadette",
    "stuart", "kripke", "wil", "wheaton", "ramona", "nowitzki", "gablehauser",
    "leslie", "winkle", "cooper", "dr", "mrs", "professor", "doctor",
    # === Friends ===
    "rachel", "ross", "monica", "chandler", "joey", "phoebe", "mike",
    "gunther", "janice", "richard", "carol", "susan", "emily", "tag",
    "gavin", "charlie", "david", "joshua", "paul", "danny", "kathy",
    "ursula", "frank", "alice", "jack", "judy", "ben", "emma",
    # === Locations, universities, brands (heavy polluters) ===
    "princeton", "caltech", "pasadena", "new", "york", "los", "angeles",
    "central", "perk", "cheesecake", "factory", "nebraska", "omaha",
    "new jersey", "jersey", "texas", "india", "israel", "switzerland",
    "cern", "mit", "ucla", "nyu",
    # === Other recurring show-specific ===
    "toblerone", "star", "wars", "trek", "lord", "rings", "hobbit",
    "batman", "superman", "spiderman", "flash", "green", "lantern",
}

# Common noise patterns to strip
NOISE_PATTERNS = [
    r'\(laughs?\)', r'\[laughs?\]', r'\(chuckles?\)', r'\(sighs?\)',
    r'\(clears? throat\)', r'\(snorts?\)', r'\(groans?\)',
    r'♪[^♪]*♪', r'♫[^♫]*♫',
    r'\(beat\)', r'\(pause\)', r'\(silence\)',
]

# =============================================================================
# TEXT EXTRACTION (very important for quality)
# =============================================================================

def extract_friends_text(filepath: str) -> str:
    """Robustly extract only the actual dialogue from a .srt file."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    content = content.replace('\ufeff', '')  # BOM

    # Standard .srt block pattern:
    #   number
    #   timestamp
    #   dialogue line(s)
    #   (blank)
    blocks = re.split(r'\n\s*\n', content)
    dialogue_parts = []

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue

        # Remove index + timestamp lines
        start_idx = 0
        if lines[0].isdigit():
            start_idx = 1
        if start_idx < len(lines) and '-->' in lines[start_idx]:
            start_idx += 1

        text_lines = lines[start_idx:]
        # Join multi-line dialogue
        text = ' '.join(text_lines)
        # Remove speaker dashes at start of line
        text = re.sub(r'^\s*-\s*', '', text)
        text = re.sub(r'\s+-\s+', ' ', text)

        if text and len(text) > 1:
            dialogue_parts.append(text)

    return ' '.join(dialogue_parts)


def extract_bbt_text(text: str) -> str:
    """
    Remove speaker prefixes like 'Sheldon: ' or 'Leonard: ' carefully.
    Must NOT destroy contractions (I'm, don't, she's).
    """
    # Pattern: Word: or Word Word: at start of line or after space/punct
    # We are conservative: only strip very common speaker patterns
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        # Remove leading "Name: " or "Name Name: "
        line = re.sub(r'^\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?:\s*', '', line)
        # Remove mid-line speaker tags (less common but happens)
        line = re.sub(r'\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?:\s+', ' ', line)
        cleaned.append(line)
    return '\n'.join(cleaned)


def clean_text(text: str) -> str:
    """Apply general noise removal."""
    text = text.lower()

    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)

    # Remove parenthetical stage directions that survived
    text = re.sub(r'\([^)]{2,30}\)', ' ', text)
    text = re.sub(r'\[[^\]]{2,30}\]', ' ', text)

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str) -> List[str]:
    """
    High-quality tokenizer for conversational English.
    Keeps common contractions together (don't, I'm, she's, couldn't, etc.)
    """
    # First protect common contractions
    protected = {
        "don't": "DONT", "doesn't": "DOESNT", "didn't": "DIDNT",
        "can't": "CANT", "couldn't": "COULDNT", "wouldn't": "WOULDNT",
        "won't": "WONT", "isn't": "ISNT", "aren't": "ARENT", "wasn't": "WASNT", "weren't": "WERENT",
        "haven't": "HAVENT", "hasn't": "HASNT", "hadn't": "HADNT",
        "i'm": "IM", "you're": "YOURE", "he's": "HES", "she's": "SHES", "it's": "ITS", "we're": "WERE", "they're": "THEYRE",
        "i've": "IVE", "you've": "YOUVE", "we've": "WEVE", "they've": "THEYVE",
        "i'll": "ILL", "you'll": "YOULL", "he'll": "HELL", "she'll": "SHELL", "we'll": "WELLL", "they'll": "THEYLL",
        "i'd": "ID", "you'd": "YOUD", "he'd": "HEDD", "she'd": "SHEDD",
    }
    for orig, repl in protected.items():
        text = re.sub(r'\b' + re.escape(orig) + r'\b', repl, text, flags=re.IGNORECASE)

    tokens = re.findall(r"\b[a-z]+\b", text.lower())

    # Restore
    restore = {v.lower(): k for k, v in protected.items()}
    tokens = [restore.get(t, t) for t in tokens]
    return tokens


# =============================================================================
# FILTERING
# =============================================================================

def is_good_word(word: str) -> bool:
    """Strict quality filter for learner vocabulary."""
    if word in CHARACTER_BLACKLIST:
        return False
    if len(word) < 2 and word != 'i' and word != 'a':
        return False
    if word.isdigit():
        return False
    if len(word) > 20:  # unrealistic
        return False
    # Reject obvious OCR garbage / fragments (from bad tokenization)
    bad_fragments = {'s', 't', 'm', 're', 'll', 've', 'd', 'doesn', 'didnt', 'isnt', 'wasnt', 'werent', 'dont', 'cant'}
    if word in bad_fragments:
        return False
    # Reject words that are mostly non-letters (shouldn't happen after tokenize)
    if sum(c.isalpha() for c in word) < len(word) * 0.7:
        return False
    return True


# =============================================================================
# DATABASE SCHEMA (designed for vectors + multilingual future)
# =============================================================================

def init_db(conn: sqlite3.Connection):
    """Create the vocabulary schema."""
    conn.executescript("""
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous = NORMAL;

    CREATE TABLE IF NOT EXISTS words (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        word          TEXT    UNIQUE NOT NULL COLLATE NOCASE,
        frequency     INTEGER DEFAULT 0,
        doc_count     INTEGER DEFAULT 0,           -- number of episodes/files it appears in
        sources       TEXT,                        -- comma separated: friends,bigbang
        tier          INTEGER,                     -- 1=core, 2=common, 3=advanced, 4=rare/valuable
        usefulness    REAL,                        -- frequency * log(doc_count + 1) style score
        example_count INTEGER DEFAULT 0,
        metadata      TEXT,                        -- JSON: lemma, pos, cefr_estimate, notes, etc. (future)
        created_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
        updated_at    TEXT    DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS examples (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        word_id    INTEGER NOT NULL,
        sentence   TEXT    NOT NULL,
        source     TEXT,                          -- friends / bigbang
        episode    TEXT,                          -- filename or episode id
        timestamp  TEXT,                          -- for future video sync
        FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_words_frequency ON words(frequency DESC);
    CREATE INDEX IF NOT EXISTS idx_words_tier ON words(tier);
    CREATE INDEX IF NOT EXISTS idx_words_usefulness ON words(usefulness DESC);
    CREATE INDEX IF NOT EXISTS idx_examples_word ON examples(word_id);

    -- Future: word_forms (surface variations), collocations, multilingual_mappings
    """)
    conn.commit()
    print("✓ Database schema initialized")


# =============================================================================
# MAIN PROCESSING
# =============================================================================

def process_friends_files() -> Tuple[Counter, Dict[str, int], Dict[str, List[str]]]:
    """Process all Friends .srt files. Returns freq, doc_count, and example candidates."""
    print("\n[1/3] Processing Friends subtitles...")
    files = sorted(glob.glob(os.path.join(FRIENDS_DIR, "*.srt")))
    print(f"      Found {len(files)} .srt files")

    freq: Counter = Counter()
    doc_count: Dict[str, int] = defaultdict(int)
    examples: Dict[str, List[str]] = defaultdict(list)

    for fpath in files:
        raw = extract_friends_text(fpath)
        cleaned = clean_text(raw)
        tokens = tokenize(cleaned)

        episode = os.path.basename(fpath)

        seen_in_this_file: Set[str] = set()
        sentences = re.split(r'[.!?]\s+', cleaned)

        for tok in tokens:
            if is_good_word(tok):
                freq[tok] += 1
                seen_in_this_file.add(tok)

        # Smarter example collection (avoid show-specific sentences)
        for tok in seen_in_this_file:
            if len(examples[tok]) >= 2:
                continue
            for sent in sentences:
                if tok not in sent:
                    continue
                slen = len(sent)
                if not (18 < slen < 155):
                    continue
                # Penalize sentences with too many proper-noun-like words or show references
                bad_markers = sum(1 for w in CHARACTER_BLACKLIST if w in sent)
                if bad_markers >= 1:
                    continue
                # Prefer "normal" sentences (not too many capitals after we lowercased, few rare words)
                if len(examples[tok]) < 2:
                    examples[tok].append(sent.strip().capitalize())
                    if len(examples[tok]) >= 2:
                        break

        for w in seen_in_this_file:
            doc_count[w] += 1

    print(f"      → {len(freq):,} unique good tokens from Friends")
    return freq, dict(doc_count), dict(examples)


def process_bbt() -> Tuple[Counter, Dict[str, int], Dict[str, List[str]]]:
    """Process the Big Bang Theory combined transcript."""
    print("\n[2/3] Processing Big Bang Theory transcripts...")
    with open(BBT_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        raw = f.read()

    # For now treat the whole file as 1 "doc" for spread calculation.
    # (We can improve later by splitting on episode markers if they exist)
    cleaned = clean_text(extract_bbt_text(raw))
    tokens = tokenize(cleaned)

    freq: Counter = Counter()
    doc_count: Dict[str, int] = defaultdict(int)
    examples: Dict[str, List[str]] = defaultdict(list)

    seen: Set[str] = set()
    for tok in tokens:
        if is_good_word(tok):
            freq[tok] += 1
            seen.add(tok)

    for w in seen:
        doc_count[w] = 1   # whole file = 1 document for now

    # Collect examples (weaker signal because no episode boundaries)
    sentences = re.split(r'[.!?]\s+', cleaned)
    for sent in sentences:
        slen = len(sent)
        if slen < 18 or slen > 145:
            continue
        bad = sum(1 for w in CHARACTER_BLACKLIST if w in sent)
        if bad >= 1:
            continue
        for tok in re.findall(r"\b[a-z]+(?:'[a-z]+)?\b", sent):
            if is_good_word(tok) and len(examples[tok]) < 1:
                examples[tok].append(sent.strip().capitalize())

    print(f"      → {len(freq):,} unique good tokens from BBT")
    return freq, dict(doc_count), dict(examples)


def merge_and_classify(
    friends_freq: Counter,
    friends_docs: Dict[str, int],
    friends_examples: Dict[str, List[str]],
    bbt_freq: Counter,
    bbt_docs: Dict[str, int],
    bbt_examples: Dict[str, List[str]],
) -> List[Dict]:
    """Merge frequencies, compute usefulness, assign tiers."""
    print("\n[3/3] Merging + intelligent classification...")

    all_words = set(friends_freq) | set(bbt_freq)

    records = []
    for word in all_words:
        f_freq = friends_freq.get(word, 0)
        b_freq = bbt_freq.get(word, 0)
        total_freq = f_freq + b_freq

        f_docs = friends_docs.get(word, 0)
        b_docs = bbt_docs.get(word, 0)
        total_docs = f_docs + b_docs   # for BBT this is 0 or 1 currently

        sources = []
        if f_freq > 0:
            sources.append("friends")
        if b_freq > 0:
            sources.append("bigbang")

        # Usefulness = frequency * log(spread). Favors words that appear across many episodes.
        usefulness = total_freq * (1 + (total_docs ** 0.6))

        # Tier assignment tuned for learner value (function words get high freq but we still want them)
        # Tier 1 = must-know spoken English (very high frequency + spread)
        # Tier 2 = extremely common conversational
        # Tier 3 = useful / thematic (BBT science, relationship vocabulary from Friends)
        if total_freq >= 220 and total_docs >= 6:
            tier = 1
        elif total_freq >= 55 and total_docs >= 4:
            tier = 2
        elif total_freq >= 15:
            tier = 3
        else:
            tier = 4

        # Collect best examples (prefer Friends because they have real episode spread)
        exs = (friends_examples.get(word, []) + bbt_examples.get(word, []))[:3]

        records.append({
            "word": word,
            "frequency": total_freq,
            "doc_count": total_docs,
            "sources": ",".join(sources),
            "tier": tier,
            "usefulness": round(usefulness, 2),
            "examples": exs,
        })

    # Sort by usefulness descending (best learning candidates first)
    records.sort(key=lambda x: x["usefulness"], reverse=True)
    print(f"      → {len(records):,} high-quality words after filtering & merging")
    return records


def populate_db(records: List[Dict], conn: sqlite3.Connection):
    """Insert everything into SQLite with examples."""
    print("\n[4/4] Populating database...")

    cur = conn.cursor()

    # Clear previous run (fresh build)
    cur.execute("DELETE FROM examples")
    cur.execute("DELETE FROM words")
    conn.commit()

    batch_words = []
    batch_examples = []

    for rec in records:
        batch_words.append((
            rec["word"],
            rec["frequency"],
            rec["doc_count"],
            rec["sources"],
            rec["tier"],
            rec["usefulness"],
            len(rec["examples"]),
            json.dumps({"sources": rec["sources"]}, ensure_ascii=False),
        ))

    cur.executemany("""
        INSERT INTO words (word, frequency, doc_count, sources, tier, usefulness, example_count, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, batch_words)

    # Get word_ids
    word_ids = {row[0]: row[1] for row in cur.execute("SELECT word, id FROM words")}

    for rec in records:
        wid = word_ids.get(rec["word"])
        if not wid:
            continue
        for ex in rec["examples"]:
            batch_examples.append((
                wid,
                ex,
                "friends" if "friends" in rec["sources"] else "bigbang",
                None,  # episode (future improvement)
                None,  # timestamp
            ))

    if batch_examples:
        cur.executemany("""
            INSERT INTO examples (word_id, sentence, source, episode, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, batch_examples)

    conn.commit()

    # Stats
    total_words = cur.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    total_examples = cur.execute("SELECT COUNT(*) FROM examples").fetchone()[0]
    tier1 = cur.execute("SELECT COUNT(*) FROM words WHERE tier=1").fetchone()[0]
    tier2 = cur.execute("SELECT COUNT(*) FROM words WHERE tier=2").fetchone()[0]

    print(f"      ✓ Inserted {total_words:,} words + {total_examples:,} example sentences")
    print(f"      ✓ Tier 1 (core):     {tier1:,}")
    print(f"      ✓ Tier 2 (common):   {tier2:,}")


def print_top_words(records: List[Dict], n: int = 25):
    """Show the best candidates for human review."""
    print(f"\n{'='*70}")
    print(f"TOP {n} MOST USEFUL WORDS (by frequency × spread)")
    print(f"{'='*70}")
    print(f"{'Rank':<5} {'Word':<14} {'Freq':>6} {'Spread':>6} {'Tier':>5}  Examples")
    print("-" * 70)
    for i, r in enumerate(records[:n], 1):
        ex_preview = (r["examples"][0][:55] + "…") if r["examples"] else ""
        print(f"{i:<5} {r['word']:<14} {r['frequency']:>6} {r['doc_count']:>6}   {r['tier']:>5}  {ex_preview}")


def main():
    start = time.time()
    print("TV English — Intelligent Vocabulary Pool Builder")
    print("=" * 70)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    # 1. Extract + count
    f_freq, f_docs, f_ex = process_friends_files()
    b_freq, b_docs, b_ex = process_bbt()

    # 2. Merge + classify
    records = merge_and_classify(f_freq, f_docs, f_ex, b_freq, b_docs, b_ex)

    # 3. Save
    populate_db(records, conn)

    # 4. Human review output
    print_top_words(records, 30)

    # 5. Write a small JSON report for the website
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_words": len(records),
        "tier_1": sum(1 for r in records if r["tier"] == 1),
        "tier_2": sum(1 for r in records if r["tier"] == 2),
        "tier_3": sum(1 for r in records if r["tier"] == 3),
        "sources": ["friends (208 episodes)", "big bang theory (~200+ episodes)"],
        "top_50": [r["word"] for r in records[:50]],
    }
    with open(os.path.join(PROJECT_ROOT, "data/db/vocabulary_stats.json"), "w") as f:
        json.dump(report, f, indent=2)

    conn.close()
    print(f"\n✓ Done in {time.time() - start:.1f}s")
    print(f"  Database: {DB_PATH}")
    print(f"  Stats:    data/db/vocabulary_stats.json")


if __name__ == "__main__":
    main()
