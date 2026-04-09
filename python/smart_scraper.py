#!/usr/bin/env python3
"""
Smart Dataset Scraper — downloads JSON/JSONL/Parquet data from HuggingFace,
GitHub and other sources with anti-blocking techniques.

Usage:
    python smart_scraper.py --url "https://..." --output ./data
    python smart_scraper.py --url "hf://username/dataset" --output ./data
    python smart_scraper.py --url "https://huggingface.co/datasets/..." --output ./data --hf-token hf_xxx

Requirements:
    pip install requests huggingface_hub datasets tqdm
"""

import argparse
import json
import os
import sys
import time
import random
import re
import urllib.request
import urllib.error
from pathlib import Path

# --- Anti-blocking User-Agent rotation ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
]

def random_ua():
    return random.choice(USER_AGENTS)

def random_delay(min_s=0.5, max_s=2.0):
    time.sleep(random.uniform(min_s, max_s))

# ────────────────────────────────────────────
# Detect URL source type
# ────────────────────────────────────────────
def detect_source(url: str) -> str:
    if url.startswith("hf://") or "huggingface.co/datasets" in url:
        return "huggingface"
    if "github.com" in url and "/raw/" in url:
        return "github_raw"
    if "github.com" in url:
        return "github"
    if url.endswith(".jsonl") or url.endswith(".json") or url.endswith(".parquet"):
        return "direct"
    if "datasets-server.huggingface.co" in url:
        return "hf_api"
    return "direct"

# ────────────────────────────────────────────
# HuggingFace datasets download
# ────────────────────────────────────────────
def download_huggingface(url: str, output_dir: str, hf_token: str = "", split: str = "train", max_rows: int = 0):
    try:
        from datasets import load_dataset
    except ImportError:
        print("Error: pip install datasets huggingface_hub")
        sys.exit(1)

    dataset_id = url
    if "huggingface.co/datasets/" in url:
        dataset_id = url.split("huggingface.co/datasets/")[1].rstrip("/")
        dataset_id = dataset_id.split("/resolve")[0].split("?")[0]
        parts = dataset_id.split("/")
        dataset_id = "/".join(parts[:2])

    print(f"📦 HuggingFace dataset: {dataset_id}")
    print(f"📂 Split: {split}")
    print(f"⏳ Downloading...")

    kwargs = {}
    if hf_token:
        kwargs["token"] = hf_token

    try:
        ds = load_dataset(dataset_id, split=split, **kwargs)
    except Exception as e:
        print(f"Error with full dataset, trying streaming: {e}")
        try:
            ds = load_dataset(dataset_id, split=split, streaming=True, **kwargs)
            records = []
            for i, row in enumerate(ds):
                if max_rows > 0 and i >= max_rows:
                    break
                records.append(dict(row))
                if (i+1) % 1000 == 0:
                    print(f"  Downloaded: {i+1} records...")
            safe_name = dataset_id.replace("/", "_")
            out_path = os.path.join(output_dir, f"{safe_name}_{split}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2, default=str)
            print(f"✅ Saved: {out_path} ({len(records)} records)")
            return
        except Exception as e2:
            print(f"Error: {e2}")
            sys.exit(1)

    if max_rows > 0:
        ds = ds.select(range(min(max_rows, len(ds))))

    records = [dict(row) for row in ds]
    safe_name = dataset_id.replace("/", "_")
    out_path = os.path.join(output_dir, f"{safe_name}_{split}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"✅ Saved: {out_path}")
    print(f"   Records : {len(records)}")
    print(f"   Size    : {size_mb:.2f} MB")

# ────────────────────────────────────────────
# Direct file download with retry + UA rotation
# ────────────────────────────────────────────
def download_direct(url: str, output_dir: str, hf_token: str = "", retries: int = 3):
    filename = url.split("/")[-1].split("?")[0]
    if not filename:
        filename = "downloaded_file.json"
    out_path = os.path.join(output_dir, filename)

    print(f"📥 Direct download: {filename}")
    print(f"   URL: {url[:80]}...")

    headers = {
        "User-Agent": random_ua(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://huggingface.co/",
    }
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    for attempt in range(retries):
        try:
            headers["User-Agent"] = random_ua()
            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=60) as response:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 1024 * 1024  # 1MB

                with open(out_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded / total * 100
                            mb = downloaded / 1024 / 1024
                            print(f"\r  Downloading: {mb:.1f} MB ({pct:.0f}%)", end="", flush=True)

            print()
            size_mb = os.path.getsize(out_path) / 1024 / 1024
            print(f"✅ Saved: {out_path} ({size_mb:.2f} MB)")
            return out_path

        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"  Error 401: --hf-token required for authentication!")
                sys.exit(1)
            elif e.code == 403:
                print(f"  Error 403: Access denied. Trying different UA...")
            elif e.code == 429:
                wait = 5 * (attempt + 1)
                print(f"  Rate limit! Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  HTTP error {e.code}: {e.reason}")

        except Exception as e:
            print(f"  Error (attempt {attempt+1}): {e}")

        if attempt < retries - 1:
            random_delay(2, 5)

    print("❌ Failed to download after all attempts.")
    sys.exit(1)

# ────────────────────────────────────────────
# GitHub download
# ────────────────────────────────────────────
def download_github(url: str, output_dir: str):
    raw_url = url
    if "github.com" in url and "/blob/" in url:
        raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    elif "github.com" in url and "/tree/" in url:
        print("ℹ️  GitHub folder — downloading as ZIP...")
        zip_url = re.sub(r'/tree/[^/]+', '', url) + "/archive/refs/heads/main.zip"
        return download_direct(zip_url, output_dir)

    return download_direct(raw_url, output_dir)

# ────────────────────────────────────────────
# HF Datasets API
# ────────────────────────────────────────────
def download_hf_api(url: str, output_dir: str, hf_token: str = "", max_rows: int = 1000):
    print(f"📡 HuggingFace API: {url[:60]}...")

    headers = {"User-Agent": random_ua()}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    api_url = url
    if "limit=" not in url:
        sep = "&" if "?" in url else "?"
        api_url = f"{url}{sep}length={max_rows}&offset=0"

    # FIX: added full error handling — previously crashed with unhandled exception
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP error {e.code}: {e.reason}")
        if e.code == 401:
            print("   --hf-token required for authentication!")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ Connection error: {e.reason}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid API response (not JSON): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

    rows = data.get("rows", [])
    records = [row.get("row", row) for row in rows]

    out_path = os.path.join(output_dir, "hf_api_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"✅ Saved: {out_path} ({len(records)} records, {size_mb:.2f} MB)")

# ────────────────────────────────────────────
# Main function
# ────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Smart Dataset Scraper")
    parser.add_argument("--url",       required=True,  help="URL or HuggingFace dataset ID")
    parser.add_argument("--output",    default=".",    help="Output folder")
    parser.add_argument("--hf-token",  default="",     help="HuggingFace API token (hf_xxx)")
    parser.add_argument("--split",     default="train",help="HF dataset split (train/test/validation)")
    parser.add_argument("--max-rows",  type=int, default=0, help="Max records (0=all)")
    parser.add_argument("--retries",   type=int, default=3, help="Number of retry attempts")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"  SMART SCRAPER")
    print(f"{'='*50}")
    print(f"  URL    : {args.url[:60]}...")
    print(f"  Output : {args.output}")
    if args.max_rows > 0:
        print(f"  Max    : {args.max_rows} records")
    print(f"{'='*50}\n")

    source = detect_source(args.url)
    print(f"🔍 Source: {source}\n")

    if source == "huggingface":
        download_huggingface(args.url, args.output, args.hf_token, args.split, args.max_rows)
    elif source == "hf_api":
        download_hf_api(args.url, args.output, args.hf_token, args.max_rows or 1000)
    elif source in ("github", "github_raw"):
        download_github(args.url, args.output)
    else:
        download_direct(args.url, args.output, args.hf_token, args.retries)

    print(f"\n{'='*50}")
    print(f"  Done! Files saved to: {args.output}")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
