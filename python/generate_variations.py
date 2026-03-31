#!/usr/bin/env python3
"""
Variāciju ģenerators — izmanto Claude API lai ģenerētu jaunas variācijas
no esošiem dataset ierakstiem.

Lietošana:
    python generate_variations.py --input fails.json --api-key sk-ant-... --count 5

Nepieciešams:
    pip install anthropic
"""

import argparse
import json
import os
import sys
import time
import random

try:
    import anthropic
except ImportError:
    print("Kludas: trukst 'anthropic' biblioteka.")
    print("Instalejiet: pip install anthropic")
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
            except:
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


def generate_variation(client, instruction: str, output: str, style: str) -> dict | None:
    """Ģenerē vienu variāciju izmantojot Claude API."""

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

        # Izvelk JSON
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
        print(f"  API kludas: {e}")
        time.sleep(2)

    return None


def main():
    parser = argparse.ArgumentParser(description="Variāciju ģenerators ar Claude API")
    parser.add_argument("--input",      required=True,  help="Ievades JSON/JSONL fails")
    parser.add_argument("--output",     default="variations_output.json")
    parser.add_argument("--api-key",    required=True,  help="Anthropic API atslēga")
    parser.add_argument("--count",      type=int, default=3,  help="Variāciju skaits katram ierakstam")
    parser.add_argument("--max-source", type=int, default=100, help="Maks. avota ierakstu skaits (0=visi)")
    parser.add_argument("--style",      default="mixed",
                        choices=["rephrase", "harder", "simpler", "different", "mixed"],
                        help="Variāciju stils")
    parser.add_argument("--delay",      type=float, default=0.5, help="Pauze starp API izsaukumiem (s)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Kludas: fails nav atrasts: {args.input}")
        sys.exit(1)

    print(f"Ielādē: {args.input}")
    records = load_file(args.input)
    print(f"Ielādēti: {len(records)} ieraksti")

    # Ierobežo avota ierakstus
    source = records
    if args.max_source > 0 and len(records) > args.max_source:
        source = random.sample(records, args.max_source)
        print(f"Izmanto: {args.max_source} nejauši izvēlēti ieraksti")

    styles_pool = ["rephrase", "harder", "simpler", "different"]
    client = anthropic.Anthropic(api_key=args.api_key)

    results = []
    total = len(source) * args.count
    done = 0
    errors = 0

    print(f"\nĢenerē {total} variācijas ({args.count} katram ierakstam)...")
    print(f"Stils: {args.style} | Pauze: {args.delay}s")
    print("=" * 50)

    for i, rec in enumerate(source):
        instr, inp, out = get_text(rec)
        if not instr or not out:
            continue

        for v in range(args.count):
            style = args.style if args.style != "mixed" else random.choice(styles_pool)
            done += 1
            print(f"  [{done}/{total}] Ieraksts {i+1}, variācija {v+1} ({style})...")

            variation = generate_variation(client, instr, out, style)

            if variation:
                results.append(variation)
            else:
                errors += 1
                print(f"    Bridinajums: variācija izlaista")

            if args.delay > 0:
                time.sleep(args.delay)

    # Saglabā
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(args.output) / 1024 / 1024

    print("=" * 50)
    print(f"Rezultāts  : {args.output}")
    print(f"Ģenerēti   : {len(results)} variācijas")
    print(f"Kludas     : {errors}")
    print(f"Izmērs     : {size_mb:.2f} MB")
    print(f"Pabeigts!")


if __name__ == "__main__":
    main()
