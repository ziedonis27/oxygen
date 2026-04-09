#!/usr/bin/env python3
"""
Data preview — returns the first N records as JSON with statistics.
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


def save_file(path: str, records: list):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Data preview")
    parser.add_argument("--input",   required=True)
    parser.add_argument("--action",  default="preview", choices=["preview", "delete", "save"])
    parser.add_argument("--offset",  type=int, default=0)
    parser.add_argument("--limit",   type=int, default=20)
    parser.add_argument("--search",  default="")
    parser.add_argument("--delete-indices", default="")  # "0,3,7"
    parser.add_argument("--output",  default="")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(json.dumps({"error": f"File not found: {args.input}"}))
        sys.exit(1)

    records = load_file(args.input)
    total   = len(records)

    # Delete
    if args.action == "delete" and args.delete_indices:
        indices = set(int(i) for i in args.delete_indices.split(",") if i.strip().isdigit())
        new_records = [r for i, r in enumerate(records) if i not in indices]
        out_path = args.output or args.input
        save_file(out_path, new_records)
        print(json.dumps({
            "action": "delete",
            "deleted": len(indices),
            "remaining": len(new_records),
            "total_before": total,
        }))
        return

    # Search + pagination
    search = args.search.lower().strip()
    if search:
        filtered = []
        for i, r in enumerate(records):
            text = json.dumps(r, ensure_ascii=False).lower()
            if search in text:
                filtered.append((i, r))
    else:
        filtered = list(enumerate(records))

    filtered_total = len(filtered)
    page_items     = filtered[args.offset: args.offset + args.limit]

    # Field statistics
    all_keys: set = set()
    for _, r in filtered[:200]:
        all_keys.update(r.keys())

    result = {
        "total":          total,
        "filtered_total": filtered_total,
        "offset":         args.offset,
        "limit":          args.limit,
        "search":         search,
        "fields":         sorted(all_keys),
        "records": [
            {"_index": orig_i, **r}
            for orig_i, r in page_items
        ],
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
