#!/usr/bin/env python3
import argparse
import json
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def split_large_json(input_path, max_mb, output_dir):
    """Sadala lielu JSON masiva failu streaminga rezima — neielada visu atminaa."""
    max_bytes = int(max_mb * 1024 * 1024)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    os.makedirs(output_dir, exist_ok=True)

    file_size_mb = os.path.getsize(input_path) / 1024 / 1024
    print(f"  Faila izmers: {file_size_mb:.1f} MB")
    print(f"  Dalas izmers: {max_mb} MB")

    part_index = 1
    part_records = []
    part_size = 2  # []
    total = 0
    saved_parts = 0

    def save_part(records, index):
        nonlocal saved_parts
        out_path = os.path.join(output_dir, f"{base_name}_part{index:04d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, separators=(",", ":"))
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"  -> {os.path.basename(out_path)} ({len(records)} ieraksti, {size_mb:.1f} MB)")
        saved_parts += 1

    print(f"  Lasa streaminga rezima...")

    with open(input_path, "r", encoding="utf-8") as f:
        # Izlasa pirmo [ simbolu
        char = f.read(1)
        while char and char != "[":
            char = f.read(1)

        # Lasa ierakstus pa vienam
        decoder = json.JSONDecoder()
        buf = ""
        
        while True:
            chunk = f.read(65536)  # 64KB chunk
            if not chunk:
                break
            buf += chunk
            
            while buf.strip():
                buf = buf.lstrip()
                if not buf:
                    break
                # Izlaid atdalitajus
                if buf[0] in ",]":
                    buf = buf[1:]
                    continue
                # Mekle pilnu JSON objektu
                try:
                    obj, idx = decoder.raw_decode(buf)
                    buf = buf[idx:]
                    
                    record_str = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
                    record_size = len(record_str.encode("utf-8")) + 1
                    
                    if part_size + record_size > max_bytes and part_records:
                        save_part(part_records, part_index)
                        part_index += 1
                        part_records = []
                        part_size = 2
                    
                    part_records.append(obj)
                    part_size += record_size
                    total += 1
                    
                    if total % 10000 == 0:
                        print(f"  ... {total} ieraksti apstradati, {saved_parts} dalas saglabjatas")
                
                except json.JSONDecodeError:
                    # Nepietiek datu — gaida nakamo chunk
                    break

    if part_records:
        save_part(part_records, part_index)

    print(f"\n  Kopaa: {total} ieraksti => {saved_parts} dalas")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default=None, help="Darba mape")
    parser.add_argument("--max-mb", type=float, default=5.0)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    script_dir = args.folder if args.folder else os.path.dirname(os.path.abspath(__file__))
    print(f"Mape: {script_dir}")
    print(f"Maks. dalas izmers: {args.max_mb} MB\n")

    import glob
    json_files = glob.glob(os.path.join(script_dir, "*.json"))
    json_files = [f for f in json_files if "_part" not in os.path.basename(f)]

    if not json_files:
        print(f"Nav .json failu mape: {script_dir}")
        sys.exit(0)

    print(f"Atrasti {len(json_files)} JSON faili")
    for json_path in json_files:
        print(f"\nApstrada: {os.path.basename(json_path)}")
        out_dir = args.output_dir if args.output_dir else os.path.dirname(json_path)
        split_large_json(json_path, args.max_mb, out_dir)

    print("\nViss pabeigts!")

if __name__ == "__main__":
    main()