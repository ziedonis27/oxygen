#!/usr/bin/env python3
"""
Konverte JSON/JSONL datasetu Alpaca fine-tuning formātā.
Ievieto convert_to_alpaca.py tajā pašā mapē kur JSON/JSONL faili un palaid:
    python convert_to_alpaca.py

Atbalsta:
  - JSON masīvs:  [{...}, {...}]
  - JSONL:        viena rinda = viens ieraksts
  - Formāts 1:    problem / code / reasoning  (Python dataset)
  - Formāts 2:    instruction / input / output (jau Alpaca)

Rezultāts: alpaca_finetune.json — gatavs fine-tuning vajadzībām.
"""

import glob
import json
import os
import sys
import re

# Faili kurus ignorēt (izvades faili)
IGNORE_NAMES = ["alpaca_finetune", "qwen_finetune"]


def clean_text(text: str) -> str:
    """Notīra kontrolrakstzīmes kas sabojā JSON validāciju."""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


def format_record(record: dict):
    """Pārveido vienu ierakstu Alpaca formātā. Atbalsta divus ievades formātus."""

    # Formāts 2: jau Alpaca formātā (instruction/input/output)
    if "instruction" in record and "output" in record:
        alpaca = {
            "instruction": clean_text(record.get("instruction", "").strip()),
            "input":       clean_text(record.get("input", "").strip()),
            "output":      clean_text(record.get("output", "").strip()),
        }
        if not alpaca["instruction"] or not alpaca["output"]:
            return None

    # Formāts 1: Python dataset (problem/code/reasoning)
    elif "problem" in record and "code" in record:
        problem   = clean_text(record.get("problem", "").strip())
        reasoning = clean_text(record.get("reasoning", "").strip())
        code      = clean_text(record.get("code", "").strip())

        if not problem or not code:
            return None

        if reasoning:
            output = f"<think>\n{reasoning}\n</think>\n\n```python\n{code}\n```"
        else:
            output = f"```python\n{code}\n```"

        alpaca = {
            "instruction": problem,
            "input":       "",
            "output":      output,
        }

    else:
        return None  # Nezināms formāts — izlaiž

    # Pārbauda vai ieraksts ir derīgs JSON
    try:
        json.dumps(alpaca, ensure_ascii=False)
    except Exception as e:
        print(f"  Bridinajums: ieraksts izlaists — {e}")
        return None

    return alpaca


def load_file(input_path: str):
    """Nolasa gan JSON masīvu, gan JSONL formātu."""
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # JSON masīvs [...]
    if content.startswith("["):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

    # Viens JSON objekts {...}
    if content.startswith("{"):
        try:
            return [json.loads(content)]
        except json.JSONDecodeError:
            pass

    # JSONL — rinda pēc rindas
    records = []
    for i, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"  Bridinajums: rinda {i} izlaista — {e}")
    return records


def convert_file(input_path: str):
    print(f"Apstrada: {os.path.basename(input_path)}")

    try:
        data = load_file(input_path)
    except Exception as e:
        print(f"  Kludas: {e}")
        return [], 0

    if not data:
        print("  Bridinajums: fails ir tukss.")
        return [], 0

    results = []
    skipped = 0

    for record in data:
        formatted = format_record(record)
        if formatted is None:
            skipped += 1
            continue
        results.append(formatted)

    print(f"  -> {len(results)} ieraksti konverteti, {skipped} izlaisti")
    return results, skipped


def validate_output(output_path: str):
    """Pārbauda vai izvades fails ir derīgs JSON."""
    print("\nValde izvades failu...")
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        problems = []
        for i, rec in enumerate(data):
            try:
                json.dumps(rec, ensure_ascii=False)
            except Exception as e:
                problems.append((i, str(e)))
        if problems:
            print(f"  Atrasti {len(problems)} problematiski ieraksti!")
            for idx, err in problems[:5]:
                print(f"  Indekss {idx}: {err}")
        else:
            print(f"  Visi {len(data)} ieraksti ir derigi!")
    except Exception as e:
        print(f"  Validacijas kludas: {e}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Meklē gan .json, gan .jsonl
    all_files = (
        glob.glob(os.path.join(script_dir, "*.json")) +
        glob.glob(os.path.join(script_dir, "*.jsonl"))
    )

    # Izfiltrē izvades failus
    source_files = [
        f for f in all_files
        if not any(name in os.path.basename(f) for name in IGNORE_NAMES)
    ]

    if not source_files:
        print(f"Nav atrasts neviens .json vai .jsonl fails mape:\n  {script_dir}")
        sys.exit(0)

    print(f"Atrasti {len(source_files)} faili mape: {script_dir}")
    for f in sorted(source_files):
        size_mb = os.path.getsize(f) / 1024 / 1024
        print(f"  {os.path.basename(f)} ({size_mb:.1f} MB)")
    print()

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

    validate_output(output_path)
    print("\nGatavs! Augshupieladejiet alpaca_finetune.json uz Colab.")


if __name__ == "__main__":
    main()