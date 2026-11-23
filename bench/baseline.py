"""Compare finished Markdown files on a fixed synthetic corpus, on Windows."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import psutil
from markdown_it import MarkdownIt

from corpus import expected, sha256


PARSER = MarkdownIt("commonmark").enable("table")
ARMS = ("unhwp", "hwp2md", "kordoc-1", "kordoc-4", "dll-1", "dll-4")
CASES = {
    "hwp": (24, ("body.hwp", "table.hwp")),
    "hwpx": (24, ("body.hwpx", "table.hwpx")),
    "long-hwp": (8, ("long.hwp",)),
    "long-hwpx": (8, ("long.hwpx",)),
    "mixed-1000": (1000, ("body.hwp", "table.hwp", "body.hwpx", "table.hwpx")),
}


def read_blocks(data):
    blocks = []
    context = None
    for token in PARSER.parse(data.decode("utf-8-sig")):
        kind = token.type
        if kind == "paragraph_open":
            context = "p"
        elif kind == "table_open":
            blocks.append(["table", []])
        elif kind == "tr_open":
            blocks[-1][1].append([])
        elif kind in ("th_open", "td_open"):
            context = "cell"
        elif kind == "inline":
            if any(child.type != "text" for child in token.children):
                raise ValueError("unexpected inline markup")
            value = "".join(child.content for child in token.children)
            if context == "p":
                blocks.append(["p", value])
            elif context == "cell":
                blocks[-1][1][-1].append(value)
            else:
                raise ValueError("unexpected text position")
        elif kind in ("paragraph_close", "td_close", "th_close"):
            context = None
        elif kind not in ("thead_open", "thead_close", "tbody_open", "tbody_close",
                          "table_close", "tr_close"):
            raise ValueError("unexpected block: " + kind)
    return blocks


def materialize(source, fixtures, case):
    source.mkdir()
    count, patterns = CASES[case]
    inputs = {}
    for i in range(count):
        pattern = patterns[i % len(patterns)]
        name = f"d{i:05}" + Path(pattern).suffix
        shutil.copyfile(fixtures / pattern, source / name)
        inputs[name] = pattern
    return inputs


def commands(arm, tools, source, output):
    if arm == "hwp2md":
        yield [tools / "hwp2md-target/release/hwp2md.exe", "batch", source, "-o", output]
    elif arm.startswith("dll-"):
        yield [sys.executable, Path(__file__).with_name("dll_batch.py").resolve(),
               tools / "ffi/unhwp.dll", source, output, arm.split("-")[1]]
    else:
        output.mkdir()
        names = sorted(p.name for p in source.iterdir())
        if arm == "unhwp":
            for name in names:
                yield [tools / "unhwp/unhwp.exe", "markdown", "--no-update-check", "--cleanup", "none", name,
                       "-o", output / (name + ".md")]
        else:
            yield ["node", tools / "node_modules/kordoc/dist/cli.js", "--format", "markdown",
                   "--table-format", "gfm", "--no-images", "--jobs", arm.split("-")[1],
                   "-d", output, *names]


def quality(output, inputs, arm):
    # A repeated output is reusable for scoring only when its bytes and its answer key match.
    cache = {}
    expected_names = set()
    passed = 0
    errors = Counter()
    sample = {}
    for name, pattern in inputs.items():
        stem = Path(name).stem
        filename = (name if arm == "unhwp" or arm.startswith("dll-") else stem) + ".md"
        expected_names.add(filename)
        file = output / filename
        if not file.is_file():
            errors["missing"] += 1
            continue
        data = file.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        key = (pattern, digest)
        if key not in cache:
            try:
                valid = read_blocks(data) == expected(Path(pattern).stem)
                reason = "pass" if valid else "paragraph/table mismatch"
            except (ValueError, IndexError) as error:
                reason = str(error)
            cache[key] = reason
        sample.setdefault(pattern, {"output_sha256": digest, "grade": cache[key]})
        if cache[key] == "pass":
            passed += 1
        else:
            errors[cache[key]] += 1
    extra = {f.name for f in output.glob("*.md")} - expected_names
    return {"passed": passed, "errors": dict(errors), "extra_outputs": len(extra), "examples": sample}


def sample_memory(stop, peak):
    parent = psutil.Process()
    while not stop.is_set():
        total = 0
        for child in parent.children(recursive=True):
            try:
                total += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        peak[0] = max(peak[0], total)
        stop.wait(0.02)


def measure(arm, tools, source, output, inputs, telemetry):
    peak = [0]
    stop = threading.Event()
    monitor = threading.Thread(target=sample_memory, args=(stop, peak)) if telemetry else None
    if monitor:
        monitor.start()
    exit_codes = Counter()
    try:
        start = time.perf_counter()
        for cmd in commands(arm, tools, source, output):
            result = subprocess.run(cmd, cwd=source, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, timeout=300)
            exit_codes[str(result.returncode)] += 1
            if result.returncode and len(inputs) <= 24:
                print(result.stderr.decode("utf-8", "replace")[-350:], file=sys.stderr)
        elapsed = time.perf_counter() - start
    finally:
        stop.set()
        if monitor:
            monitor.join()
    return {"seconds": round(elapsed, 6), "exit_codes": dict(exit_codes),
            "sampled_peak_bytes": (peak[0] or None) if telemetry else None,
            **quality(output, inputs, arm)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tools", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("repetitions must be positive")
    tools = args.tools.resolve()
    fixtures = tools / "fixtures"
    manifest = json.loads((fixtures / "manifest.json").read_text())
    for name, info in manifest.items():
        if sha256(fixtures / name) != info["sha256"]:
            raise ValueError("fixture changed: " + name)
    tools_used = {"unhwp": tools / "unhwp/unhwp.exe", "dll": tools / "ffi/unhwp.dll",
                  "hwp2md": tools / "hwp2md-target/release/hwp2md.exe",
                  "kordoc": tools / "node_modules/kordoc/dist/cli.js",
                  "node": Path(shutil.which("node")), "python": Path(sys.executable),
                  "Cargo.lock": tools / "hwp2md-0.5.0-source/Cargo.lock",
                  "package-lock.json": tools / "package-lock.json"}
    inventory = {k: sha256(p) for k, p in tools_used.items() if p.is_file()}
    args.results.parent.mkdir(parents=True, exist_ok=True)
    with args.results.open("x", encoding="utf-8") as report:
        def emit(record):
            report.write(json.dumps(record, ensure_ascii=False) + "\n")
            report.flush()
        emit({"type": "inventory", "fixtures": manifest, "tools_sha256": inventory,
              "python": sys.version.split()[0], "node": subprocess.check_output(
                  ["node", "--version"], text=True).strip(),
              "logical_cpus": os.cpu_count(), "ram_bytes": psutil.virtual_memory().total})
        with tempfile.TemporaryDirectory(prefix="hwp-md-bench-") as scratch:
            for case in args.cases:
                source = Path(scratch) / case
                inputs = materialize(source, fixtures, case)
                total_bytes = sum(manifest[p]["bytes"] for p in inputs.values())
                counts = dict(Counter(inputs.values()))
                for turn in range(args.repetitions + 1):
                    shift = turn % len(args.arms)
                    for arm in args.arms[shift:] + args.arms[:shift]:
                        with tempfile.TemporaryDirectory(dir=scratch) as temp:
                            result = measure(arm, tools, source, Path(temp) / "out", inputs, turn == 0)
                        emit({"case": case, "arm": arm, "round": turn, "counts": counts,
                              "input_bytes": total_bytes, **result})
                print(case, "complete", flush=True)


if __name__ == "__main__":
    main()
