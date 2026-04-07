#!/usr/bin/env python3
"""
Dashboard skripts — analizē darba mapes failus un atgriež statistiku JSON formātā.
"""
import argparse
import json
import os
import sys
from pathlib import Path


def analyze_json_file(path: str) -> dict:
    """Analizē vienu JSON/JSONL failu — atgriež ierakstu skaitu un izmēru."""
    try:
        size_mb = os.path.getsize(path) / 1024 / 1024
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if content.startswith("["):
            data = json.loads(content)
            count = len(data)
        else:
            count = sum(1 for line in content.splitlines() if line.strip())

        return {"name": os.path.basename(path), "count": count, "size_mb": round(size_mb, 2)}
    except Exception as e:
        return {"name": os.path.basename(path), "count": 0, "size_mb": 0, "error": str(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(json.dumps({"error": "Mape nav atrasta"}))
        sys.exit(1)

    files = []
    total_records = 0
    total_size_mb = 0.0

    for ext in ["*.json", "*.jsonl"]:
        for f in sorted(folder.glob(ext)):
            if f.name.startswith("."):
                continue
            info = analyze_json_file(str(f))
            files.append(info)
            total_records += info["count"]
            total_size_mb += info["size_mb"]

    # Apakšmapju faili (1 līmenis dziļi)
    for subdir in folder.iterdir():
        if subdir.is_dir() and subdir.name not in ["node_modules", ".git", "target", "python", ".svelte-kit"]:
            for ext in ["*.json", "*.jsonl"]:
                for f in sorted(subdir.glob(ext)):
                    info = analyze_json_file(str(f))
                    info["name"] = f"{subdir.name}/{f.name}"
                    files.append(info)
                    total_records += info["count"]
                    total_size_mb += info["size_mb"]

    # Parquet faili
    parquet_count = len(list(folder.glob("*.parquet")))

    result = {
        "files": files,
        "total_records": total_records,
        "total_files": len(files),
        "total_size_mb": round(total_size_mb, 2),
        "parquet_files": parquet_count,
        "folder": str(folder),
    }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
