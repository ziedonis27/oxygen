#!/usr/bin/env python3
"""
Variation generator — uses Claude API to generate new variations
from existing dataset records.

Usage:
    python generate_variations.py --input file.json --count 5

API key is read from ANTHROPIC_API_KEY environment variable (recommended).

Requirements:
    pip install anthropic
"""

import argparse
import json
import os
import sys
import time
import random
from typing import Optional  # FIX: dict | None not supported in Python < 3.10

try:
    import anthropic
except ImportError:
    print("Error: missing 'anthropic' library.")
    print("Install: pip install anthropic")
    sys.exit(1)


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
    if "instruction" in r:
        return r.get("instruction", ""), r.get("input", ""), r.get("output", "")
    if "messages" in r:
        msgs = r["messages"]
        u = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        a = next((m["content"] for m in msgs if m.get("role") == "assistant"), "")
        return u, "", a
    if "problem" in r:
        return r.get("problem", ""), "", r.get("code", "")
    return "", "", ""


# FIX: dict | None -> Optional[dict] (supported Python 3.8+)
def generate_variation(client, instruction: str, output: str, style: str) -> Optional[dict]:
    """Generates one variation using Claude API."""

    styles = {
        "rephrase":  "Rephrase the instruction differently but keep the same programming task. Change wording, add/remove context.",
        "harder":    "Make the instruction more complex — add constraints, edge cases, or performance requirements.",
        "simpler":   "Simplify the instruction — make it more beginner-friendly with clearer wording.",
        "different": "Create a completely different but related programming task in the same domain/language.",
    }

    style_prompt = styles.get(style, styles["rephrase"])

    prompt = f"""You are a dataset augmentation assistant. Given a programming instruction and its solution, generate a variation.

Style: {style_prompt}

ORIGINAL INSTRUCTION:
{instruction[:1000]}

ORIGINAL SOLUTION (first 500 chars):
{output[:500]}

Generate a NEW instruction variation and a complete solution.
Respond ONLY with valid JSON in this exact format, no other text:
{{
  "instruction": "new instruction here",
  "input": "",
  "output": "complete solution here"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()

        # Extract JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        result = json.loads(text)

        if "instruction" in result and "output" in result:
            return {
                "instruction": result["instruction"],
                "input":       result.get("input", ""),
                "output":      result["output"],
            }
    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"  API error: {e}")
        time.sleep(2)

    return None


def main():
    parser = argparse.ArgumentParser(description="Variation generator with Claude API")
    parser.add_argument("--input",      required=True,  help="Input JSON/JSONL file")
    parser.add_argument("--output",     default="variations_output.json")
    parser.add_argument("--api-key",    default="", help="Anthropic API key (recommended: use ANTHROPIC_API_KEY env var)")
    parser.add_argument("--count",      type=int, default=3,  help="Variations per record")
    parser.add_argument("--max-source", type=int, default=100, help="Max source records (0=all)")
    parser.add_argument("--style",      default="mixed",
                        choices=["rephrase", "harder", "simpler", "different", "mixed"],
                        help="Variation style")
    parser.add_argument("--delay",      type=float, default=0.5, help="Delay between API calls (s)")
    args = parser.parse_args()

    # API key: env var first (safer), then argument
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip() or args.api_key.strip()
    if not api_key:
        print("Error: Anthropic API key not provided.")
        print("Options:")
        print("  1. Set environment variable: set ANTHROPIC_API_KEY=sk-ant-...")
        print("  2. Pass as argument: --api-key sk-ant-...")
        sys.exit(1)

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}")
        sys.exit(1)

    print(f"Loading: {args.input}")
    records = load_file(args.input)
    print(f"Loaded: {len(records)} records")

    source = records
    if args.max_source > 0 and len(records) > args.max_source:
        source = random.sample(records, args.max_source)
        print(f"Using: {args.max_source} randomly selected records")

    styles_pool = ["rephrase", "harder", "simpler", "different"]
    client = anthropic.Anthropic(api_key=api_key)

    results = []
    total = len(source) * args.count
    done = 0
    errors = 0

    print(f"\nGenerating {total} variations ({args.count} per record)...")
    print(f"Style: {args.style} | Delay: {args.delay}s")
    print("=" * 50)
    sys.stdout.flush()

    for i, rec in enumerate(source):
        instr, inp, out = get_text(rec)
        if not instr or not out:
            continue

        for v in range(args.count):
            style = args.style if args.style != "mixed" else random.choice(styles_pool)
            done += 1
            percent = int(done / total * 100) if total > 0 else 0
            print(f"  [{done}/{total}] ({percent}%) Record {i+1}, variation {v+1} ({style})...")
            sys.stdout.flush()

            variation = generate_variation(client, instr, out, style)

            if variation:
                results.append(variation)
            else:
                errors += 1
                print(f"    Warning: variation skipped")

            if args.delay > 0:
                time.sleep(args.delay)

    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(args.output) / 1024 / 1024

    print("=" * 50)
    print(f"Output     : {args.output}")
    print(f"Generated  : {len(results)} variations")
    print(f"Errors     : {errors}")
    print(f"Size       : {size_mb:.2f} MB")
    print(f"Done!")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
