"""Compare the two published JSONL ledgers to their pre-redaction copies."""

import argparse
import hashlib
import json
from pathlib import Path

FILES = ("2026-11-22.jsonl", "2026-11-23-mixed.jsonl")
REDACTED = ("logical_cpus", "ram_bytes")


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse(data):
    return [json.loads(line, object_pairs_hook=unique_keys)
            for line in data.decode("utf-8").splitlines()]


def differences(before, after):
    if type(before) is not type(after):
        return 1
    if isinstance(before, dict):
        keys = before.keys() & after.keys()
        return len(before.keys() ^ after.keys()) + sum(differences(before[k], after[k]) for k in keys)
    if isinstance(before, list):
        return abs(len(before) - len(after)) + sum(differences(a, b) for a, b in zip(before, after))
    return int(before != after)


def compare(name, original_dir, public_dir):
    before = (original_dir / name).read_bytes()
    after = (public_dir / name).read_bytes()
    original, public = parse(before), parse(after)
    if not original or original[0].get("type") != "inventory":
        raise ValueError("first record is not an inventory")
    for key in REDACTED:
        del original[0][key]
    changed = differences(original, public)
    bytes_changed = sum(b != a for b, a in zip(before.splitlines()[1:], after.splitlines()[1:]))
    if changed or bytes_changed:
        raise ValueError(f"{name}: {changed} unexpected JSON changes, {bytes_changed} changed non-header lines")
    return (hashlib.sha256(before).hexdigest(), hashlib.sha256(after).hexdigest(),
            len(public), changed, bytes_changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_dir", type=Path)
    parser.add_argument("public_dir", type=Path, nargs="?",
                        default=Path(__file__).resolve().parents[1] / "bench" / "results")
    args = parser.parse_args()
    for name in FILES:
        before, after, rows, changes, bytes_changed = compare(name, args.original_dir, args.public_dir)
        print(name)
        print(f"  before SHA-256: {before}")
        print(f"  after  SHA-256: {after}")
        print(f"  deleted keys in row 1: {', '.join(REDACTED)}")
        print(f"  JSON rows: {rows}; other JSON changes: {changes}; data lines changed: {bytes_changed}")


if __name__ == "__main__":
    main()
