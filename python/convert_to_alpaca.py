#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

IGNORE_NAMES = ["alpaca_finetune", "qwen_finetune", "alpaca_merged", "filtered_output"]

def clean_text(text):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(text))

def format_record(record):
    if "instruction" in record and "output" in record:
        alpaca = {
            "instruction": clean_text(record.get("instruction", "").strip()),
            "input":       clean_text(record.get("input", "").strip()),
            "output":      clean_text(record.get("output", "").strip()),
        }
        if not alpaca["instruction"] or not alpaca["output"]:
            return None
        return alpaca
    elif "problem" in record and "code" in record:
        problem   = clean_text(record.get("problem", "").strip())
        code      = clean_text(record.get("code", "").strip())
        reasoning = clean_text(record.get("reasoning", "").strip())
        if not problem or not code:
            return None
        output = f"<think>\n{reasoning}\n</think>\n\n```python\n{code}\n```" if reasoning else f"```python\n{code}\n```"
        return {"instruction": problem, "input": "", "output": output}
    elif "code" in record:
        code = clean_text(record.get("code", "").strip())
        lang = record.get("language", "python").lower()
        if not code or len(code) < 50:
            return None
        return {
            "instruction": "Explain what this code does and how it works.",
            "input": f"```{lang}\n{code}\n```",
            "output": f"This {lang} code implements the following functionality:\n\n```{lang}\n{code}\n```"
        }
    return None

def load_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read().strip()
    if content.startswith("["):
        try:
            return json.loads(content)
        except:
            pass
    if content.startswith("{"):
        try:
            return [json.loads(content)]
        except:
            pass
    records = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except:
            pass
    return records

def convert_file(path):
    print(f"Apstrada: {os.path.basename(path)}")
    try:
        data = load_file(path)
    except Exception as e:
        print(f"  Kludas: {e}")
        return [], 0
    results = []
    skipped = 0
    for record in data:
        formatted = format_record(record)
        if formatted is None:
            skipped += 1
        else:
            results.append(formatted)
    print(f"  -> {len(results)} konverteti, {skipped} izlaisti")
    return results, skipped

def main():
    parser = argparse.ArgumentParser(description="Konverte uz Alpaca formatu")
    parser.add_argument("--folder", default=None, help="Darba mape")
    args, _ = parser.parse_known_args()
    script_dir = args.folder if args.folder else os.path.dirname(os.path.abspath(__file__))
    print(f"Mape: {script_dir}")

    all_files = (
        glob.glob(os.path.join(script_dir, "*.json")) +
        glob.glob(os.path.join(script_dir, "*.jsonl"))
    )
    source_files = [f for f in all_files if not any(n in os.path.basename(f) for n in IGNORE_NAMES)]

    if not source_files:
        print(f"Nav atrasts neviens fails mape: {script_dir}")
        sys.exit(0)

    print(f"Atrasti {len(source_files)} faili")
    all_records = []
    total_skipped = 0
    for path in sorted(source_files):
        records, skipped = convert_file(path)
        all_records.extend(records)
        total_skipped += skipped

    output_path = os.path.join(script_dir, "alpaca_finetune.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"\nRezultats : {output_path}")
    print(f"Kopaa     : {len(all_records)} ieraksti")
    print(f"Izlaisti  : {total_skipped}")
    print(f"Izmers    : {size_mb:.2f} MB")
    print("Gatavs!")

if __name__ == "__main__":
    main()