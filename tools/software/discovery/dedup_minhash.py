import os
import re
import json
import argparse
from datasketch import MinHash, MinHashLSH


def tokenize(text):
    text = text.lower()
    text = re.sub(r'#.*', '', text)  # python comments
    text = re.sub(r'//.*', '', text)  # js/ts/c/cpp comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)  # block comments
    text = re.sub(r'\s+', '', text)  # remove all whitespace
    # N-gram tokenization
    n = 5
    return [text[i:i+n] for i in range(len(text)-n+1)] if len(text) > n else [text]


def _process_file_for_dedup(path, lsh, hashes, num_perm):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return

    tokens = tokenize(content)
    if not tokens:
        return

    m = MinHash(num_perm=num_perm)
    for token in tokens:
        m.update(token.encode('utf-8'))

    lsh.insert(path, m)
    hashes[path] = m


def run_dedup(target_dir, threshold=0.9, num_perm=128):
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    hashes = {}

    extensions = {'.py', '.js', '.ts', '.java', '.cs', '.cpp', '.c', '.go', '.rb', '.php', '.rs'}

    for root, dirs, files in os.walk(target_dir):
        # Skip typical ignore dirs
        dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', 'venv', '__pycache__', 'dist', 'build'}]
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in extensions:
                path = os.path.join(root, file)
                _process_file_for_dedup(path, lsh, hashes, num_perm)

    clusters = []
    seen = set()
    for path, m in hashes.items():
        if path in seen:
            continue
        result = lsh.query(m)
        if len(result) > 1:
            clusters.append(result)
            seen.update(result)

    return clusters


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Deduplicate code files using MinHash/LSH.')
    parser.add_argument('path', help='Path to scan')
    parser.add_argument('--threshold', type=float, default=0.9, help='Similarity threshold (0.0 to 1.0)')
    parser.add_argument('--out', default='dedup_report.json', help='Output JSON file')
    args = parser.parse_args()

    print(f"Scanning {args.path} for clones (threshold={args.threshold})...")
    clusters = run_dedup(args.path, threshold=args.threshold)

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump({'threshold': args.threshold, 'clusters': clusters}, f, indent=2)

    print(f"Found {len(clusters)} clusters of duplicate/similar files.")
    print(f"Report saved to {args.out}")
