"""
Lightweight English Lemmatizer for TV subtitle data.

Designed specifically for conversational/spoken English from TV shows.
Prioritizes practical grouping for language learners over perfect linguistic accuracy.

Features:
- Handles regular inflections (ing, ed, s, es, er, est, ly)
- Large set of irregular verbs common in daily speech
- Maps spoken reductions (gonna, wanna, gotta, etc.) to their lemmas
- Keeps important spoken forms visible as variants
"""

import re
from typing import Dict, List, Tuple

# =============================================================================
# TEXT CLEANING UTILITIES
# =============================================================================

QUOTE_CHARS = r'''['"‘’“”«»„‚‛‹›]'''

def strip_outer_quotes(text: str) -> str:
    """
    Baştaki ve sondaki tırnak / apostrophe varyasyonlarını temizler.
    SRT dosyalarında sık görülen ''word'' ve 'word' gibi kirlilikleri düzeltir.
    """
    if not text:
        return text
    # Birden fazla tırnak karakterini ('' gibi) de yakala
    return re.sub(rf'^({QUOTE_CHARS}|'')+|({QUOTE_CHARS}|'')+$', '', text)


def clean_surface(text: str) -> str:
    """
    Yüzey formu (surface) için kapsamlı temizlik.
    - Dış tırnakları at
    - Sadece harf + iç apostrof bırak
    - Küçük harfe çevir
    Bu fonksiyon hem lemmatizer'da hem analiz scriptlerinde kullanılmalı.
    """
    if not text:
        return ""
    s = strip_outer_quotes(text)
    # Sadece harf + apostrof tut (contractions için)
    s = re.sub(r"[^a-zA-ZçğıöşüÇĞİÖŞÜ']", "", s)
    return s.lower()

# =============================================================================
# IRREGULAR VERBS (very common in Friends + Big Bang Theory)
# =============================================================================

IRREGULAR_VERBS: Dict[str, str] = {
    # be
    "am": "be", "is": "be", "are": "be", "was": "be", "were": "be", "been": "be", "being": "be",
    # go
    "went": "go", "gone": "go", "going": "go", "goes": "go",
    # get
    "got": "get", "gotten": "get", "getting": "get", "gets": "get",
    # make
    "made": "make", "making": "make", "makes": "make",
    # take
    "took": "take", "taken": "take", "taking": "take", "takes": "take",
    # come
    "came": "come", "coming": "come", "comes": "come",
    # say
    "said": "say", "saying": "say", "says": "say",
    # know
    "knew": "know", "known": "know", "knowing": "know", "knows": "know",
    # think
    "thought": "think", "thinking": "think", "thinks": "think",
    # see
    "saw": "see", "seen": "see", "seeing": "see", "sees": "see",
    # give
    "gave": "give", "given": "give", "giving": "give", "gives": "give",
    # find
    "found": "find", "finding": "find", "finds": "find",
    # tell
    "told": "tell", "telling": "tell", "tells": "tell",
    # feel
    "felt": "feel", "feeling": "feel", "feels": "feel",
    # put
    "putting": "put", "puts": "put",
    # let
    "letting": "let", "lets": "let",
    # begin
    "began": "begin", "begun": "begin", "beginning": "begin", "begins": "begin",
    # bring
    "brought": "bring", "bringing": "bring", "brings": "bring",
    # buy
    "bought": "buy", "buying": "buy", "buys": "buy",
    # choose
    "chose": "choose", "chosen": "choose", "choosing": "choose", "chooses": "choose",
    # do
    "did": "do", "done": "do", "doing": "do", "does": "do",
    # drink
    "drank": "drink", "drunk": "drink", "drinking": "drink", "drinks": "drink",
    # drive
    "drove": "drive", "driven": "drive", "driving": "drive", "drives": "drive",
    # eat
    "ate": "eat", "eaten": "eat", "eating": "eat", "eats": "eat",
    # fall
    "fell": "fall", "fallen": "fall", "falling": "fall", "falls": "fall",
    # fly
    "flew": "fly", "flown": "fly", "flying": "fly", "flies": "fly",
    # forget
    "forgot": "forget", "forgotten": "forget", "forgetting": "forget", "forgets": "forget",
    # get (already above)
    # have
    "had": "have", "having": "have", "has": "have",
    # hear
    "heard": "hear", "hearing": "hear", "hears": "hear",
    # hold
    "held": "hold", "holding": "hold", "holds": "hold",
    # keep
    "kept": "keep", "keeping": "keep", "keeps": "keep",
    # leave
    "left": "leave", "leaving": "leave", "leaves": "leave",
    # lose
    "lost": "lose", "losing": "lose", "loses": "lose",
    # mean
    "meant": "mean", "meaning": "mean", "means": "mean",
    # meet
    "met": "meet", "meeting": "meet", "meets": "meet",
    # pay
    "paid": "pay", "paying": "pay", "pays": "pay",
    # read
    "reading": "read", "reads": "read",
    # run
    "ran": "run", "running": "run", "runs": "run",
    # send
    "sent": "send", "sending": "send", "sends": "send",
    # show
    "showed": "show", "shown": "show", "showing": "show", "shows": "show",
    # sit
    "sat": "sit", "sitting": "sit", "sits": "sit",
    # sleep
    "slept": "sleep", "sleeping": "sleep", "sleeps": "sleep",
    # speak
    "spoke": "speak", "spoken": "speak", "speaking": "speak", "speaks": "speak",
    # stand
    "stood": "stand", "standing": "stand", "stands": "stand",
    # swim
    "swam": "swim", "swum": "swim", "swimming": "swim", "swims": "swim",
    # take (already)
    # teach
    "taught": "teach", "teaching": "teach", "teaches": "teach",
    # tell (already)
    # think (already)
    # wear
    "wore": "wear", "worn": "wear", "wearing": "wear", "wears": "wear",
    # win
    "won": "win", "winning": "win", "wins": "win",
    # write
    "wrote": "write", "written": "write", "writing": "write", "writes": "write",
    # become
    "became": "become", "becoming": "become", "becomes": "become",
    # break
    "broke": "break", "broken": "break", "breaking": "break", "breaks": "break",
}

# Spoken reductions / very common informal forms
SPOKEN_REDUCTIONS: Dict[str, str] = {
    "gonna": "go",
    "gotta": "get",
    "wanna": "want",
    "kinda": "kind",
    "sorta": "sort",
    "outta": "out",
    "hafta": "have",
    "tryna": "try",
    "dunno": "know",
    "lemme": "let",
    "gimme": "give",
    "whatcha": "what",
    "ya": "you",           # careful with this one
    "ain't": "be",         # or "have" depending on context, we map to be for simplicity
    "ain": "be",
}

# Common adjective/adverb rules
ADJ_SUFFIXES = ["er", "est", "ly"]

# Irregular nouns (very common)
IRREGULAR_NOUNS: Dict[str, str] = {
    "men": "man",
    "women": "woman",
    "children": "child",
    "feet": "foot",
    "teeth": "tooth",
    "mice": "mouse",
    "geese": "goose",
    "people": "person",   # debatable but useful for learners
}

# Adjective irregulars
IRREGULAR_ADJECTIVES: Dict[str, str] = {
    "better": "good",
    "best": "good",
    "worse": "bad",
    "worst": "bad",
    "more": "much",       # also "many"
    "most": "much",
}

# =============================================================================
# LEMMATIZER
# =============================================================================

def lemmatize(word: str) -> str:
    """
    Return the lemma (base form) of a word.
    Designed for spoken English from TV subtitles.
    """
    if not word or len(word) < 2:
        return word

    # Önce dış tırnak ve junk karakterleri temizle (SRT quote pollution için kritik)
    w = clean_surface(word)

    # 1. Irregular adjectives (better → good, etc.)
    if w in IRREGULAR_ADJECTIVES:
        return IRREGULAR_ADJECTIVES[w]

    # 2. Irregular nouns
    if w in IRREGULAR_NOUNS:
        return IRREGULAR_NOUNS[w]

    # 3. Direct irregular verb match (highest priority)
    if w in IRREGULAR_VERBS:
        return IRREGULAR_VERBS[w]

    # 4. Spoken reductions
    if w in SPOKEN_REDUCTIONS:
        return SPOKEN_REDUCTIONS[w]

    # 3. Handle common contractions we may have missed
    if w.endswith("'s") and len(w) > 3:
        base = w[:-2]
        if base in {"he", "she", "it", "that", "what", "who", "there"}:
            return "be"  # he's → be
        return base

    if w.endswith("'re"):
        return "be"
    if w.endswith("'ve"):
        return "have"
    if w.endswith("'d"):
        return w[:-2]  # would/ had → base
    if w.endswith("'ll"):
        return w[:-3]  # will → base

    # 4. Regular verb forms
    if w.endswith("ing") and len(w) > 5:
        base = w[:-3]
        # handle doubling: running → run, stopping → stop
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        # e-drop: making → make, taking → take
        if base.endswith("e"):
            return base
        # common vowel changes
        if base.endswith("i"):
            return base[:-1] + "y"
        return base

    if w.endswith("ed") and len(w) > 4:
        base = w[:-2]
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        if base.endswith("i"):
            return base[:-1] + "y"
        return base

    # 5. 3rd person singular + plural nouns
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4:
        base = w[:-2]
        if base.endswith(("s", "x", "z", "ch", "sh")):
            return base
        return base
    if w.endswith("s") and len(w) > 3:
        # Don't strip if it's already short or special
        if not w.endswith(("ss", "us", "is")):
            return w[:-1]

    # 6. Adjective comparative/superlative
    if w.endswith("est") and len(w) > 5:
        base = w[:-3]
        if base.endswith("i"):
            base = base[:-1] + "y"
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        return base

    if w.endswith("er") and len(w) > 4:
        base = w[:-2]
        if base.endswith("i"):
            base = base[:-1] + "y"
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        return base

    # 7. Adverbs
    if w.endswith("ly") and len(w) > 4:
        base = w[:-2]
        if base.endswith("i"):
            base = base[:-1] + "y"
        return base

    return w


def get_variant_type(surface: str, lemma: str) -> str:
    """Classify the relationship between surface and lemma (for UI display)."""
    if surface == lemma:
        return "base"
    if surface in SPOKEN_REDUCTIONS:
        return "spoken"
    if surface.endswith(("ing", "in'")):
        return "progressive"
    if surface.endswith(("ed", "d")):
        return "past"
    if surface.endswith(("s", "es")):
        return "3rd/person/plural"
    if surface.endswith(("er", "est")):
        return "comparative"
    return "other"


if __name__ == "__main__":
    # Quick test
    test_words = [
        "running", "ran", "runs", "gonna", "gotta", "wanna",
        "happier", "happiest", "beautifully", "said", "went",
        "children", "better", "best", "thinking", "thinks"
    ]
    for w in test_words:
        lemma = lemmatize(w)
        print(f"{w:12} → {lemma}")
