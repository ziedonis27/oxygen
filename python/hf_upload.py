#!/usr/bin/env python3
"""
HuggingFace augšuplāde — augšuplādē datasetu uz HF Hub.

Lietošana:
    python hf_upload.py --input fails.json --repo username/dataset-name --token hf_xxx

Nepieciešams:
    pip install huggingface_hub datasets
"""
import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="HuggingFace augšuplāde")
    parser.add_argument("--input",   required=True)
    parser.add_argument("--repo",    required=True, help="HF repo: username/dataset-name")
    parser.add_argument("--token",   required=True, help="HF API token: hf_xxx")
    parser.add_argument("--private", action="store_true", default=False)
    parser.add_argument("--branch",  default="main")
    parser.add_argument("--message", default="Upload via Oxygen ML Dataset Manager")
    args = parser.parse_args()

    # Pārbauda importus
    try:
        from huggingface_hub import HfApi, create_repo, RepoCard
    except ImportError:
        print("Kļūda: trūkst 'huggingface_hub' bibliotēka.")
        print("Instalējiet: pip install huggingface_hub")
        sys.exit(1)

    if not os.path.exists(args.input):
        print(f"Kļūda: fails nav atrasts: {args.input}")
        sys.exit(1)

    filename = os.path.basename(args.input)
    size_mb  = os.path.getsize(args.input) / 1024 / 1024

    print(f"Fails   : {filename} ({size_mb:.2f} MB)")
    print(f"Repo    : {args.repo}")
    print(f"Privāts : {'Jā' if args.private else 'Nē'}")
    print(f"Zars    : {args.branch}")
    print("Savienojas ar HuggingFace...")
    sys.stdout.flush()

    api = HfApi(token=args.token)

    # Izveido repo ja neeksistē
    try:
        create_repo(
            repo_id=args.repo,
            repo_type="dataset",
            private=args.private,
            token=args.token,
            exist_ok=True,
        )
        print(f"Repo gatavs: https://huggingface.co/datasets/{args.repo}")
    except Exception as e:
        print(f"Repo kļūda: {e}")
        sys.exit(1)

    # Augšuplādē failu
    print(f"Augšuplādē {filename}...")
    sys.stdout.flush()

    try:
        url = api.upload_file(
            path_or_fileobj=args.input,
            path_in_repo=filename,
            repo_id=args.repo,
            repo_type="dataset",
            commit_message=args.message,
            token=args.token,
        )
        print(f"\n✅ Veiksmīgi augšuplādēts!")
        print(f"URL : https://huggingface.co/datasets/{args.repo}")
        print(f"Fails: {filename}")
        print(f"Izmērs: {size_mb:.2f} MB")
        print("Pabeigts!")
    except Exception as e:
        print(f"Augšuplādes kļūda: {e}")
        sys.exit(1)

    sys.stdout.flush()


if __name__ == "__main__":
    main()
