#!/usr/bin/env python3
"""
TV English Vocab - Reproducible Subtitle Downloader (Option B)

Downloads subtitles from the exact same public GitHub repositories 
the original data was built from, so that everyone gets very similar files.

Confirmed sources (provided by user):
- Big Bang Theory → https://github.com/Yulatu/TBBT-transcripts-wordcloud-NLP/tree/master/txts
- Friends         → https://github.com/BerdanCeylan/ingilizce/tree/main/friends_srt

This approach helps keep the pre-built word cards, examples, and matching consistent.

Usage:
    python3 scripts/download_subtitles.py --friends
    python3 scripts/download_subtitles.py --bbt
    python3 scripts/download_subtitles.py --all
"""

import os
import urllib.request
import urllib.parse
import time
import argparse
import zipfile
import shutil
from pathlib import Path
from io import BytesIO

PROJECT_ROOT = Path(__file__).parent.parent
FRIENDS_DIR = PROJECT_ROOT / "data/subtitles/friends"
BBT_DIR = PROJECT_ROOT / "data/subtitles/bigbangtheory"

FRIENDS_DIR.mkdir(parents=True, exist_ok=True)
BBT_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dest_path: Path, desc: str = "") -> bool:
    if dest_path.exists():
        print(f"  ✓ Already exists: {dest_path.name}")
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {desc or dest_path.name} ...", end=" ", flush=True)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TV-English-Vocab/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        print("done")
        time.sleep(0.35)
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False


def download_zip_and_extract(url: str, extract_to: Path, desc: str = ""):
    """Download a zip and extract specific parts."""
    print(f"  Downloading {desc} ...", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TV-English-Vocab/1.0"})
        with urllib.request.urlopen(req, timeout=120) as response:
            data = response.read()

        with zipfile.ZipFile(BytesIO(data)) as z:
            z.extractall(extract_to)
        print("done")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False


# =============================================================================
# FRIENDS - From user's confirmed sources
# =============================================================================
def download_friends():
    print("\n" + "="*60)
    print("FRIENDS - Downloading from confirmed public sources")
    print("="*60)

    # Primary source provided by user
    print("\nSource 1: https://github.com/BerdanCeylan/ingilizce/tree/main/friends_srt")

    zip_url = "https://github.com/BerdanCeylan/ingilizce/archive/refs/heads/main.zip"
    temp_extract = PROJECT_ROOT / "temp_friends_extract"

    print("Downloading the repo and extracting friends_srt folder...")
    if download_zip_and_extract(zip_url, temp_extract, "BerdanCeylan/ingilizce repo"):
        source_folder = temp_extract / "ingilizce-main" / "friends_srt"

        if source_folder.exists():
            count = 0
            for srt_file in source_folder.glob("*.srt"):
                dest = FRIENDS_DIR / srt_file.name
                try:
                    shutil.copy2(srt_file, dest)
                    count += 1
                except Exception as e:
                    print(f"  Failed to copy {srt_file.name}: {e}")

            print(f"  ✓ Copied {count} Friends .srt files from BerdanCeylan repo.")
        else:
            print("  Could not find friends_srt folder in the downloaded repo.")

        # Cleanup
        if temp_extract.exists():
            shutil.rmtree(temp_extract, ignore_errors=True)
    else:
        print("Failed to download from BerdanCeylan repo.")

    # Secondary source (VocabLevel) - kept for S05 quality if needed
    print("\nSource 2 (optional - VocabLevel for Season 5):")
    print("If you want higher quality S05, you can also run the old logic or add manually.")


# =============================================================================
# BIG BANG THEORY - Yulatu repo (confirmed source)
# =============================================================================
def download_bbt():
    print("\n" + "="*60)
    print("BIG BANG THEORY - Downloading from confirmed source")
    print("="*60)
    print("Source: https://github.com/Yulatu/TBBT-transcripts-wordcloud-NLP/tree/master/txts\n")

    zip_url = "https://github.com/Yulatu/TBBT-transcripts-wordcloud-NLP/archive/refs/heads/master.zip"
    temp_extract = PROJECT_ROOT / "temp_bbt_extract"

    print("Downloading repo and extracting /txts folder...")
    if not download_zip_and_extract(zip_url, temp_extract, "BBT repo"):
        print("Failed to download BBT repo.")
        return

    # Exact path the user confirmed
    source_txts = temp_extract / "TBBT-transcripts-wordcloud-NLP-master" / "txts"
    target = BBT_DIR / "transcripts.txt"

    if source_txts.exists() and any(source_txts.iterdir()):
        print("Combining episode transcripts into single transcripts.txt (matching current app format)...")

        all_lines = []
        for txt_file in sorted(source_txts.glob("*.txt")):
            try:
                with open(txt_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                    if content:
                        # Add a clear separator so it's still usable
                        all_lines.append(f"\n\n=== {txt_file.stem} ===\n")
                        all_lines.append(content)
            except Exception as e:
                print(f"  Skipped {txt_file.name}: {e}")

        with open(target, "w", encoding="utf-8") as out:
            out.write("\n".join(all_lines))

        print(f"  ✓ Combined transcripts saved to {target}")
    else:
        print("  Could not find /txts folder or it was empty.")

    # Cleanup temp
    if temp_extract.exists():
        shutil.rmtree(temp_extract, ignore_errors=True)

    print("\nBBT ready at: data/subtitles/bigbangtheory/transcripts.txt")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--friends", action="store_true")
    parser.add_argument("--bbt", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    print("TV English Vocab - Downloading from Original Public Sources (Option B)")
    print("BBT source (confirmed):  https://github.com/Yulatu/TBBT-transcripts-wordcloud-NLP/tree/master/txts")
    print("Friends source (confirmed): https://github.com/BerdanCeylan/ingilizce/tree/main/friends_srt\n")

    if args.all or args.friends:
        download_friends()

    if args.all or args.bbt:
        download_bbt()

    if not (args.friends or args.bbt or args.all):
        print("Usage:")
        print("  python3 scripts/download_subtitles.py --friends")
        print("  python3 scripts/download_subtitles.py --bbt")
        print("  python3 scripts/download_subtitles.py --all")

    print("\nAfter downloading subtitles, run the site with:")
    print("  python -m http.server 8000")


if __name__ == "__main__":
    main()