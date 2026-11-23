"""Build paired, synthetic fixtures. Run once into a new local directory."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected(kind):
    if kind == "body":
        return [
            ["p", "첫 문단은 가상 관측 안내입니다."],
            ["p", "오전 측정값 12.7도, 오후 측정값 18.3도입니다."],
            ["p", "마지막 문단은 다음 관측 일정을 기록합니다."],
        ]
    if kind == "table":
        return [
            ["p", "가상 물품 수량표를 확인합니다."],
            ["table", [
                ["품목", "개수", "단위"],
                ["파란 연필", "27", "자루"],
                ["검정 펜", "63", "개"],
                ["빈 상자", "", "묶음"],
            ]],
            ["p", "여기까지가 가상 물품 목록입니다."],
        ]
    if kind == "long":
        return [["p", f"가상 관측 기록 {i:04d}번의 수량은 {i * 13 + 7}개입니다."]
                for i in range(1, 501)]
    raise ValueError(kind)


def build(destination):
    from hwpx import HwpxDocument

    destination.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for kind in ("body", "table", "long"):
        doc = HwpxDocument.new()
        for block, value in expected(kind):
            if block == "p":
                doc.add_paragraph(value)
            else:
                table = doc.add_table(len(value), len(value[0]))
                for row, cells in enumerate(value):
                    for column, cell in enumerate(cells):
                        table.cell(row, column).text = cell
        for extension in ("hwp", "hwpx"):
            path = destination / f"{kind}.{extension}"
            doc.save(path)
            manifest[path.name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    build(parser.parse_args().destination)
