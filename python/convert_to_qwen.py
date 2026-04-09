#!/usr/bin/env python3
"""
Converts JSON/JSONL dataset to Qwen fine-tuning format (JSONL).
Place convert_to_qwen.py in the same folder as your JSON/JSONL files and run:
    python convert_to_qwen.py

Output: qwen_finetune.jsonl — ready for Qwen fine-tuning.
"""

import glob
import json
import os
import sys

SYSTEM_PROMPT = (
    "You are an expert Python programmer. "
    "When given a programming problem, reason through it step by step, "
    "then provide a complete, working solution."
)


def format_record(record: dict):
    problem = record.get("problem", "").strip()
    reasoning = record.get("reasoning", "").strip()
    code = record.get("code", "").strip()

    if not problem or not code:
        return None

    if reasoning:
        assistant_content = (
            f"<think>\n{reasoning}\n</think>\n\n"
            f"```python\n{code}\n```"
        )
    else:
        assistant_content = f"```python\n{code}\n```"

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": problem},
            {"role": "assistant", "content": assistant_content},
        ]
    }


def load_file(input_path: str):
    """Reads both JSON array and JSONL format."""
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # Try as JSON array
    if content.startswith("["):
        try:
            records = json.loads(content)
            return records
        except json.JSONDecodeError:
            pass

    # Try as JSONL (line by line)
    for i, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"  Warning: line {i} skipped — {e}")

    return records


def convert_file(input_path: str, out_file):
    print(f"Processing: {os.path.basename(input_path)}")

    try:
        data = load_file(input_path)
    except Exception as e:
        print(f"  Error: {e}")
        return 0, 0

    if not data:
        print("  Warning: file is empty or could not be read.")
        return 0, 0

    ok = 0
    skipped = 0

    for record in data:
        formatted = format_record(record)
        if formatted is None:
            skipped += 1
            continue
        out_file.write(json.dumps(formatted, ensure_ascii=False) + "\n")
        ok += 1

    print(f"  -> {ok} records converted, {skipped} skipped (missing data)")
    return ok, skipped


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Find both .json and .jsonl files
    json_files = (
        glob.glob(os.path.join(script_dir, "*.json")) +
        glob.glob(os.path.join(script_dir, "*.jsonl"))
    )

    # Filter out already-converted output files
    json_files = [
        f for f in json_files
        if "qwen_finetune" not in os.path.basename(f)
    ]

    if not json_files:
        print(f"No .json or .jsonl files found in folder:\n  {script_dir}")
        sys.exit(0)

    output_path = os.path.join(script_dir, "qwen_finetune.jsonl")

    print(f"Found {len(json_files)} files in: {script_dir}\n")

    total_ok = 0
    total_skipped = 0

    with open(output_path, "w", encoding="utf-8") as out_file:
        for json_path in sorted(json_files):
            ok, skipped = convert_file(json_path, out_file)
            total_ok += ok
            total_skipped += skipped

    size_mb = os.path.getsize(output_path) / 1024 / 1024

    print(f"\nOutput  : {output_path}")
    print(f"Total   : {total_ok} records")
    print(f"Skipped : {total_skipped}")
    print(f"Size    : {size_mb:.2f} MB")
    print("\nReady for Qwen fine-tuning!")


if __name__ == "__main__":
    main()
