#!/usr/bin/env python3
"""
Export episode / script data for the "Senaryoları İncele" feature.
Groups sentences by file (episode) from vocabulary_v2.db.
"""

import sqlite3
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data/db/vocabulary_v2.db")
WEB_DIR = os.path.join(PROJECT_ROOT, "data/web")
os.makedirs(WEB_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("Exporting episode/script data...")

# Get distinct files with sentence counts
episodes = []
for row in conn.execute("""
    SELECT file, source, COUNT(*) as sentence_count
    FROM sentences
    GROUP BY file, source
    ORDER BY source, sentence_count DESC
"""):
    episodes.append({
        "file": row["file"],
        "source": row["source"],
        "sentence_count": row["sentence_count"]
    })

with open(os.path.join(WEB_DIR, "episodes.json"), "w", encoding="utf-8") as f:
    json.dump(episodes, f, indent=2, ensure_ascii=False)

print(f"  ✓ episodes.json ({len(episodes)} episodes)")

# For a few popular episodes, pre-export some sentences for quick loading
# (In a real app we'd fetch dynamically, but for static site we pre-load a few)
popular_files = [e["file"] for e in episodes[:6]]  # top 6

episode_samples = {}
for file in popular_files:
    sentences = []
    for row in conn.execute("""
        SELECT text FROM sentences 
        WHERE file = ? 
        ORDER BY id 
        LIMIT 40
    """, (file,)):
        sentences.append(row["text"])
    
    episode_samples[file] = sentences

with open(os.path.join(WEB_DIR, "episode_samples.json"), "w", encoding="utf-8") as f:
    json.dump(episode_samples, f, indent=2, ensure_ascii=False)

print(f"  ✓ episode_samples.json (samples for {len(popular_files)} episodes)")

conn.close()
print("\n✅ Episode data exported for script browser.")