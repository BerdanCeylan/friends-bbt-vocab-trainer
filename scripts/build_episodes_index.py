#!/usr/bin/env python3
"""
Robust episode index builder for TV English learning site.

Generates:
- data/web/friends_episodes.json   (all detectable Friends .srt, sorted)
- data/web/bbt_episodes.json       (all BBT episodes, correctly sorted S01E01 -> S10E24)

Seasons and episodes inside seasons are always numerically sorted.
Dedupes duplicate rips for same (season, episode) by preferring nice titles.
"""

import os
import json
import re
import glob
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRIENDS_DIR = os.path.join(PROJECT_ROOT, "data/subtitles/friends")
BBT_DIR = os.path.join(PROJECT_ROOT, "data/subtitles/bigbangtheory/episodes")
WEB_DIR = os.path.join(PROJECT_ROOT, "data/web")
os.makedirs(WEB_DIR, exist_ok=True)


def nice_title_from_slug(slug: str) -> str:
    """series-06-episode-23-the-love-spell-potential -> The Love Spell Potential"""
    t = slug.replace('-', ' ').strip()
    # Fix common small words
    t = re.sub(r'\bThe\b', 'The', t)  # already title-ish
    return t.title()


def parse_bbt_filename(filename: str):
    """Handle series-06-episode-23-... and series-6-episode-01-... and series-1-episode-1-..."""
    if not filename.endswith('.txt') or filename == 'transcripts.txt':
        return None
    m = re.search(r'series-0?(\d+)-episode-0?(\d+)-(.+)\.txt$', filename, re.I)
    if not m:
        return None
    season = int(m.group(1))
    episode = int(m.group(2))
    slug = m.group(3)
    title = nice_title_from_slug(slug)
    return {
        "season": season,
        "episode": episode,
        "title": title,
        "filename": filename,
        "filepath": f"data/subtitles/bigbangtheory/episodes/{filename}"
    }


def parse_friends_filename(filename: str):
    """Support multiple common naming conventions for Friends SRTs."""
    base = filename

    # Pattern 1: Friends - [10x01] - The One ... - [group].srt   or [10x17-18]
    m = re.search(r'\[(\d{1,2})x(\d{1,2})(?:-\d+)?\]', base, re.I)
    if m:
        season = int(m.group(1))
        episode = int(m.group(2))
        title_m = re.search(r'\]\s*-\s*(.+?)\s*(?:-\s*\[|\.srt|$)', base)
        title = title_m.group(1).strip() if title_m else f"Episode {episode}"
        return {"season": season, "episode": episode, "title": title}

    # Pattern 2: Friends - 6x01 - The One After Vegas.en.srt   (no brackets)
    m = re.search(r'(?<!\w)(\d{1,2})x(\d{1,2})(?:-\d+)?(?!\w)', base, re.I)
    if m:
        season = int(m.group(1))
        episode = int(m.group(2))
        title_m = re.search(r'\d{1,2}x\d{1,2}(?:-\d+)?\s*-\s*(.+?)\s*(\.en)?\.srt$', base)
        title = title_m.group(1).strip() if title_m else f"Episode {episode}"
        return {"season": season, "episode": episode, "title": title}

    # Pattern 3: friends.s01e05.720p.bluray...srt  or friends.s10e17-18....
    m = re.search(r'[sS](\d{1,2})[eE](\d{1,2})(?:-\d+)?', base)
    if m:
        season = int(m.group(1))
        episode = int(m.group(2))
        # No reliable title in these filenames
        title = f"Episode {episode}"
        return {"season": season, "episode": episode, "title": title}

    return None


def build_friends_index():
    files = glob.glob(os.path.join(FRIENDS_DIR, "*.srt"))
    candidates = []

    for full in files:
        base = os.path.basename(full)
        parsed = parse_friends_filename(base)
        if not parsed:
            continue
        parsed["filename"] = base
        parsed["filepath"] = f"data/subtitles/friends/{base}"
        candidates.append(parsed)

    # Dedup by (season, episode) — prefer entries that have a real "The One..." style title
    best = {}
    for p in candidates:
        key = (p["season"], p["episode"])
        existing = best.get(key)
        if not existing:
            best[key] = p
            continue
        # Prefer longer/more descriptive title
        if len(p["title"]) > len(existing["title"]) or "The One" in p["title"]:
            best[key] = p

    # Group + sort
    seasons = defaultdict(list)
    for p in best.values():
        seasons[str(p["season"])].append(p)

    for s in seasons:
        seasons[s].sort(key=lambda x: x["episode"])

    output = {
        "total_episodes": len(best),
        "seasons": dict(sorted(seasons.items(), key=lambda kv: int(kv[0])))
    }
    return output


def build_bbt_index():
    files = [f for f in os.listdir(BBT_DIR) if f.endswith('.txt')]
    episodes = []

    for f in files:
        parsed = parse_bbt_filename(f)
        if parsed:
            episodes.append(parsed)

    # Group
    seasons = defaultdict(list)
    for ep in episodes:
        seasons[str(ep["season"])].append(ep)

    # Sort seasons and episodes inside
    for s in seasons:
        seasons[s].sort(key=lambda x: x["episode"])

    output = {
        "total_episodes": len(episodes),
        "seasons": dict(sorted(seasons.items(), key=lambda kv: int(kv[0])))
    }
    return output


def main():
    print("Building Friends episode index...")
    friends = build_friends_index()
    with open(os.path.join(WEB_DIR, "friends_episodes.json"), "w", encoding="utf-8") as f:
        json.dump(friends, f, indent=2, ensure_ascii=False)
    print(f"  Friends: {friends['total_episodes']} episodes across {len(friends['seasons'])} seasons")

    print("Building BBT episode index...")
    bbt = build_bbt_index()
    with open(os.path.join(WEB_DIR, "bbt_episodes.json"), "w", encoding="utf-8") as f:
        json.dump(bbt, f, indent=2, ensure_ascii=False)
    print(f"  BBT: {bbt['total_episodes']} episodes across {len(bbt['seasons'])} seasons")

    print("\nDone. JSON files written to data/web/")
    print("Seasons (Friends):", sorted([int(k) for k in friends["seasons"].keys()]))
    print("Seasons (BBT):    ", sorted([int(k) for k in bbt["seasons"].keys()]))


if __name__ == "__main__":
    main()
