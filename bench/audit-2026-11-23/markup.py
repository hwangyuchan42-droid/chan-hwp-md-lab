"""Measure HTML table markup without retaining any source or converted text."""

from pathlib import Path
import argparse
import json
import re
import shutil
import tempfile

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from measure import FILES, HTML_TABLE, dump, run, sizes
from table_audit import rendered_table


STRUCTURAL_TAG = re.compile(rb"</?(?:table|thead|tbody|tfoot|tr|th|td|caption|colgroup|col)\b[^>]*>", re.I)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("tools", "inputs", "evidence"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    patched = args.tools / "unhwp-table-target/release/unhwp.dll"
    expected = json.loads((args.evidence / "scores.json").read_text(encoding="utf-8"))
    hashes = {row["arm"]: row["sha256"] for row in expected["runs"]}
    stats = []
    engine = MarkdownIt("commonmark", {"html": True}).enable("table")
    with tempfile.TemporaryDirectory(prefix="hwp-markup-audit-") as folder:
        parent = Path(folder)
        source = parent / "inputs"
        source.mkdir()
        for name in FILES:
            shutil.copyfile(args.inputs / name, source / name)
        for arm in ("dll-html", "dll-preserve"):
            row, outputs = run(arm, args.tools, source, parent / arm, patched)
            assert row["output_sha256"] == hashes[arm]
            for name, data in outputs.items():
                tag_count = sum(len(m) for block in HTML_TABLE.findall(data)
                                for m in STRUCTURAL_TAG.findall(block))
                soup = BeautifulSoup(engine.render(data.decode("utf-8-sig")), "html.parser")
                tables = [rendered_table(table) for table in soup.find_all("table")]
                stats.append({"arm": arm, "name": name, "sha256": row["output_sha256"][name],
                              **sizes(data), "html_structural_tag_bytes": tag_count,
                              "html_structural_tag_percent": round(100 * tag_count / len(data), 6),
                              "rendered_1_by_1": sum(t.rows == t.columns == 1 for t in tables)})
    dump(args.evidence / "markup.json", stats)
    for row in stats:
        print(row)
