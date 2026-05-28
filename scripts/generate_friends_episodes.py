#!/usr/bin/env python3
"""
Friends .srt dosyalarından sezon-bölüm yapılı episode metadata oluşturur.
"""

import os
import json
import re
import glob

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRIENDS_DIR = os.path.join(PROJECT_ROOT, "data/subtitles/friends")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data/web/friends_episodes.json")

def parse_friends_filename(filename):
    """'Friends - [10x01] - The One After Joey and Rachel Kiss - [arsenaloyal].srt' formatını parse eder"""
    match = re.search(r'\[(\d+)x(\d+)\]\s*-\s*(.+?)\s*(?:-\s*\[|\.srt)', filename)
    if not match:
        return None
    
    season = int(match.group(1))
    episode = int(match.group(2))
    title = match.group(3).strip()
    
    return {
        "season": season,
        "episode": episode,
        "title": title,
        "filename": filename,
        "filepath": f"data/subtitles/friends/{filename}"
    }

def main():
    files = glob.glob(os.path.join(FRIENDS_DIR, "*.srt"))
    episodes = []
    
    for f in files:
        filename = os.path.basename(f)
        parsed = parse_friends_filename(filename)
        if parsed:
            episodes.append(parsed)
    
    # Sezonlara göre grupla
    seasons = {}
    for ep in episodes:
        s = str(ep["season"])
        if s not in seasons:
            seasons[s] = []
        seasons[s].append(ep)
    
    # Her sezon içindeki bölümleri sırala
    for s in seasons:
        seasons[s] = sorted(seasons[s], key=lambda x: x["episode"])
    
    output = {
        "total_episodes": len(episodes),
        "seasons": seasons
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {OUTPUT_FILE}")
    print(f"Total episodes: {len(episodes)}")
    print(f"Seasons: {sorted([int(k) for k in seasons.keys()])}")

if __name__ == "__main__":
    print("DEPRECATED: Use scripts/build_episodes_index.py instead (full 208 eps + correct numeric ordering).")
    main()