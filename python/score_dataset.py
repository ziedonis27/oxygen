#!/usr/bin/env python3
"""
Kvalitātes novērtēšanas skripts — piešķir punktus (1–10) katram ierakstam
pēc vairākiem kritērijiem un saglabā rezultātus ar score lauku.

Kritēriji:
  - Instrukcijas garums (vārdi)
  - Output garums (vārdi)
  - Koda bloku klātbūtne
  - Valodas skaidrība
  - Dublicētu instrukciju sods
  - Īsu/bezjēdzīgu atbilžu sods

Lietošana:
    python score_dataset.py --input fails.json --output scored.json --min-score 5
"""

import argparse
import json
import os
import re
import sys
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
            except Exception:
                pass
    return records


def get_text(r: dict) -> tuple:
    def s(v): return str(v) if v is not None else ""
    if "instruction" in r:
        return s(r.get("instruction")), s(r.get("input")), s(r.get("output"))
    if "messages" in r:
        msgs = r.get("messages", [])
        u = next((m.get("content") for m in msgs if m.get("role") == "user"), "")
        a = next((m.get("content") for m in msgs if m.get("role") == "assistant"), "")
        return s(u), "", s(a)
    if "problem" in r:
        return s(r.get("problem")), "", s(r.get("code"))
    if "prompt" in r:
        return s(r.get("prompt")), "", s(r.get("completion"))
    if "script" in r:
        return s(r.get("input")), "", s(r.get("script"))
    return "", "", ""

# Atbalsts UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def count_words(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def count_code_blocks(text: str) -> int:
    return len(re.findall(r"```", text)) // 2


def count_code_lines(text: str) -> int:
    """Skaita koda rindas ``` blokos."""
    blocks = re.findall(r"```.*?```", text, re.DOTALL)
    return sum(len(b.splitlines()) for b in blocks)


def has_structured_output(text: str) -> bool:
    """Pārbauda vai output ir strukturēts (saraksti, virsraksti, kods)."""
    return bool(re.search(r"(```|#{1,3} |\n[-*] |\n\d+\. )", text))


def detect_language(text: str) -> str:
    """Vienkārša valodas noteikšana."""
    lv_chars = len(re.findall(r"[āčēģīķļņšūž]", text.lower()))
    ru_chars = len(re.findall(r"[а-яё]", text.lower()))
    if lv_chars > 3:
        return "lv"
    if ru_chars > 5:
        return "ru"
    return "en"


def score_record(instr: str, inp: str, out: str) -> dict:
    """
    Novērtē ierakstu un atgriež detalizētu score.
    Kopējais score: 1–10 punkti.
    """
    scores = {}
    reasons = []

    instr_words = count_words(instr)
    out_words   = count_words(out)
    code_blocks = count_code_blocks(out)
    code_lines  = count_code_lines(out)

    # 1. Instrukcijas garums (0–2 punkti)
    if instr_words >= 15:
        scores["instr_len"] = 2
    elif instr_words >= 7:
        scores["instr_len"] = 1
        reasons.append("īsa instrukcija")
    else:
        scores["instr_len"] = 0
        reasons.append("ļoti īsa instrukcija")

    # 2. Output garums (0–3 punkti)
    if out_words >= 150:
        scores["out_len"] = 3
    elif out_words >= 60:
        scores["out_len"] = 2
    elif out_words >= 20:
        scores["out_len"] = 1
        reasons.append("īss output")
    else:
        scores["out_len"] = 0
        reasons.append("ļoti īss output")

    # 3. Kods outputā (0–2 punkti)
    if code_blocks >= 2 or code_lines >= 20:
        scores["code"] = 2
    elif code_blocks == 1 or code_lines >= 5:
        scores["code"] = 1
    else:
        scores["code"] = 0

    # 4. Struktūra (0–1 punkts)
    if has_structured_output(out):
        scores["structure"] = 1
    else:
        scores["structure"] = 0
        reasons.append("nav struktūras")

    # 5. Valodas konsekvence (0–1 punkts)
    lang_instr = detect_language(instr)
    lang_out   = detect_language(out)
    if lang_instr == lang_out:
        scores["lang"] = 1
    else:
        scores["lang"] = 0
        reasons.append(f"valodu neatbilstība ({lang_instr}≠{lang_out})")

    # 6. Sods par bezsaturu (−1)
    penalty = 0
    bad_phrases = ["i don't know", "i cannot", "as an ai", "i'm sorry", "es nezinu", "es nevaru"]
    out_lower = out.lower()
    if any(p in out_lower for p in bad_phrases):
        penalty -= 1
        reasons.append("bezsatura atbilde")

    # Kopējais score
    raw = sum(scores.values()) + penalty
    total = max(1, min(10, raw))

    return {
        "total": total,
        "breakdown": scores,
        "reasons": reasons,
        "stats": {
            "instr_words": instr_words,
            "out_words":   out_words,
            "code_blocks": code_blocks,
            "code_lines":  code_lines,
            "lang":        lang_instr,
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Dataset kvalitātes novērtētājs")
    parser.add_argument("--input",     required=True,  help="Ievades JSON/JSONL fails")
    parser.add_argument("--output",    default="scored_output.json", help="Izvades fails")
    parser.add_argument("--min-score", type=int, default=0,  help="Min. score filtrēšanai (0=visi)")
    parser.add_argument("--max-score", type=int, default=10, help="Max. score filtrēšanai")
    parser.add_argument("--stats-only", action="store_true", help="Tikai statistika, nesaglabā failu")
    parser.add_argument("--top",       type=int, default=0,  help="Saglabā tikai top N ierakstus")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Kludas: fails nav atrasts: {args.input}")
        sys.exit(1)

    def log(msg):
        print(msg, file=sys.stderr, flush=True)

    log(f"Ielāde: {args.input}")
    records = load_file(args.input)
    log(f"Ielādēti: {len(records)} ieraksti")
    log("Novērtē...")

    scored = []
    score_dist = Counter()

    for i, rec in enumerate(records):
        instr, inp, out = get_text(rec)
        if not instr and not out:
            continue

        result = score_record(instr, inp, out)
        s = result["total"]
        score_dist[s] += 1

        new_rec = dict(rec)
        new_rec["_score"]   = s
        new_rec["_reasons"] = result["reasons"]
        new_rec["_stats"]   = result["stats"]
        scored.append(new_rec)

        if (i + 1) % 1000 == 0:
            log(f"  Apstrādāti: {i+1}/{len(records)}")

    scored.sort(key=lambda x: x["_score"], reverse=True)
    filtered = [r for r in scored if args.min_score <= r["_score"] <= args.max_score]

    if args.top > 0:
        filtered = filtered[:args.top]

    log("\n" + "=" * 50)
    log("KVALITĀTES SADALĪJUMS:")
    total_scored = len(scored)
    for s in range(10, 0, -1):
        cnt = score_dist.get(s, 0)
        bar = "█" * int(cnt / max(total_scored, 1) * 30)
        pct = cnt / max(total_scored, 1) * 100
        log(f"  {s:2d}/10  {bar:<30} {cnt:5d} ({pct:.1f}%)")

    total_sum = sum(r["_score"] for r in scored)
    avg = total_sum / max(total_scored, 1) if total_scored > 0 else 0

    log(f"\nVidējais score : {avg:.2f}/10")
    log(f"Kopā ieraksti  : {total_scored}")
    log(f"Pēc filtrēšanas: {len(filtered)}")

    if not args.stats_only:
        out_records = [dict(r) for r in filtered]
        out_dir = os.path.dirname(os.path.abspath(args.output))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out_records, f, ensure_ascii=False, indent=2)

        size_mb = os.path.getsize(args.output) / 1024 / 1024
        log(f"\nSaglabāts : {os.path.abspath(args.output)}")
        log(f"Izmērs    : {size_mb:.2f} MB")

    log("Pabeigts!")

    # IZVADE PRIEKS UI (TIKAI STDOUT)
    summary = {
        "total": total_scored,
        "saved": len(filtered),
        "average": float(avg),
        "distribution": [{"score": s, "count": score_dist[s], "pct": (score_dist[s]/total_scored)*100 if total_scored>0 else 0} for s in range(11)]
    }
    print(json.dumps(summary))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
