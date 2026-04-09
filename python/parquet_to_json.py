#!/usr/bin/env python3
"""
Converts all Parquet files in the current folder to JSON.
Usage:
    python parquet_to_json.py
    python parquet_to_json.py --output-dir ./results
    python parquet_to_json.py --indent 2   (formatted JSON, default: 2)

Required libraries (install once):
    pip install pandas pyarrow
"""

import argparse
import os
import sys
import glob
import json

try:
    import pandas as pd
except ImportError:
    print("Missing library 'pandas'. Install: pip install pandas pyarrow")
    sys.exit(1)


def convert_parquet(input_path: str, output_dir: str, indent: int):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    out_path = os.path.join(output_dir, f"{base_name}.json")

    print(f"Processing: {os.path.basename(input_path)}")

    try:
        df = pd.read_parquet(input_path)
    except Exception as e:
        print(f"  Error: could not read file — {e}")
        return

    # Convert to JSON list (each record = object)
    records = df.to_dict(orient="records")

    # Convert datetime types to string (JSON doesn't support datetime natively)
    def default_serializer(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return str(obj)

    os.makedirs(output_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=indent, default=default_serializer)

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  -> Saved: {out_path}  ({len(records)} records, {size_mb:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Convert Parquet files to JSON.")
    parser.add_argument("--folder", default=None, help="Working folder")
    parser.add_argument("--output-dir", default=None,
                        help="Output folder (default: same folder as parquet file)")
    parser.add_argument("--indent", type=int, default=2,
                        help="JSON indent (default: 2, 0 = compact)")
    args = parser.parse_args()

    script_dir = args.folder if args.folder else os.path.dirname(os.path.abspath(__file__))
    parquet_files = glob.glob(os.path.join(script_dir, "*.parquet"))

    if not parquet_files:
        print(f"No .parquet files found in folder: {script_dir}")
        sys.exit(0)

    print(f"Found {len(parquet_files)} Parquet files in: {script_dir}\n")

    for parquet_path in parquet_files:
        out_dir = args.output_dir if args.output_dir else os.path.dirname(parquet_path)
        convert_parquet(parquet_path, out_dir, args.indent)

    print("\nAll done!")


if __name__ == "__main__":
    main()
