#!/usr/bin/env python3
"""
JSON/JSONL Datu Filtrs — STRĪMĒŠANAS REŽĪMS (piemērots milzīgiem failiem).
Lietošana:
    python filter_dataset.py [opcijas]
"""

import argparse
import json
import os
import re
import sys
import time

# Piespiest UTF-8 kodējumu (Windows termināļiem)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

def get_text(record: dict) -> tuple[str, str, str]:
    """Atgriež (instruction, input, output) no jebkura formāta."""
    def s(v): return str(v) if v is not None else ""
    
    if "instruction" in record:
        return (s(record.get("instruction")), s(record.get("input")), s(record.get("output")))
    if "messages" in record:
        msgs = record.get("messages", [])
        user = next((m.get("content") for m in msgs if m.get("role") == "user"), "")
        asst = next((m.get("content") for m in msgs if m.get("role") == "assistant"), "")
        return s(user), "", s(asst)
    if "problem" in record:
        return s(record.get("problem")), "", s(record.get("code"))
    if "prompt" in record:
        return s(record.get("prompt")), "", s(record.get("completion"))
    # Blender / Scripting formāts
    if "script" in record:
        return s(record.get("input")), "", s(record.get("script"))
    return "", "", ""

def matches_domain(text: str, domain: str) -> bool:
    if domain == "nav" or not domain:
        return True
    keywords = DOMAIN_KEYWORDS.get(domain, [])
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)

def has_code_block(text: str) -> bool:
    return "```" in text

def word_count(text: str) -> int:
    if text is None: return 0
    t = str(text).strip()
    return len(t.split()) if t else 0

def to_alpaca(instr: str, inp: str, out: str) -> dict:
    return {"instruction": instr, "input": inp, "output": out}

def to_messages(instr: str, inp: str, out: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": f"{instr}\n\n{inp}".strip() if inp else instr},
            {"role": "assistant", "content": out},
        ]
    }

def stream_json_array(f):
    """Mēģina straumēt JSON masīva ierakstus pa vienam."""
    decoder = json.JSONDecoder()
    buffer = ""
    # Atrod sākuma [
    while True:
        chunk = f.read(1024 * 64)
        if not chunk: break
        buffer += chunk
        if '[' in buffer:
            buffer = buffer[buffer.find('[')+1:].strip()
            break
    
    while True:
        try:
            while buffer and buffer[0] in (',', ' ', '\n', '\r', '\t', ']'):
                if buffer[0] == ']': return # Masīva beigas
                buffer = buffer[1:].strip()
            
            if not buffer:
                chunk = f.read(1024 * 64)
                if not chunk: break
                buffer = chunk.strip()
                continue
            
            obj, pos = decoder.raw_decode(buffer)
            yield obj
            buffer = buffer[pos:].strip()
            
        except json.JSONDecodeError:
            chunk = f.read(1024 * 64)
            if not chunk: break
            buffer += chunk

def stream_loader(path: str):
    """Detektē formātu un straumē ierakstus."""
    with open(path, "r", encoding="utf-8") as f:
        first_char = ""
        while not first_char:
            c = f.read(1)
            if not c: break
            if not c.isspace(): first_char = c
        
        f.seek(0)
        if first_char == '[':
            yield from stream_json_array(f)
        else:
            # JSONL režīms
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except:
                        pass

def main():
    parser = argparse.ArgumentParser(description="JSON/JSONL Filtrs (Streaming)")
    parser.add_argument("--input",         required=True)
    parser.add_argument("--output",        required=True)
    parser.add_argument("--domain",        default="nav")
    parser.add_argument("--min-output",    type=int, default=0)
    parser.add_argument("--min-instr",     type=int, default=0)
    parser.add_argument("--max-records",   type=int, default=0)
    parser.add_argument("--remove-dupes",  action="store_true")
    parser.add_argument("--require-code",  action="store_true")
    parser.add_argument("--format",        default="alpaca", choices=["alpaca","messages","jsonl"])
    parser.add_argument("--include-words", default="")
    parser.add_argument("--exclude-words", default="")
    parser.add_argument("--append", action="store_true", help="Pievienot datus esošajam failam")
    args = parser.parse_args()

    print(f"--- Oxygen Streaming Filter ---")
    print(f"CWD: {os.getcwd()}")
    print(f"Ievade: {args.input}")
    print(f"Izvade: {os.path.abspath(args.output)}")
    
    if not os.path.exists(args.input):
        print(f"Kluda: fails nav atrasts: {args.input}")
        return

    include_words = [w.strip().lower() for w in args.include_words.split(",") if w.strip()]
    exclude_words = [w.strip().lower() for w in args.exclude_words.split(",") if w.strip()]

    stats = {"total": 0, "saved": 0, "skipped": 0, "duplicates": 0, "domain": 0, "length": 0, "format": 0, "first": True}
    seen_hashes = set()
    found_keys = set()
    
    mode = "a" if args.append and os.path.exists(args.output) else "w"
    if mode == "a":
        with open(args.output, "rb+") as f_tmp:
            f_tmp.seek(0, 2)
            pos = f_tmp.tell()
            while pos > 0:
                pos -= 1
                f_tmp.seek(pos)
                char = f_tmp.read(1)
                if char == b"]":
                    f_tmp.truncate(pos)
                    stats["first"] = False
                    break
            else:
                mode = "w"

    start_time = time.time()
    
    with open(args.output, mode, encoding="utf-8") as out_f:
        if mode == "w" and args.format != "jsonl":
            out_f.write("[\n")
        
        for rec in stream_loader(args.input):
            stats["total"] += 1
            
            for k in rec.keys(): found_keys.add(k)
            
            instr, inp, output_text = get_text(rec)
            
            if not instr.strip() or not output_text.strip():
                stats["format"] += 1
                stats["skipped"] += 1
                continue
                
            full_text = f"{instr} {inp} {output_text}".lower()

            if args.domain != "nav" and not matches_domain(full_text, args.domain):
                stats["domain"] += 1; stats["skipped"] += 1; continue
            if word_count(output_text) < args.min_output or word_count(instr) < args.min_instr:
                stats["length"] += 1; stats["skipped"] += 1; continue
            if args.require_code and not has_code_block(output_text):
                stats["skipped"] += 1; continue
            if include_words and not all(w in full_text for w in include_words):
                stats["skipped"] += 1; continue
            if exclude_words and any(w in full_text for w in exclude_words):
                stats["skipped"] += 1; continue
            
            if args.remove_dupes:
                key = instr.strip()[:200]
                if key in seen_hashes:
                    stats["duplicates"] += 1; stats["skipped"] += 1; continue
                seen_hashes.add(key)

            if args.format == "messages": res_obj = to_messages(instr, inp, output_text)
            else: res_obj = to_alpaca(instr, inp, output_text)

            if args.format == "jsonl":
                out_f.write(json.dumps(res_obj, ensure_ascii=False) + "\n")
            else:
                if not stats["first"]: out_f.write(",\n")
                out_f.write("  " + json.dumps(res_obj, ensure_ascii=False))
                stats["first"] = False
            
            stats["saved"] += 1
            if (stats["total"] % 1000) == 0:
                print(f"  Apstrādāti: {stats['total']}... (Saglabāti: {stats['saved']})", end="\r")

            if args.max_records > 0 and stats["saved"] >= args.max_records:
                break

        if args.format != "jsonl":
            out_f.write("\n]")

    duration = time.time() - start_time
    print(f"\n\n--- Filtrēšana pabeigta ({duration:.1f}s) ---")
    print(f"Kopā lasīti: {stats['total']}")
    print(f"Saglabāti  : {stats['saved']}")
    print(f"Izlaisti   : {stats['skipped']}")
    print(f"  - Dublejumi: {stats['duplicates']}")
    print(f"  - Domens   : {stats['domain']}")
    print(f"  - Garums   : {stats['length']}")
    print(f"  - Formāts  : {stats['format']} (tukši lauki)")
    
    if stats["saved"] == 0 and stats["total"] > 0:
        print(f"\nBRĪDINĀJUMS: Neviens ieraksts netika saglabāts!")
        print(f"Failā atrastie lauki (keys): {list(found_keys)}")
        print(f"Pārbaudiet, vai skripts prot nolasīt šos laukus (get_text funkcija).")
    
    size_mb = os.path.getsize(args.output) / 1024 / 1024
    print(f"\nFAILS SAGLABĀTS: {os.path.abspath(args.output)} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()
