#!/usr/bin/env python3
"""
Sadala lielu JSON failu (masīvu) mazākos failos pa 5 MB.
Ievieto split_json.py tajā pašā mapē kur JSON faili un palaid:
    python split_json.py
    python split_json.py --max-mb 2
    python split_json.py --output-dir ./dalas
"""

import argparse
import glob
import json
import os
import sys


def split_json(input_path: str, max_mb: float, output_dir: str):
    max_bytes = int(max_mb * 1024 * 1024)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    os.makedirs(output_dir, exist_ok=True)

    print(f"Lasa: {os.path.basename(input_path)} ...")

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  Kludas: nekorekts JSON — {e}")
        return
    except Exception as e:
        print(f"  Kludas: {e}")
        return

    # Atbalsta gan masīvu [...], gan vienu objektu {...}
    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = data
    else:
        print("  Kludas: JSON jābūt masīvam [...] vai objektam {...}")
        return

    print(f"  Kopā ieraksti: {len(records)}")

    part_index = 1
    part_records = []
    part_size = 2  # '[]' simboli

    def save_part(records_chunk, index):
        out_path = os.path.join(output_dir, f"{base_name}_part{index:04d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records_chunk, f, ensure_ascii=False, indent=2, default=str)
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"  -> Saglabats: {os.path.basename(out_path)}  ({len(records_chunk)} ieraksti, {size_mb:.2f} MB)")

    for record in records:
        record_str = json.dumps(record, ensure_ascii=False, default=str)
        record_size = len(record_str.encode("utf-8")) + 2  # +2 komats + atstarpe

        # Ja viens ieraksts lielāks par limitu — saglabā atsevišķi
        if record_size > max_bytes:
            if part_records:
                save_part(part_records, part_index)
                part_index += 1
                part_records = []
                part_size = 2
            save_part([record], part_index)
            part_index += 1
            print(f"  Bridinajums: viens ieraksts parsniedzmax {max_mb} MB — saglabats atseviski.")
            continue

        if part_size + record_size > max_bytes and part_records:
            save_part(part_records, part_index)
            part_index += 1
            part_records = []
            part_size = 2

        part_records.append(record)
        part_size += record_size

    if part_records:
        save_part(part_records, part_index)
        part_index += 1

    print(f"  Pabeigts: {part_index - 1} dalas izveidotas.\n")


def main():
    parser = argparse.ArgumentParser(description="Sadala lielu JSON failu mazakos.")
    parser.add_argument("--max-mb", type=float, default=5.0,
                        help="Maks. izmers MB vienai dalai (noklusejums: 5.0)")
    parser.add_argument("--output-dir", default=None,
                        help="Izvades mape (noklusejums: ta pati mape kur fails)")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_files = glob.glob(os.path.join(script_dir, "*.json"))

    # Izfiltre jau sadalitas dalas
    json_files = [f for f in json_files if "_part" not in os.path.basename(f)]

    if not json_files:
        print(f"Nav atrasts neviens .json fails mape: {script_dir}")
        sys.exit(0)

    print(f"Atrasti {len(json_files)} JSON faili mape: {script_dir}")
    print(f"Maks. dalas izmers: {args.max_mb} MB\n")

    for json_path in json_files:
        out_dir = args.output_dir if args.output_dir else os.path.dirname(json_path)
        split_json(json_path, args.max_mb, out_dir)

    print("Viss pabeigts!")


if __name__ == "__main__":
    main()