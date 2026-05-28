#!/usr/bin/env python3
"""
TV English Vocab - Data Downloader (Option B friendly)

This script helps users get the data needed to run the app.

For the BEST experience (the exact word cards + examples you built):
→ Download the pre-processed data package.

For advanced users who want to re-process everything:
→ Also download raw subtitles from public sources.

Usage:
    python3 scripts/download_data.py --processed          # Recommended
    python3 scripts/download_data.py --raw-subtitles
    python3 scripts/download_data.py --all
"""

import os
import sys
import urllib.request
import urllib.parse
import zipfile
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_WEB_DIR = PROJECT_ROOT / "data/web"
SUBTITLES_DIR = PROJECT_ROOT / "data/subtitles"

def download_file(url: str, dest: Path, desc=""):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"  ✓ Already exists: {dest.name}")
        return True

    print(f"  Downloading {desc or dest.name}...", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TV-English-Vocab/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        print("done")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

def download_and_extract_zip(url: str, extract_to: Path, desc=""):
    """Download a zip and extract it."""
    temp_zip = PROJECT_ROOT / "temp_data.zip"
    if not download_file(url, temp_zip, desc):
        return False

    print(f"  Extracting {desc}...")
    try:
        with zipfile.ZipFile(temp_zip, 'r') as z:
            z.extractall(extract_to)
        print("  ✓ Extracted successfully")
        temp_zip.unlink()
        return True
    except Exception as e:
        print(f"  Extraction failed: {e}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed", action="store_true", help="Download pre-built data (recommended for normal use)")
    parser.add_argument("--raw-subtitles", action="store_true", help="Download raw subtitle files from public sources")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    print("=== TV English Vocab Data Downloader ===\n")

    if args.processed or args.all:
        print("--- Pre-processed Data (Best Experience) ---")
        print("This gives you the exact word cards, examples, and matching you built.\n")

        # TODO: User will replace these URLs with real direct download links
        # (Google Drive direct link, GitHub Releases direct asset URL, etc.)
        processed_url = "https://example.com/your-data-web.zip"   # <-- CHANGE THIS

        print("⚠️  You need to host your processed data somewhere and put the direct link here.")
        print("   For now this is a placeholder.\n")

        if "example.com" in processed_url:
            print("Please edit this script and replace the URL with your actual data package link.")
            print("Recommended places to host: GitHub Releases, Google Drive (make sure direct download works), Mega, etc.\n")
        else:
            success = download_and_extract_zip(processed_url, PROJECT_ROOT, "processed data")
            if success:
                print("✓ Pre-processed data ready. You can now run the site.\n")

    if args.raw_subtitles or args.all:
        print("--- Raw Subtitles (Advanced / Re-processing) ---")
        print("Only needed if you want to re-generate the vocabulary yourself.\n")
        # Call the logic from download_subtitles.py or improve here
        print("For raw subtitles, use: python3 scripts/download_subtitles.py --friends --bbt")
        print("(This part is still being improved)\n")

    if not (args.processed or args.raw_subtitles or args.all):
        print("Recommended usage for normal users:")
        print("  python3 scripts/download_data.py --processed")
        print("\nFor people who want to experiment with their own subtitles:")
        print("  python3 scripts/download_data.py --all")

if __name__ == "__main__":
    main()