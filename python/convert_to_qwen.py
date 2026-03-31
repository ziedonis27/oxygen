#!/usr/bin/env python3
"""
Konverte JSON/JSONL datasetu Qwen fine-tuning formātā (JSONL).
Ievieto convert_to_qwen.py tajā pašā mapē kur JSON/JSONL faili un palaid:
    python convert_to_qwen.py

Rezultāts: qwen_finetune.jsonl — gatavs Qwen fine-tuning vajadzībām.
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
    """Nolasa gan JSON masīvu, gan JSONL formātu."""
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # Mēģina kā JSON masīvu
    if content.startswith("["):
        try:
            records = json.loads(content)
            return records
        except json.JSONDecodeError:
            pass

    # Mēģina kā JSONL (rinda pēc rindas)
    for i, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"  Bridinajums: rinda {i} izlaista — {e}")

    return records


def convert_file(input_path: str, out_file):
    print(f"Apstrada: {os.path.basename(input_path)}")

    try:
        data = load_file(input_path)
    except Exception as e:
        print(f"  Kludas: {e}")
        return 0, 0

    if not data:
        print("  Bridinajums: fails ir tukss vai neizdevas nolasit.")
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

    print(f"  -> {ok} ieraksti konverteti, {skipped} izlaisti (trukst dati)")
    return ok, skipped


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Meklē gan .json, gan .jsonl failus
    json_files = (
        glob.glob(os.path.join(script_dir, "*.json")) +
        glob.glob(os.path.join(script_dir, "*.jsonl"))
    )

    # Izfiltre jau sadalitas dalas un ieprieksejos rezultatus
    json_files = [
        f for f in json_files
        if "qwen_finetune" not in os.path.basename(f)
    ]

    if not json_files:
        print(f"Nav atrasts neviens .json vai .jsonl fails mape:\n  {script_dir}")
        sys.exit(0)

    output_path = os.path.join(script_dir, "qwen_finetune.jsonl")

    print(f"Atrasti {len(json_files)} faili mape: {script_dir}\n")

    total_ok = 0
    total_skipped = 0

    with open(output_path, "w", encoding="utf-8") as out_file:
        for json_path in sorted(json_files):
            ok, skipped = convert_file(json_path, out_file)
            total_ok += ok
            total_skipped += skipped

    size_mb = os.path.getsize(output_path) / 1024 / 1024

    print(f"\nRezultats : {output_path}")
    print(f"Kopaa     : {total_ok} ieraksti")
    print(f"Izlaisti  : {total_skipped}")
    print(f"Izmers    : {size_mb:.2f} MB")
    print("\nGatavs Qwen fine-tuning vajadzibam!")


if __name__ == "__main__":
    main()