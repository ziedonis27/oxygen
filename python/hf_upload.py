#!/usr/bin/env python3
"""
HuggingFace upload — uploads a dataset to HF Hub.

Usage:
    python hf_upload.py --input file.json --repo username/dataset-name --token hf_xxx

Requirements:
    pip install huggingface_hub datasets
"""
import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="HuggingFace upload")
    parser.add_argument("--input",   required=True)
    parser.add_argument("--repo",    required=True, help="HF repo: username/dataset-name")
    parser.add_argument("--token",   required=True, help="HF API token: hf_xxx")
    parser.add_argument("--private", action="store_true", default=False)
    parser.add_argument("--branch",  default="main")
    parser.add_argument("--message", default="Upload via Oxygen ML Dataset Manager")
    args = parser.parse_args()

    # Check imports
    try:
        from huggingface_hub import HfApi, create_repo, RepoCard
    except ImportError:
        print("Error: missing 'huggingface_hub' library.")
        print("Install: pip install huggingface_hub")
        sys.exit(1)

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}")
        sys.exit(1)

    filename = os.path.basename(args.input)
    size_mb  = os.path.getsize(args.input) / 1024 / 1024

    print(f"File    : {filename} ({size_mb:.2f} MB)")
    print(f"Repo    : {args.repo}")
    print(f"Private : {'Yes' if args.private else 'No'}")
    print(f"Branch  : {args.branch}")
    print("Connecting to HuggingFace...")
    sys.stdout.flush()

    api = HfApi(token=args.token)

    # Create repo if it doesn't exist
    try:
        create_repo(
            repo_id=args.repo,
            repo_type="dataset",
            private=args.private,
            token=args.token,
            exist_ok=True,
        )
        print(f"Repo ready: https://huggingface.co/datasets/{args.repo}")
    except Exception as e:
        print(f"Repo error: {e}")
        sys.exit(1)

    # Upload file
    print(f"Uploading {filename}...")
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
        print(f"\n✅ Successfully uploaded!")
        print(f"URL : https://huggingface.co/datasets/{args.repo}")
        print(f"File: {filename}")
        print(f"Size: {size_mb:.2f} MB")
        print("Done!")
    except Exception as e:
        print(f"Upload error: {e}")
        sys.exit(1)

    sys.stdout.flush()


if __name__ == "__main__":
    main()
