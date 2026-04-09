#!/usr/bin/env python3
"""
Splits all JSONL files in the current folder into parts < 2 MB (default).
Usage:
    python split_jsonl.py
    python split_jsonl.py --max-mb 5
    python split_jsonl.py --max-mb 1 --output-dir ./parts
"""

import argparse
import os
import sys
import glob


def split_jsonl(input_path: str, max_mb: float, output_dir: str):
    max_bytes = int(max_mb * 1024 * 1024)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    os.makedirs(output_dir, exist_ok=True)

    part_index = 1
    current_size = 0
    current_lines = 0
    out_file = None

    def open_new_part():
        nonlocal part_index, current_size, current_lines, out_file
        if out_file:
            out_file.close()
            print(f"  -> Saved: {out_file.name}  ({current_size / 1024 / 1024:.2f} MB, {current_lines} lines)")
        out_path = os.path.join(output_dir, f"{base_name}_part{part_index:04d}.jsonl")
        out_file = open(out_path, "w", encoding="utf-8")
        part_index += 1
        current_size = 0
        current_lines = 0

    total_lines = 0
    skipped_lines = 0

    open_new_part()

    with open(input_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line if raw_line.endswith("\n") else raw_line + "\n"
            line_size = len(line.encode("utf-8"))

            if line_size > max_bytes:
                skipped_lines += 1
                print(f"  Warning: line {total_lines + 1} exceeds {max_mb} MB — skipped.")
                continue

            if current_size + line_size > max_bytes:
                open_new_part()

            out_file.write(line)
            current_size += line_size
            current_lines += 1
            total_lines += 1

    if out_file:
        out_file.close()
        if current_lines > 0:
            print(f"  -> Saved: {out_file.name}  ({current_size / 1024 / 1024:.2f} MB, {current_lines} lines)")

    print(f"   Total {total_lines} lines => {part_index - 1} parts.\n")
    if skipped_lines:
        print(f"   Skipped {skipped_lines} lines (too large).")


def main():
    parser = argparse.ArgumentParser(description="Splits JSONL files into smaller parts.")
    parser.add_argument("--folder", default=None, help="Working folder")
    parser.add_argument("--max-mb", type=float, default=2.0,
                        help="Max size MB per part (default: 2.0)")
    parser.add_argument("--output-dir", default=None,
                        help="Output folder (default: same folder as file)")
    args = parser.parse_args()

    # Find JSONL files in the script directory
    script_dir = args.folder if hasattr(args,'folder') and args.folder else os.path.dirname(os.path.abspath(__file__))
    jsonl_files = glob.glob(os.path.join(script_dir, "*.jsonl"))

    # Filter out already-split parts (to avoid reprocessing)
    jsonl_files = [f for f in jsonl_files if "_part" not in os.path.basename(f)]

    if not jsonl_files:
        print(f"No .jsonl files found in folder: {script_dir}")
        sys.exit(0)

    print(f"Found {len(jsonl_files)} JSONL files in: {script_dir}")
    print(f"Max part size: {args.max_mb} MB\n")

    for jsonl_path in jsonl_files:
        print(f"Processing: {os.path.basename(jsonl_path)}")
        out_dir = args.output_dir if args.output_dir else os.path.dirname(jsonl_path)
        split_jsonl(jsonl_path, args.max_mb, out_dir)

    print("All done!")


if __name__ == "__main__":
    main()
