"""Measure the two publisher-issued documents. Results contain counts, hashes and times only."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from baseline import commands
from corpus import sha256
from table_audit import grade, original


FILES = {"appendix.hwp": "3b73cc510033920112cf96a01dbd6124e9707fc37b710bbd5608df2d513dcce0",
         "release.hwpx": "93ffd8fbe0a8bcdc5b96cbf9615c4cbb3e614980befccbca2642d2925441a207"}
ARMS = ("unhwp", "hwp2md", "kordoc-4", "dll-4", "kordoc-html", "dll-html", "unhwp-html")


def invocation(arm, tools, source, out, preserve_library):
    base = {"kordoc-html": "kordoc-4", "dll-html": "dll-4", "unhwp-html": "unhwp",
            "dll-preserve": "dll-4"}.get(arm, arm)
    for cmd in commands(base, tools, source, out):
        if arm == "dll-html":
            cmd.append("--merged-html")
        elif arm == "dll-preserve":
            cmd[2] = preserve_library
            cmd.append("--preserve-tables")
        elif arm == "unhwp-html":
            cmd[2:2] = ["--table-mode", "html"]
        elif arm == "kordoc-html":
            i = cmd.index("--table-format")
            cmd[i:i+2] = ["--html-tables", "--keep-layout-tables"]
        yield cmd


def measure(arm, tools, source, out, names, references, cache, preserve_library=None):
    codes = []
    start = time.perf_counter()
    for cmd in invocation(arm, tools, source, out, preserve_library):
        result = subprocess.run(cmd, cwd=source, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=180)
        codes.append(result.returncode)
    seconds = time.perf_counter() - start
    outputs = {}
    for name in names:
        output_name = name if arm.startswith(("dll", "unhwp")) else Path(name).stem
        path = out / (output_name + ".md")
        if not path.is_file():
            outputs[name] = {"missing": True}
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        key = name, digest
        if key not in cache:
            cache[key] = grade(references[name], data)
        outputs[name] = {"sha256": digest, **cache[key]}
    return {"seconds": round(seconds, 6), "exit_codes": codes, "grades": outputs,
            "markdown_files": sum(1 for _ in out.glob("*.md"))}


def main():
    parser = argparse.ArgumentParser()
    for key in ("tools", "inputs", "results"):
        parser.add_argument(key, type=Path)
    parser.add_argument("--review-view", action="store_true",
                        help="Audit the track-changes view, as in the first public-document run")
    parser.add_argument("--preserve-library", type=Path, help="Add the patched DLL's --preserve-tables mode")
    args = parser.parse_args()
    tools = args.tools.resolve()
    references, inventory = {}, {}
    for name, expected_hash in FILES.items():
        path = args.inputs / name
        if sha256(path) != expected_hash:
            raise ValueError(f"source differs: {name}")
        references[name] = original(path, review_view=args.review_view)
        tables, body, info = references[name]
        inventory[name] = {"sha256": expected_hash, "bytes": path.stat().st_size, **info,
                           "tables": len(tables), "cells": sum(len(t.cells) for t in tables),
                           "merged_tables": sum(t.merged for t in tables), "body_texts": len(body)}
    binaries = ["ffi/unhwp.dll", "unhwp/unhwp.exe", "hwp2md-target/release/hwp2md.exe",
                "node_modules/kordoc/dist/cli.js"]
    tool_hashes = {name: sha256(tools / name) for name in binaries}
    preserve_library = args.preserve_library.resolve() if args.preserve_library else None
    arms = ARMS
    if preserve_library:
        tool_hashes["patched unhwp.dll"] = sha256(preserve_library)
        arms += ("dll-preserve",)
    with args.results.open("x", encoding="utf-8") as log, tempfile.TemporaryDirectory() as scratch:
        def emit(record):
            print(json.dumps(record, ensure_ascii=False), file=log, flush=True)

        emit({"type": "inventory", "inputs": inventory, "tools": tool_hashes})
        cache = {}
        for case, names in [("hwp", ["appendix.hwp"]), ("hwpx", ["release.hwpx"]), ("mixed", list(FILES))]:
            source = Path(scratch) / case
            source.mkdir()
            for name in names:
                shutil.copyfile(args.inputs/name, source/name)
            for turn in range(1, 6):
                shift = (turn - 1) % len(arms)
                for arm in arms[shift:] + arms[:shift]:
                    with tempfile.TemporaryDirectory(dir=scratch) as dest:
                        row = measure(arm, tools, source, Path(dest)/"out", names, references, cache,
                                      preserve_library)
                    emit({"case": case, "round": turn, "arm": arm, **row})
            print(case, "complete", flush=True)


if __name__ == "__main__":
    main()
