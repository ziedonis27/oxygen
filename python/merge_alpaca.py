#!/usr/bin/env python3
"""
Merges multiple Alpaca JSON files into one, skipping duplicates.
Place merge_alpaca.py in the same folder as your Alpaca JSON files and run:
    python merge_alpaca.py

Output: alpaca_merged.json
"""

import glob
import json
import os
import sys


def load_json(path: str):
    print(f"Reading: {os.path.basename(path)}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            print(f"  -> {len(data)} records")
            return data
        else:
            print("  Warning: file is not an array — skipped")
            return []
    except Exception as e:
        print(f"  Error: {e}")
        return []


def main():
    import argparse as _ap
    _p = _ap.ArgumentParser()
    _p.add_argument("--folder", default=None)
    _args, _ = _p.parse_known_args()
    script_dir = _args.folder if _args.folder else os.path.dirname(os.path.abspath(__file__))

    # Find all .json files except already merged
    json_files = glob.glob(os.path.join(script_dir, "*.json"))
    json_files = [
        f for f in json_files
        if "alpaca_merged" not in os.path.basename(f)
    ]

    if not json_files:
        print(f"No .json files found in folder:\n  {script_dir}")
        sys.exit(0)

    print(f"Found {len(json_files)} JSON files:\n")

    all_records = []
    total_loaded = 0

    for path in sorted(json_files):
        records = load_json(path)
        all_records.extend(records)
        total_loaded += len(records)

    print(f"\nTotal loaded   : {total_loaded} records")

    # Skip duplicates by 'instruction' field
    seen = set()
    unique_records = []
    duplicates = 0

    for rec in all_records:
        key = rec.get("instruction", "").strip()
        if not key:
            continue
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique_records.append(rec)

    print(f"Duplicates     : {duplicates}")
    print(f"Unique         : {len(unique_records)}")

    # Save result
    output_path = os.path.join(script_dir, "alpaca_merged.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique_records, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"\nOutput : {output_path}")
    print(f"Size   : {size_mb:.2f} MB")
    print("\nDone! Upload alpaca_merged.json to Colab.")


if __name__ == "__main__":
    main()
