"""Locate table geometry loss between the source, unhwp JSON export and Markdown."""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import tempfile

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

from corpus import sha256
from dll_batch import Extractor
from public_benchmark import FILES
from table_audit import original, placed_table, rendered_table


def json_tables(doc):
    stack = list(doc["sections"])
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if set(node) == {"Table"}:
                rows = node["Table"]["rows"]
                yield placed_table([[(c["rowspan"], c["colspan"], "") for c in r["cells"]] for r in rows])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def inspect(tools, source, *, cli=None, library=None, review_view=False, preserve_tables=False):
    if sha256(source) != FILES[source.name]:
        raise ValueError("input hash differs")
    source_tables, _, metadata = original(source, review_view=review_view)
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "export.json"
        subprocess.run([cli or tools / "unhwp/unhwp.exe", "json", "--no-update-check", "--cleanup", "none",
                        source, "-o", target], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        exported = json.loads(target.read_text(encoding="utf-8"))
    md = Extractor(library or tools / "ffi/unhwp.dll", merged_html=not preserve_tables,
                   preserve_tables=preserve_tables).markdown(source)
    soup = BeautifulSoup(MarkdownIt("commonmark", {"html": True}).enable("table").render(md.decode("utf-8")),
                         "html.parser")
    stages = {"source": source_tables, "json": list(json_tables(exported)),
              "markdown": [rendered_table(t) for t in soup.find_all("table")]}
    geometry = {stage: Counter(t.geometry() for t in tables) for stage, tables in stages.items()}
    targets = []
    for idx, table in enumerate(source_tables, 1):
        if (table.rows, table.columns) == (24, 24):
            targets.append({"source_table_ordinal": idx, "rows": table.rows, "columns": table.columns,
                            "cells": len(table.cells), "matching_geometry":
                                {s: counts[table.geometry()] for s, counts in geometry.items()}})
    return {"input_sha256": sha256(source), "reference_storage": metadata.get("hwp_storage"),
            "section_count_json": len(exported["sections"]),
            "skipped_sections_json": len(exported["skipped_sections"]),
            "table_counts": {s: len(t) for s, t in stages.items()},
            "source_geometry_matches": {s: (geometry["source"] & count).total() for s, count in geometry.items()},
            "targets": targets}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tools", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--library", type=Path)
    parser.add_argument("--review-view", action="store_true")
    parser.add_argument("--preserve-tables", action="store_true")
    args = parser.parse_args()
    data = inspect(args.tools.resolve(), args.source.resolve(), cli=args.cli, library=args.library,
                   review_view=args.review_view, preserve_tables=args.preserve_tables)
    with args.result.open("x", encoding="utf-8") as out:
        print(json.dumps(data, indent=2), file=out)
