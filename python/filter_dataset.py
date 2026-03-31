#!/usr/bin/env python3
"""
JSON/JSONL Datu Filtrs — filtrē ierakstus pēc domēna, kvalitātes un formāta.
Lietošana:
    python filter_dataset.py [opcijas]

Opcijas:
    --input         Ievades fails (.json vai .jsonl)
    --output        Izvades fails (noklusejums: filtered_output.json)
    --domain        Domēns: svelte5, python, coding, webdev, blender, zbrush, unreal, nav
    --min-output    Min. output lauka garums vārdos (noklusejums: 0)
    --min-instr     Min. instruction lauka garums vārdos (noklusejums: 0)
    --max-records   Maks. ierakstu skaits (0 = visi)
    --remove-dupes  Izlaiž dublējumus (pec instruction)
    --require-code  Prasa kodu outputā (``` bloki)
    --format        Izvades formāts: alpaca, messages, jsonl (noklusejums: alpaca)
    --include-words Obligātie vārdi (ar komatu, piem: svelte,$state)
    --exclude-words Izslēgt vārdus (ar komatu, piem: react,vue,angular)
"""

import argparse
import json
import os
import re
import sys

# Domēnu atslēgvārdi
DOMAIN_KEYWORDS = {
    "svelte5":  ["svelte", "$state", "$derived", "$effect", "$props", "rune", "sveltekit"],
    "python":   ["python", "def ", "import ", "class ", "lambda", "pytest", "pip"],
    "coding":   ["function", "algorithm", "data structure", "complexity", "recursion", "loop"],
    "webdev":   ["html", "css", "javascript", "typescript", "react", "vue", "angular", "dom"],
    "blender":  ["blender", "mesh", "vertex", "shader", "bpy", "geometry node"],
    "zbrush":   ["zbrush", "sculpt", "dynamesh", "zsphere", "subtool"],
    "unreal":   ["unreal", "blueprint", "ue5", "ue4", "actor", "component", "pawn"],
}

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
            except json.JSONDecodeError:
                pass
    return records

def get_text(record: dict) -> tuple[str, str, str]:
    """Atgriež (instruction, input, output) no jebkura formāta."""
    # Alpaca formāts
    if "instruction" in record:
        return (
            record.get("instruction", ""),
            record.get("input", ""),
            record.get("output", ""),
        )
    # Messages formāts
    if "messages" in record:
        msgs = record["messages"]
        user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        asst = next((m["content"] for m in msgs if m.get("role") == "assistant"), "")
        return user, "", asst
    # Problem/code formāts
    if "problem" in record:
        return record.get("problem",""), "", record.get("code","")
    # Prompt/completion
    if "prompt" in record:
        return record.get("prompt",""), "", record.get("completion","")

    return "", "", ""

def matches_domain(text: str, domain: str) -> bool:
    if domain == "nav":
        return True
    keywords = DOMAIN_KEYWORDS.get(domain, [])
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)

def has_code_block(text: str) -> bool:
    return "```" in text

def word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0

def to_alpaca(record: dict, instr: str, inp: str, out: str) -> dict:
    return {"instruction": instr, "input": inp, "output": out}

def to_messages(record: dict, instr: str, inp: str, out: str) -> dict:
    system = "You are a helpful AI assistant."
    user_content = f"{instr}\n\n{inp}".strip() if inp else instr
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": out},
        ]
    }

def main():
    parser = argparse.ArgumentParser(description="JSON/JSONL Datu Filtrs")
    parser.add_argument("--input",         required=True)
    parser.add_argument("--output",        default="filtered_output.json")
    parser.add_argument("--domain",        default="nav")
    parser.add_argument("--min-output",    type=int, default=0)
    parser.add_argument("--min-instr",     type=int, default=0)
    parser.add_argument("--max-records",   type=int, default=0)
    parser.add_argument("--remove-dupes",  action="store_true")
    parser.add_argument("--require-code",  action="store_true")
    parser.add_argument("--format",        default="alpaca", choices=["alpaca","messages","jsonl"])
    parser.add_argument("--include-words", default="")
    parser.add_argument("--exclude-words", default="")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Kludas: fails nav atrasts: {args.input}")
        sys.exit(1)

    print(f"Lasa: {args.input}")
    records = load_file(args.input)
    print(f"Ielādēti: {len(records)} ieraksti")

    include_words = [w.strip().lower() for w in args.include_words.split(",") if w.strip()]
    exclude_words = [w.strip().lower() for w in args.exclude_words.split(",") if w.strip()]

    results = []
    seen = set()
    stats = {"dupes": 0, "domain": 0, "min_out": 0, "min_instr": 0, "code": 0, "words": 0, "max": 0}

    for rec in records:
        instr, inp, out = get_text(rec)
        full_text = f"{instr} {inp} {out}".lower()

        # Domēns
        if args.domain != "nav" and not matches_domain(full_text, args.domain):
            stats["domain"] += 1
            continue

        # Min garumi
        if word_count(out) < args.min_output:
            stats["min_out"] += 1
            continue
        if word_count(instr) < args.min_instr:
            stats["min_instr"] += 1
            continue

        # Koda prasība
        if args.require_code and not has_code_block(out):
            stats["code"] += 1
            continue

        # Obligātie vārdi
        if include_words and not all(w in full_text for w in include_words):
            stats["words"] += 1
            continue

        # Izslēgtie vārdi
        if exclude_words and any(w in full_text for w in exclude_words):
            stats["words"] += 1
            continue

        # Dublējumi
        if args.remove_dupes:
            key = instr.strip()[:200]
            if key in seen:
                stats["dupes"] += 1
                continue
            seen.add(key)

        # Formāts
        if args.format == "alpaca":
            results.append(to_alpaca(rec, instr, inp, out))
        elif args.format == "messages":
            results.append(to_messages(rec, instr, inp, out))
        else:
            results.append(to_alpaca(rec, instr, inp, out))

        # Maks. ieraksti
        if args.max_records > 0 and len(results) >= args.max_records:
            stats["max"] += 1
            break

    # Saglabā
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)

    if args.format == "jsonl":
        with open(args.output, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(args.output) / 1024 / 1024

    print(f"\n--- Filtrēšanas rezultāts ---")
    print(f"Sākumā      : {len(records)}")
    print(f"Izlaisti    : {sum(stats.values())} (dublejumi:{stats['dupes']} domens:{stats['domain']} garums:{stats['min_out']+stats['min_instr']} kods:{stats['code']} vardi:{stats['words']})")
    print(f"Rezultāts   : {len(results)} ieraksti")
    print(f"Saglabāts   : {args.output} ({size_mb:.2f} MB)")
