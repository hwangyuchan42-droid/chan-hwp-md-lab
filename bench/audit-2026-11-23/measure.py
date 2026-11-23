"""Re-score fixed historical converters and time the same two-file mixed batch."""

import argparse
from collections import defaultdict
import hashlib
from importlib.metadata import version
import json
import platform
from pathlib import Path
import re
import shutil
from statistics import median
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public_benchmark import FILES, invocation
from table_audit import grade


ARMS = ("dll-html", "dll-preserve", "unhwp", "unhwp-html", "hwp2md", "kordoc-4", "kordoc-html")
TIMED = ARMS[:5]  # Exactly five cyclic rotations.
HTML_TABLE = re.compile(rb"<table(?=[\s>])[^>]*>.*?</table\s*>", re.S | re.I)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as file:
        print(json.dumps(data, ensure_ascii=False, indent=2), file=file)


def run(arm, tools, source, out, patched):
    statuses, commands = [], []
    start = time.perf_counter()
    for cmd in invocation(arm, tools, source, out, patched):
        result = subprocess.run(cmd, cwd=source, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=180)
        statuses.append(result.returncode)
        commands.append(cmd)
    elapsed = time.perf_counter() - start
    if any(statuses):
        raise RuntimeError(f"{arm}: exit status {statuses}")
    outputs = {}
    for name in FILES:
        stem = name if arm.startswith(("dll", "unhwp")) else Path(name).stem
        outputs[name] = (out / (stem + ".md")).read_bytes()
    if len(list(out.glob("*.md"))) != len(FILES):
        raise RuntimeError(f"{arm}: unexpected number of Markdown files")
    return {"arm": arm, "elapsed_seconds": elapsed, "exit_codes": statuses,
            "commands": [[str(part) for part in cmd] for cmd in commands],
            "output_sha256": {n: sha(b) for n, b in outputs.items()}}, outputs


def sizes(data):
    html = HTML_TABLE.findall(data)
    marker_count = len(re.findall(rb"<table(?=[\s>])", data, re.I))
    if marker_count != len(html):
        raise ValueError("unpaired or nested HTML table in this fixed output")
    html_bytes = sum(map(len, html))
    return {"bytes": len(data), "html_tables": len(html), "html_table_block_bytes": html_bytes,
            "html_table_block_percent": round(100 * html_bytes / len(data), 6)}


def historic(bench):
    history = {}
    for slug in ("2026-11-23-public-isolated", "2026-11-23-final-body"):
        path = bench / "results" / (slug + ".jsonl")
        raw = path.read_bytes()
        header, *lines = [json.loads(line) for line in raw.splitlines()]
        groups = defaultdict(list)
        output_hashes = defaultdict(set)
        order = defaultdict(list)
        for row in lines:
            if row["case"] == "mixed":
                groups[row["arm"]].append(row["seconds"])
                order[row["round"]].append(row["arm"])
                output_hashes[row["arm"]].add(tuple(g["sha256"] for g in row["grades"].values()))
        history[slug] = {"sha256": sha(raw), "tool_hashes": header["tools"], "order": dict(order),
                         "seconds": dict(groups), "medians": {a: median(v) for a, v in groups.items()},
                         "output_hashes": {a: sorted(v) for a, v in output_hashes.items()}}
    return history


def main():
    parser = argparse.ArgumentParser()
    for name in ("tools", "inputs", "evidence"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    tools, inputs = args.tools.resolve(), args.inputs.resolve()
    patched = tools / "unhwp-table-target/release/unhwp.dll"
    binaries = [sys.executable, shutil.which("node"), tools / "unhwp/unhwp.exe",
                tools / "ffi/unhwp.dll", patched, tools / "hwp2md-target/release/hwp2md.exe",
                tools / "node_modules/kordoc/dist/cli.js",
                Path(__file__).resolve().parents[1] / "dll_batch.py",
                Path(__file__).resolve().parents[1] / "public_benchmark.py",
                Path(__file__).resolve().parents[1] / "baseline.py",
                Path(__file__).resolve().parents[1] / "table_audit.py", Path(__file__).resolve()]
    bench = Path(__file__).resolve().parents[1]
    info = {"platform": platform.platform(), "temp_directory": tempfile.gettempdir(),
            "processor": platform.processor(), "python": platform.python_version(),
            "packages": {n: version(n) for n in ("beautifulsoup4", "markdown-it-py", "python-hwpx", "lxml")},
            "files": {str(p): sha(Path(p).read_bytes()) for p in binaries}}
    history = historic(bench)
    rows = []
    with tempfile.TemporaryDirectory(prefix="hwp-audit-") as folder:
        parent = Path(folder)
        source = parent / "inputs"
        source.mkdir()
        for n, digest in FILES.items():
            shutil.copyfile(inputs / n, source / n)
            assert sha((source / n).read_bytes()) == digest
        # Complete all timed rounds first. Parsing and scoring the reference cannot affect their order.
        for turn in range(len(TIMED)):
            for arm in TIMED[turn:] + TIMED[:turn]:
                row, _ = run(arm, tools, source, parent / f"time-{turn + 1}-{arm}", patched)
                rows.append({"round": turn + 1, **row})
        dump(args.evidence / "timings.json", {"environment": info, "inputs": FILES,
             "history": history, "runs": rows})
        # Re-run each arm for grading and verify identity with all corresponding timed outputs.
        from table_audit import original
        refs = {
            "review": {n: original(source / n, review_view=True) for n in FILES},
            "final": {n: original(source / n, review_view=False) for n in FILES},
        }
        checks = []
        for arm in ARMS:
            row, outputs = run(arm, tools, source, parent / f"quality-{arm}", patched)
            for timed in rows:
                if timed["arm"] == arm:
                    assert timed["output_sha256"] == row["output_sha256"]
            checks.append({"arm": arm, "commands": row["commands"], "exit_codes": row["exit_codes"],
                           "sha256": row["output_sha256"], "sizes": {n: sizes(b) for n, b in outputs.items()},
                           "grades": {key: {n: grade(ref[n], data) for n, data in outputs.items()}
                                      for key, ref in refs.items()}})
    for n, digest in FILES.items():
        assert sha((inputs / n).read_bytes()) == digest
    dump(args.evidence / "scores.json", {"inputs": FILES, "runs": checks})
    for arm in TIMED:
        print(arm, "median", f"{median(r['elapsed_seconds'] for r in rows if r['arm'] == arm):.6f}")
    for row in checks:
        grades = row["grades"]
        print(row["arm"], {c: {f: (g["table_values_and_geometry"], g["ordered_body_texts"])
                              for f, g in v.items()} for c, v in grades.items()})


if __name__ == "__main__":
    main()
