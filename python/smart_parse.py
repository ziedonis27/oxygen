#!/usr/bin/env python3
"""
Smart Parse — automatically analyzes JSON/JSONL file structure and quality.
Detects format, field types, language, quality and suggests filter settings.
"""

import argparse
import json
import os
import sys
import re
from collections import Counter

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
            except:
                pass
    return records

def detect_format(records: list) -> str:
    if not records:
        return "unknown"
    r = records[0]
    if "instruction" in r and "output" in r:
        return "alpaca"
    if "messages" in r:
        msgs = r["messages"]
        roles = [m.get("role","") for m in msgs]
        if "user" in roles and "assistant" in roles:
            return "messages (user/assistant)"
        return "messages"
    if "problem" in r and "code" in r:
        return "problem/solution"
    if "prompt" in r and "completion" in r:
        return "prompt/completion"
    if "question" in r and "answer" in r:
        return "question/answer"
    if "input" in r and "output" in r:
        return "input/output"
    keys = list(r.keys())
    return f"unknown ({', '.join(keys[:5])})"

def get_text(r: dict) -> tuple:
    if "instruction" in r:
        return r.get("instruction",""), r.get("input",""), r.get("output","")
    if "messages" in r:
        msgs = r["messages"]
        u = next((m["content"] for m in msgs if m.get("role")=="user"),"")
        a = next((m["content"] for m in msgs if m.get("role")=="assistant"),"")
        return u, "", a
    if "problem" in r:
        return r.get("problem",""), "", r.get("code","") + r.get("reasoning","")
    if "prompt" in r:
        return r.get("prompt",""), "", r.get("completion","")
    if "question" in r:
        return r.get("question",""), "", r.get("answer","")
    return "", "", ""

def detect_language(text: str) -> str:
    lv = len(re.findall(r'[āčēģīķļņšūž]', text.lower()))
    ru = len(re.findall(r'[а-яёА-ЯЁ]', text))
    en = len(re.findall(r'[a-zA-Z]', text))
    if lv > 5:
        return "Latvian"
    if ru > en * 0.3:
        return "Russian"
    return "English"

def has_code(text: str) -> bool:
    return "```" in text or "def " in text or "function " in text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}")
        sys.exit(1)

    size_mb = os.path.getsize(args.input) / 1024 / 1024
    print(f"\n{'='*50}")
    print(f"  SMART PARSE ANALYSIS")
    print(f"{'='*50}")
    print(f"  File   : {os.path.basename(args.input)}")
    print(f"  Size   : {size_mb:.2f} MB")

    records = load_file(args.input)
    if not records:
        print("  Error: file is empty!")
        sys.exit(1)

    fmt = detect_format(records)
    print(f"  Format : {fmt}")
    print(f"  Records: {len(records)}")

    # Field analysis
    all_keys = Counter()
    for r in records:
        for k in r.keys():
            all_keys[k] += 1
    print(f"\n  FIELDS:")
    for k, v in all_keys.most_common():
        pct = v / len(records) * 100
        print(f"    {k:<20} {v:>6} records ({pct:.0f}%)")

    # Length analysis
    instr_lens, out_lens, total_lens = [], [], []
    has_code_count = 0
    has_think_count = 0
    dupes = set()
    dupe_count = 0

    for r in records:
        instr, inp, out = get_text(r)
        full = instr + inp + out
        iw = len(instr.split())
        ow = len(out.split())
        instr_lens.append(iw)
        out_lens.append(ow)
        total_lens.append(len(full.split()))
        if has_code(out):
            has_code_count += 1
        if "<think>" in out:
            has_think_count += 1
        key = instr.strip()[:150]
        if key in dupes:
            dupe_count += 1
        dupes.add(key)

    avg_instr = sum(instr_lens) // len(instr_lens) if instr_lens else 0
    avg_out   = sum(out_lens)   // len(out_lens)   if out_lens   else 0
    max_out   = max(out_lens)   if out_lens else 0
    min_out   = min(out_lens)   if out_lens else 0

    print(f"\n  LENGTHS (words):")
    print(f"    Avg instruction  : {avg_instr}")
    print(f"    Avg output       : {avg_out}")
    print(f"    Output min/max   : {min_out} / {max_out}")
    print(f"    Avg total words  : {sum(total_lens)//len(total_lens)}")

    print(f"\n  CONTENT:")
    print(f"    With code (```)  : {has_code_count} ({has_code_count/len(records)*100:.0f}%)")
    print(f"    With <think>     : {has_think_count} ({has_think_count/len(records)*100:.0f}%)")
    print(f"    Duplicates       : {dupe_count} ({dupe_count/len(records)*100:.1f}%)")

    # Language
    sample = " ".join([get_text(r)[0] for r in records[:50]])
    lang = detect_language(sample)
    print(f"    Language         : {lang}")

    # Recommendations
    print(f"\n  FILTER RECOMMENDATIONS:")
    rec_min_out = max(10, avg_out // 3)
    rec_min_instr = max(5, avg_instr // 4)
    print(f"    --min-output  {rec_min_out}   (avg {avg_out} → recommended {rec_min_out})")
    print(f"    --min-instr   {rec_min_instr}    (avg {avg_instr} → recommended {rec_min_instr})")
    if dupe_count > 0:
        print(f"    --remove-dupes    ({dupe_count} duplicates found)")
    if has_code_count > len(records) * 0.5:
        print(f"    --require-code    ({has_code_count/len(records)*100:.0f}% already contain code)")

    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
