#!/usr/bin/env python3
"""
Download Friends Season 5 English subtitles from the public VocabLevel GitHub repo.
These are the missing files needed for complete corpus + episode browser.

Source: https://github.com/hossein-amirkhani/VocabLevel/tree/master/Subtitles/Friends5
"""

import os
import urllib.request
import urllib.parse
import time

DEST_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data/subtitles/friends"
)
os.makedirs(DEST_DIR, exist_ok=True)

# Files from the repo (as of latest visible tree)
FILES = [
    "Friends - 5x01 - The One After Ross Says Rachel.en.sub",
    "Friends - 5x02 - The One With All The Kissing.en.sub",
    "Friends - 5x03 - The One Hundredth.en.sub",
    "Friends - 5x04 - The One Where Phoebe Hates PBS.en.sub",
    "Friends - 5x05 - The One With The Kips.en.sub",
    "Friends - 5x06 - The One With The Yeti.en.sub",
    "Friends - 5x07 - The One Where Ross Moves In.en.sub",
    "Friends - 5x08 - The One With The Thanksgiving Flashbacks.en.sub",
    "Friends - 5x09 - The One With Ross's Sandwich.en.sub",
    "Friends - 5x10 - The One With The Inappropriate Sister.en.sub",
    "Friends - 5x11 - The One With All The Resolutions.en.sub",
    "Friends - 5x12 - The One With Chandler's Work Laugh.en.sub",
    "Friends - 5x13 - The One With Joey's Bag.en.sub",
    "Friends - 5x14 - The One Where Everybody Finds Out.en.sub",
    "Friends - 5x15 - The One With The Girl Who Hits Joey.en.sub",
    "Friends - 5x16 - The One With The Cop.en.sub",
    "Friends - 5x17 - The One With Rachel's Inadvertent Kiss.en.sub",
    "Friends - 5x18 - The One Where Rachel Smokes.en.sub",
    "Friends - 5x19 - The One Where Ross Can't Flirt.en.sub",
    "Friends - 5x20 - The One With The Ride Along.en.sub",
    "Friends - 5x21 - The One With The Ball.en.sub",
    "Friends - 5x22 - The One With Joey's Big Break.en.sub",
    "Friends - 5x23 - The One In Vegas (1).en.sub",
]

BASE_RAW = "https://raw.githubusercontent.com/hossein-amirkhani/VocabLevel/master/Subtitles/Friends5/"

def download_one(name):
    url = BASE_RAW + urllib.parse.quote(name)
    dest_name = name.replace(".sub", ".srt")  # rename for consistency with our parser + existing files
    dest_path = os.path.join(DEST_DIR, dest_name)

    if os.path.exists(dest_path):
        print(f"Already exists: {dest_name}")
        return True

    print(f"Downloading {name} ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        print(f"  ✓ Saved as {dest_name}")
        time.sleep(0.4)  # be nice to GitHub
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

def main():
    print(f"Destination: {DEST_DIR}")
    print(f"Will download {len(FILES)} Season 5 episodes from VocabLevel (public educational repo)")
    print()

    success = 0
    for f in FILES:
        if download_one(f):
            success += 1

    print()
    print(f"Done. {success}/{len(FILES)} files downloaded/verified.")
    print("Now run:  python3 scripts/build_episodes_index.py")

if __name__ == "__main__":
    main()
