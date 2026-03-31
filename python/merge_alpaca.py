#!/usr/bin/env python3
"""
Apvieno vairākus Alpaca JSON failus vienā, izlaižot dublējumus.
Ievieto merge_alpaca.py tajā pašā mapē kur Alpaca JSON faili un palaid:
    python merge_alpaca.py

Rezultāts: alpaca_merged.json
"""

import glob
import json
import os
import sys


def load_json(path: str):
    print(f"Lasa: {os.path.basename(path)}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            print(f"  -> {len(data)} ieraksti")
            return data
        else:
            print("  Bridinajums: fails nav masivs — izlaists")
            return []
    except Exception as e:
        print(f"  Kludas: {e}")
        return []


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Meklē visus .json failus izņemot jau merged
    json_files = glob.glob(os.path.join(script_dir, "*.json"))
    json_files = [
        f for f in json_files
        if "alpaca_merged" not in os.path.basename(f)
    ]

    if not json_files:
        print(f"Nav atrasts neviens .json fails mape:\n  {script_dir}")
        sys.exit(0)

    print(f"Atrasti {len(json_files)} JSON faili:\n")

    all_records = []
    total_loaded = 0

    for path in sorted(json_files):
        records = load_json(path)
        all_records.extend(records)
        total_loaded += len(records)

    print(f"\nKopaa ielādēti : {total_loaded} ieraksti")

    # Izlaiž dublējumus pēc 'instruction' lauka
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

    print(f"Dublejumi      : {duplicates}")
    print(f"Unikāli        : {len(unique_records)}")

    # Saglabā rezultātu
    output_path = os.path.join(script_dir, "alpaca_merged.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique_records, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"\nRezultats : {output_path}")
    print(f"Izmers    : {size_mb:.2f} MB")
    print("\nGatavs! Augshupieladejiet alpaca_merged.json uz Colab.")


if __name__ == "__main__":
    main()