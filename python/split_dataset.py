#!/usr/bin/env python3
"""
Treniņa sadale — sadala datasetu train/validation/test daļās.
"""
import argparse
import json
import os
import random
import sys


def load_file(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if content.startswith("["):
        return json.loads(content)
    records = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    return records


def save_split(records: list, path: str, fmt: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if fmt == "jsonl":
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Train/Val/Test sadale")
    parser.add_argument("--input",      required=True)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--train-pct",  type=float, default=80.0)
    parser.add_argument("--val-pct",    type=float, default=10.0)
    parser.add_argument("--test-pct",   type=float, default=10.0)
    parser.add_argument("--shuffle",    action="store_true", default=True)
    parser.add_argument("--seed",       type=int, default=42)
    parser.add_argument("--format",     default="json", choices=["json", "jsonl"])
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Kļūda: fails nav atrasts: {args.input}")
        sys.exit(1)

    # Pārbauda procentus
    total_pct = args.train_pct + args.val_pct + args.test_pct
    if abs(total_pct - 100.0) > 0.1:
        print(f"Kļūda: procenti ({total_pct:.1f}%) nav vienādi ar 100%")
        sys.exit(1)

    print(f"Ielādē: {args.input}")
    records = load_file(args.input)
    total   = len(records)
    print(f"Ieraksti: {total}")

    if args.shuffle:
        random.seed(args.seed)
        random.shuffle(records)
        print(f"Jaukts (seed={args.seed})")

    # Aprēķina robežas
    train_end = int(total * args.train_pct / 100)
    val_end   = train_end + int(total * args.val_pct / 100)

    train_set = records[:train_end]
    val_set   = records[train_end:val_end]
    test_set  = records[val_end:]

    # Izvades mape
    input_dir  = os.path.dirname(os.path.abspath(args.input))
    output_dir = args.output_dir or input_dir
    ext        = "jsonl" if args.format == "jsonl" else "json"

    splits = [
        ("train", train_set),
        ("validation", val_set),
        ("test", test_set),
    ]

    print("\n" + "=" * 50)
    print("SADALE:")
    saved = []
    for name, data in splits:
        if not data:
            print(f"  {name:12s}: 0 ieraksti (izlaists)")
            continue
        out_path = os.path.join(output_dir, f"split_{name}.{ext}")
        save_split(data, out_path, args.format)
        size_mb  = os.path.getsize(out_path) / 1024 / 1024
        pct_real = len(data) / total * 100
        print(f"  {name:12s}: {len(data):6d} ieraksti ({pct_real:.1f}%) → {os.path.basename(out_path)} ({size_mb:.2f} MB)")
        saved.append(out_path)

    print(f"\nKopā    : {total} ieraksti")
    print(f"Formāts : {args.format.upper()}")
    print(f"Mape    : {output_dir}")
    print("Pabeigts!")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
