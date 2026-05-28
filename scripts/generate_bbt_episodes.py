#!/usr/bin/env python3
"""
Generate structured episode metadata for all BBT transcripts.
Creates data/web/bbt_episodes.json with season, episode, title, and file path.
"""

import os
import json
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPISODES_DIR = os.path.join(PROJECT_ROOT, "data/subtitles/bigbangtheory/episodes")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data/web/bbt_episodes.json")

def parse_filename(filename):
    """Parse filename like 'series-06-episode-23-the-love-spell-potential.txt'"""
    match = re.match(r'series-(\d+)-episode-(\d+)-(.+)\.txt', filename)
    if not match:
        return None
    
    season = int(match.group(1))
    episode = int(match.group(2))
    title_slug = match.group(3)
    
    # Convert slug to nice title
    title = title_slug.replace('-', ' ').title()
    
    return {
        "season": season,
        "episode": episode,
        "title": title,
        "filename": filename,
        "filepath": f"data/subtitles/bigbangtheory/episodes/{filename}"
    }

def main():
    files = [f for f in os.listdir(EPISODES_DIR) if f.endswith('.txt')]
    episodes = []
    
    for f in sorted(files):
        parsed = parse_filename(f)
        if parsed:
            episodes.append(parsed)
    
    # Group by season for nicer structure
    seasons = {}
    for ep in episodes:
        s = ep["season"]
        if s not in seasons:
            seasons[s] = []
        seasons[s].append(ep)
    
    output = {
        "total_episodes": len(episodes),
        "seasons": seasons
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {OUTPUT_FILE}")
    print(f"Total episodes: {len(episodes)}")
    print(f"Seasons covered: {sorted(seasons.keys())}")

if __name__ == "__main__":
    print("DEPRECATED: Use scripts/build_episodes_index.py instead (produces correct sort + both shows).")
    main()