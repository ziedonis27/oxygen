#!/usr/bin/env python3
"""
Language filter — detects and filters records by language.

Supported languages:
  en  — English
  lv  — Latvian
  ru  — Russian
  de  — German
  fr  — French
  es  — Spanish
  zh  — Chinese
  ja  — Japanese
  auto — Auto (keeps all, adds _lang field)

Usage:
    python language_filter.py --input file.json --lang en
    python language_filter.py --input file.json --lang en,lv --stats-only

Optional:
    pip install langdetect   or   conda install -c conda-forge langdetect
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

# Try to import langdetect
try:
    from langdetect import detect, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    DetectorFactory.seed = 42  # Reproducible results
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False


# ─────────────────────────────────────────
# Lightweight fallback language detection
# (works without langdetect)
# ─────────────────────────────────────────

LV_CHARS  = set("āčēģīķļņšūžĀČĒĢĪĶĻŅŠŪŽ")
RU_CHARS  = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
ZH_RANGE  = (0x4E00, 0x9FFF)
JA_RANGES = [(0x3040, 0x309F), (0x30A0, 0x30FF)]
DE_CHARS  = set("äöüÄÖÜß")
FR_CHARS  = set("àâæçéèêëîïôœùûüÿÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ")
ES_CHARS  = set("áéíóúüñÁÉÍÓÚÜÑ¿¡")


def fast_detect(text: str) -> str:
    """Fast language detection without ML library."""
    if not text or len(text.strip()) < 5:
        return "unknown"

    sample = text[:500]
    chars  = Counter(sample)
    total  = max(len(sample), 1)

    # Latvian — unique characters (ķ, ļ, ģ etc.)
    lv_count = sum(chars.get(c, 0) for c in LV_CHARS)
    if lv_count / total > 0.02:
        return "lv"

    # Russian — Cyrillic
    ru_count = sum(chars.get(c, 0) for c in RU_CHARS)
    if ru_count / total > 0.1:
        return "ru"

    # Chinese
    zh_count = sum(1 for c in sample if ZH_RANGE[0] <= ord(c) <= ZH_RANGE[1])
    if zh_count / total > 0.05:
        return "zh"

    # Japanese
    ja_count = sum(1 for c in sample if any(s <= ord(c) <= e for s, e in JA_RANGES))
    if ja_count / total > 0.03:
        return "ja"

    # German
    de_count = sum(chars.get(c, 0) for c in DE_CHARS)
    if de_count / total > 0.01:
        return "de"

    # French
    fr_count = sum(chars.get(c, 0) for c in FR_CHARS)
    if fr_count / total > 0.01:
        return "fr"

    # Spanish
    es_count = sum(chars.get(c, 0) for c in ES_CHARS)
    if es_count / total > 0.01:
        return "es"

    return "en"  # default — Latin alphabet = English


# Minimum text length for reliable detection
MIN_RELIABLE_LENGTH = 40


def detect_language(text: str) -> str:
    """
    Detects language using a two-stage approach:
    1. fast_detect — quick Unicode analysis (LV/RU/ZH/JA very accurate)
    2. langdetect  — ML model for English/DE/FR/ES distinction (if text long enough)

    For short texts (<40 chars) uses only fast_detect,
    as langdetect is unreliable with short texts.
    """
    if not text or len(text.strip()) < 5:
        return "unknown"

    text = text.strip()

    # 1. fast_detect first — very accurate for non-Latin languages
    fast_result = fast_detect(text)
    if fast_result in ("lv", "ru", "zh", "ja"):
        return fast_result  # High confidence — return immediately

    # 2. Text too short — don't trust langdetect
    if len(text) < MIN_RELIABLE_LENGTH:
        return fast_result  # "en", "de", "fr", "es" or "unknown"

    # 3. Use langdetect for longer texts
    if HAS_LANGDETECT:
        try:
            ld_result = detect(text[:1500])
            # If langdetect says "nl" (Dutch) but no Dutch characters found
            # and fast_detect says "en" — trust fast_detect
            nl_chars = set("ĳĲ")
            nl_specific = sum(1 for c in text if c in nl_chars)
            if ld_result == "nl" and nl_specific == 0 and fast_result == "en":
                return "en"
            return ld_result
        except LangDetectException:
            return fast_result

    return fast_result


def get_text(r: dict) -> tuple:
    if "instruction" in r:
        return r.get("instruction", ""), r.get("input", ""), r.get("output", "")
    if "messages" in r:
        msgs = r["messages"]
        u = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        a = next((m["content"] for m in msgs if m.get("role") == "assistant"), "")
        return u, "", a
    if "problem" in r:
        return r.get("problem", ""), "", r.get("code", "")
    if "prompt" in r:
        return r.get("prompt", ""), "", r.get("completion", "")
    return "", "", ""


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


LANG_NAMES = {
    "en": "English 🇬🇧",    "lv": "Latvian 🇱🇻",
    "ru": "Russian 🇷🇺",    "de": "German 🇩🇪",
    "fr": "French 🇫🇷",     "es": "Spanish 🇪🇸",
    "zh": "Chinese 🇨🇳",    "ja": "Japanese 🇯🇵",
    "nl": "Dutch 🇳🇱",      "it": "Italian 🇮🇹",
    "pt": "Portuguese 🇵🇹", "unknown": "Unknown ❓",
}


def main():
    parser = argparse.ArgumentParser(description="Language filter")
    parser.add_argument("--input",      required=True,  help="Input JSON/JSONL file")
    parser.add_argument("--output",     default="lang_filtered.json")
    parser.add_argument("--lang",       default="auto",
                        help="Language(s): en,lv,ru,de,fr,es,zh,ja or auto. Comma-separated: en,lv")
    parser.add_argument("--field",      default="instruction",
                        help="Detection field: instruction, output, both")
    parser.add_argument("--stats-only", action="store_true", help="Stats only")
    parser.add_argument("--add-field",  action="store_true", help="Add _lang field")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}")
        sys.exit(1)

    target_langs = (
        [l.strip().lower() for l in args.lang.split(",") if l.strip()]
        if args.lang != "auto" else []
    )
    auto_mode = args.lang == "auto"

    def log(msg):
        print(msg, file=sys.stderr, flush=True)

    method = "langdetect + fast_detect" if HAS_LANGDETECT else "built-in detection"
    log(f"Loading : {args.input}")
    log(f"Method  : {method}")
    if not HAS_LANGDETECT:
        log("  ℹ️  For improved detection: conda install -c conda-forge langdetect")
    if target_langs:
        log(f"Languages: {', '.join(target_langs)}")
    else:
        log("Mode    : auto (adds _lang field to all records)")

    records = load_file(args.input)
    log(f"Records : {len(records)}\nDetecting languages...")

    lang_counts = Counter()
    results     = []
    skipped     = 0

    for i, rec in enumerate(records):
        instr, inp, out = get_text(rec)

        if args.field == "output":
            detect_text = out
        elif args.field == "both":
            detect_text = f"{instr} {out}"
        else:
            detect_text = instr or out

        lang = detect_language(detect_text)
        lang_counts[lang] += 1

        if auto_mode or not target_langs:
            new_rec = dict(rec)
            new_rec["_lang"] = lang
            results.append(new_rec)
        else:
            if lang in target_langs:
                new_rec = dict(rec)
                if args.add_field:
                    new_rec["_lang"] = lang
                results.append(new_rec)
            else:
                skipped += 1

        if (i + 1) % 2000 == 0:
            log(f"  Processed: {i+1}/{len(records)}")

    # Statistics to stderr log
    total = len(records)
    log("\n" + "=" * 50)
    log("LANGUAGE DISTRIBUTION:")
    for lang, cnt in lang_counts.most_common():
        name = LANG_NAMES.get(lang, lang)
        bar  = "█" * int(cnt / max(total, 1) * 30)
        pct  = cnt / max(total, 1) * 100
        log(f"  {lang:8s} {name:22s} {bar:<30} {cnt:6d} ({pct:.1f}%)")

    log(f"\nTotal records  : {total}")
    if not auto_mode:
        log(f"Saved          : {len(results)}")
        log(f"Filtered out   : {skipped}")

    if not args.stats_only:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        size_mb = os.path.getsize(args.output) / 1024 / 1024
        log(f"\nSaved    : {os.path.abspath(args.output)}")
        log(f"Records  : {len(results)}")
        log(f"Size     : {size_mb:.2f} MB")

    log("Done!")

    # OUTPUT FOR UI (STDOUT)
    summary = {
        "total": total,
        "saved": len(results),
        "stats": [{"lang": lang, "name": LANG_NAMES.get(lang, lang), "count": cnt, "pct": (cnt/total)*100 if total>0 else 0} for lang, cnt in lang_counts.most_common()]
    }
    print(json.dumps(summary))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
