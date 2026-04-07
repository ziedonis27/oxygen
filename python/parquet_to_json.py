#!/usr/bin/env python3
"""
Konvertē visus Parquet failus pašreizējā mapē uz JSON.
Lietošana:
    python parquet_to_json.py
    python parquet_to_json.py --output-dir ./rezultati
    python parquet_to_json.py --indent 2   (formatēts JSON, noklusejums: 2)

Nepieciešamās bibliotēkas (instalē vienu reizi):
    pip install pandas pyarrow
"""

import argparse
import os
import sys
import glob
import json

try:
    import pandas as pd
except ImportError:
    print("Trukst biblioteka 'pandas'. Instalejiet: pip install pandas pyarrow")
    sys.exit(1)


def convert_parquet(input_path: str, output_dir: str, indent: int):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    out_path = os.path.join(output_dir, f"{base_name}.json")

    print(f"Apstrada: {os.path.basename(input_path)}")

    try:
        df = pd.read_parquet(input_path)
    except Exception as e:
        print(f"  Kludas: nevareja nolasit failu — {e}")
        return

    # Konverte uz JSON sarakstu (katrs ieraksts = objekts)
    records = df.to_dict(orient="records")

    # Parsaka datuma/laika tipus uz string (JSON neatklauj datetime)
    def default_serializer(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return str(obj)

    os.makedirs(output_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=indent, default=default_serializer)

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  -> Saglabats: {out_path}  ({len(records)} ieraksti, {size_mb:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Konverte Parquet failus uz JSON.")
    parser.add_argument("--folder", default=None, help="Darba mape")
    parser.add_argument("--output-dir", default=None,
                        help="Izvades mape (noklusejums: ta pati mape kur parquet fails)")
    parser.add_argument("--indent", type=int, default=2,
                        help="JSON atkape (noklusejums: 2, 0 = kompakts)")
    args = parser.parse_args()

    script_dir = args.folder if args.folder else os.path.dirname(os.path.abspath(__file__))
    parquet_files = glob.glob(os.path.join(script_dir, "*.parquet"))

    if not parquet_files:
        print(f"Nav atrasts neviens .parquet fails mape: {script_dir}")
        sys.exit(0)

    print(f"Atrasti {len(parquet_files)} Parquet faili mape: {script_dir}\n")

    for parquet_path in parquet_files:
        out_dir = args.output_dir if args.output_dir else os.path.dirname(parquet_path)
        convert_parquet(parquet_path, out_dir, args.indent)

    print("\nViss pabeigts!")


if __name__ == "__main__":
    main()
