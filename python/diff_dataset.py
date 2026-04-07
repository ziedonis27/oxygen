#!/usr/bin/env python3
"""
Datasetu salīdzinājums (Diff) — salīdzina divus JSON/JSONL failus pēc instrukcijām.
"""
import argparse
import json
import os
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


def get_key(r: dict) -> str:
    """Atgriež unikālu atslēgu ierakstam salīdzināšanai."""
    for field in ("instruction", "prompt", "problem", "question"):
        if field in r:
            return r[field].strip()[:200]
    if "messages" in r:
        msgs = r["messages"]
        u = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        return u.strip()[:200]
    return json.dumps(r, ensure_ascii=False)[:200]


def get_output(r: dict) -> str:
    for field in ("output", "completion", "code", "answer"):
        if field in r:
            return r[field].strip()[:500]
    if "messages" in r:
        msgs = r["messages"]
        a = next((m["content"] for m in msgs if m.get("role") == "assistant"), "")
        return a.strip()[:500]
    return ""


def main():
    parser = argparse.ArgumentParser(description="Datasetu Diff")
    parser.add_argument("--file-a",  required=True)
    parser.add_argument("--file-b",  required=True)
    parser.add_argument("--limit",   type=int, default=50, help="Max diff ierakstu skaits")
    args = parser.parse_args()

    for p in (args.file_a, args.file_b):
        if not os.path.exists(p):
            print(json.dumps({"error": f"Fails nav atrasts: {p}"}))
            sys.exit(1)

    records_a = load_file(args.file_a)
    records_b = load_file(args.file_b)

    keys_a = {get_key(r): r for r in records_a}
    keys_b = {get_key(r): r for r in records_b}

    set_a = set(keys_a.keys())
    set_b = set(keys_b.keys())

    only_in_a  = set_a - set_b          # Dzēsti
    only_in_b  = set_b - set_a          # Pievienoti
    in_both    = set_a & set_b          # Kopīgi

    # Mainīti — ir abos, bet output atšķiras
    changed = []
    for key in in_both:
        out_a = get_output(keys_a[key])
        out_b = get_output(keys_b[key])
        if out_a != out_b:
            changed.append(key)

    def fmt(r: dict) -> dict:
        return {
            "instruction": get_key(r),
            "output_preview": get_output(r)[:200],
        }

    result = {
        "file_a": {"path": args.file_a, "total": len(records_a)},
        "file_b": {"path": args.file_b, "total": len(records_b)},
        "summary": {
            "added":    len(only_in_b),
            "removed":  len(only_in_a),
            "changed":  len(changed),
            "unchanged": len(in_both) - len(changed),
        },
        "added":   [fmt(keys_b[k]) for k in list(only_in_b)[:args.limit]],
        "removed": [fmt(keys_a[k]) for k in list(only_in_a)[:args.limit]],
        "changed": [
            {
                "instruction":  k[:200],
                "output_a":     get_output(keys_a[k])[:200],
                "output_b":     get_output(keys_b[k])[:200],
            }
            for k in changed[:args.limit]
        ],
    }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
