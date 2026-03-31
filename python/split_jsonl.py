#!/usr/bin/env python3
"""
Sadala visus JSONL failus pašreizējā mapē daļās < 2 MB (noklusējums).
Lietošana:
    python split_jsonl.py
    python split_jsonl.py --max-mb 5
    python split_jsonl.py --max-mb 1 --output-dir ./dalas
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
            print(f"  -> Saglabats: {out_file.name}  ({current_size / 1024 / 1024:.2f} MB, {current_lines} rindas)")
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
                print(f"  Bridinajums: rinda {total_lines + 1} parsniedzmax {max_mb} MB — izlaista.")
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
            print(f"  -> Saglabats: {out_file.name}  ({current_size / 1024 / 1024:.2f} MB, {current_lines} rindas)")

    print(f"   Kopaa {total_lines} rindas => {part_index - 1} dalas.\n")
    if skipped_lines:
        print(f"   Izlaistas {skipped_lines} rindas (parak lielas).")


def main():
    parser = argparse.ArgumentParser(description="Sadala JSONL failus mazakos.")
    parser.add_argument("--max-mb", type=float, default=2.0,
                        help="Maks. izmers MB vienai dalai (noklusejums: 2.0)")
    parser.add_argument("--output-dir", default=None,
                        help="Izvades mape (noklusejums: ta pati mape, kur fails)")
    args = parser.parse_args()

    # Mekle JSONL failus tur, kur scripts atrodas
    script_dir = os.path.dirname(os.path.abspath(__file__))
    jsonl_files = glob.glob(os.path.join(script_dir, "*.jsonl"))

    # Izfiltre jau sadalitas dalas (lai netiktu apstradatas atkartoti)
    jsonl_files = [f for f in jsonl_files if "_part" not in os.path.basename(f)]

    if not jsonl_files:
        print(f"Nav atrasts neviens .jsonl fails mape: {script_dir}")
        sys.exit(0)

    print(f"Atrasti {len(jsonl_files)} JSONL faili mape: {script_dir}")
    print(f"Maks. dalas izmers: {args.max_mb} MB\n")

    for jsonl_path in jsonl_files:
        print(f"Apstrada: {os.path.basename(jsonl_path)}")
        out_dir = args.output_dir if args.output_dir else os.path.dirname(jsonl_path)
        split_jsonl(jsonl_path, args.max_mb, out_dir)

    print("Viss pabeigts!")


if __name__ == "__main__":
    main()