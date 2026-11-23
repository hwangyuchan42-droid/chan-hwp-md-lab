"""Collect binary stream evidence and reconcile the two reference sets."""

import argparse
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
import re
import struct
import sys
from xml.etree import ElementTree as ET
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hwpx.hwp5 import records
from hwpx.hwp5.cfb import CompoundFile
from hwpx.hwp5.controls import TableProps
from hwpx.hwp5.fileheader import parse_file_header
from hwpx.hwp5.section_xml import build_section, ConversionReport
from measure import dump, FILES, sha
from table_audit import normalize, original, source_table


def tag(element):
    return element.tag.rsplit("}", 1)[-1]


def text_of(paragraph):
    return "".join("".join(part.itertext()) for part in paragraph.findall("./{*}run/{*}t"))


def comparison(old, new):
    matches = Counter(old) & Counter(new)
    opcodes = SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
    return {"old": len(old), "new": len(new), "multiset_equal": matches.total(),
            "edits": {name: {"blocks": sum(q == name for q, *_ in opcodes),
                             "old": sum(j - i for q, i, j, x, y in opcodes if q == name),
                             "new": sum(y - x for q, i, j, x, y in opcodes if q == name)}
                      for name in ("equal", "delete", "replace", "insert")},
            "changed_ranges": [
                {"kind": q, "old_one_based_start": i + 1, "old_count": j - i,
                 "new_one_based_start": x + 1, "new_count": y - x}
                for q, i, j, x, y in opcodes if q != "equal"]}


def walk(node, path, active, marks, tables, collected, owner):
    kind = tag(node)
    if kind in ("deleteBegin", "deleteEnd", "insertBegin", "insertEnd"):
        marks[kind] += 1
    if kind == "deleteBegin":
        active[node.get("Id")] = node.get("TcId")
    elif kind == "deleteEnd":
        del active[node.get("Id")]
    elif kind == "tbl":
        tables.append((source_table(node), tuple(active.values()), owner))
    # Same direct paragraph/run/text boundary as the scorer.
    capture = path[:3] == ("p", "run", "t")
    if capture and node.text and not active:
        collected.append(node.text)
    for child in node:
        walk(child, (*path, tag(child)), active, marks, tables, collected, owner)
        if capture and child.tail and not active:
            collected.append(child.tail)


def analyze(compound, paths, compressed):
    tables, xml_body, readout, fragments, neighbors = [], [], [], [], {}
    for name in paths:
        raw = compound.read(name)
        payload = zlib.decompress(raw, -15) if compressed else raw
        stream = records.parse_records(payload, name)
        root = ET.fromstring(build_section(stream, ConversionReport()))
        active = {}
        marks = Counter()
        first_table = len(tables)
        for ordinal, node in enumerate(root, 1):
            visible = []
            owner = name, ordinal
            walk(node, (tag(node),), active, marks, tables, visible, owner)
            if tag(node) == "p" and node.find(".//{*}tbl") is None:
                unfiltered = text_of(node).strip()
                if normalize(unfiltered):
                    neighbors[owner] = unfiltered
                    xml_body.append(normalize(unfiltered))
                    fragments.append(normalize("".join(visible)))
        if active:
            raise ValueError("unmatched deletion mark")
        raw_tables = [TableProps.decode(r.payload) for r in stream.records if r.tag == records.TABLE]
        assert [(t.rows, t.cols) for t in raw_tables] == [(t.rows, t.columns) for t, *_ in tables[first_table:]]
        readout.append({"path": name, "stored_bytes": len(raw), "inflated_bytes": len(payload),
                        "stored_sha256": sha(raw), "inflated_sha256": sha(payload),
                        "records": len(stream.records), "table_records": len(raw_tables),
                        "xml_change_marks": dict(marks)})
    return tables, xml_body, fragments, readout, neighbors


def collect(source):
    data = source.read_bytes()
    assert sha(data) == FILES[source.name]
    compound = CompoundFile(data)
    raw_header = compound.read("FileHeader")
    header = parse_file_header(raw_header)
    compressed = header.compressed
    docinfo = compound.read("DocInfo")
    doc = zlib.decompress(docinfo, -15) if compressed else docinfo
    counts = Counter(r.tag for r in records.parse_records(doc, "DocInfo").records)
    track_counts = {n: {"tag_id": getattr(records, n), "count": counts[getattr(records, n)]}
                    for n in ("TRACKCHANGE", "TRACK_CHANGE", "TRACK_CHANGE_AUTHOR")}
    streams = {}
    for storage in ("ViewText", "BodyText"):
        paths = [p for p in compound.stream_paths() if re.fullmatch(storage + r"/Section\d+", p)]
        paths.sort(key=lambda p: int(p.split("Section")[-1]))
        streams[storage] = analyze(compound, paths, compressed)
    view, view_body, accepted_fragments, view_readout, neighbors = streams["ViewText"]
    body, final_body, _, final_readout, _ = streams["BodyText"]
    assert original(source, review_view=True)[:2] == ([t for t, *_ in view], view_body)
    assert original(source, review_view=False)[:2] == ([t for t, *_ in body], final_body)
    retained = [t for t, markers, _ in view if not markers]
    assert [t.geometry() for t in retained] == [t.geometry() for t, *_ in body]
    removed = [{"view_ordinal": i, "rows": t.rows, "columns": t.columns, "cells": len(t.cells),
                "section": owner[0], "parent_element": owner[1], "deletion_ids": ids,
                "same_geometry_count_in_final": sum(t.geometry() == b.geometry() for b, *_ in body),
                "same_cells_count_in_final": sum(t == b for b, *_ in body)}
               for i, (t, ids, owner) in enumerate(view, 1) if ids]
    common_values = sum(t == b for t, (b, _, _) in zip(retained, body))
    changed = {"empty_after_removing_delete_marked_text": [],
               "nonempty_text_changed": [], "normalized_text_unchanged": []}
    for i, (old, new) in enumerate(zip(view_body, accepted_fragments), 1):
        bucket = ("normalized_text_unchanged" if old == new else
                  "nonempty_text_changed" if new else "empty_after_removing_delete_marked_text")
        changed[bucket].append(i)
    surviving = [(i, text) for i, text in enumerate(accepted_fragments, 1) if text]
    joins = []
    for kind, i, j, x, y in SequenceMatcher(None, [v for _, v in surviving], final_body,
                                             autojunk=False).get_opcodes():
        if kind == "equal":
            continue
        joins.append({"view_ordinals": [ordinal for ordinal, _ in surviving[i:j]],
                      "final_ordinals": list(range(x + 1, y + 1)),
                      "exact_when_joined": "".join(text for _, text in surviving[i:j]) ==
                                           "".join(final_body[x:y])})
    _, _, (stream, ordinal) = view[107]
    prev_index = max(i for name, i in neighbors if name == stream and i < ordinal)
    next_index = min(i for name, i in neighbors if name == stream and i > ordinal)
    prefix = [neighbors[stream, i][:10] for i in (prev_index, next_index)]
    summary = {"source_sha256": sha(data),
               "file_header": {"bytes": len(raw_header), "sha256": sha(raw_header),
                               "format": header.version_text,
                               "properties_le_hex": raw_header[36:40].hex(),
                               "properties_integer_hex": f"0x{struct.unpack_from('<I', raw_header, 36)[0]:08x}",
                               "flags_set": header.flag_names,
                               "flags": {n: header.has(n) for n in
                                         ("compressed", "distribution", "password", "drm",
                                          "cert_encrypted", "cert_drm", "track_changes")},
                               "encrypt_version": header.encrypt_version},
               "docinfo": {"stored_sha256": sha(docinfo), "inflated_sha256": sha(doc),
                           "stored_bytes": len(docinfo), "inflated_bytes": len(doc), "change_tags": track_counts},
               "streams": view_readout + final_readout,
               "tables": {"view": len(view), "final": len(body),
                          "view_1_by_1": sum(t.rows == t.columns == 1 for t, *_ in view),
                          "final_1_by_1": sum(t.rows == t.columns == 1 for t, *_ in body),
                          "retained_geometry_equal_in_order": len(retained),
                          "retained_values_equal_in_order": common_values, "deleted_review_tables": removed},
               "body": {"direct_comparison": comparison(view_body, final_body),
                        "view_paragraph_ordinals_by_marked_text_status": changed,
                        "join_checks": joins,
                        "after_filtering_delete_marked_text":
                            comparison([p for p in accepted_fragments if p], final_body)},
               "table_108_neighbor_locations": {"stream": stream, "table_parent_element": ordinal,
                                                "previous_body_element": prev_index,
                                                "next_body_element": next_index}}
    return summary, prefix


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--report-template", type=Path)
    args = parser.parse_args()
    summary, prefixes = collect(args.source)
    if args.report_template:
        report = args.report_template.read_text(encoding="utf-8")
        for placeholder, prefix in zip(("<PREVIOUS_10>", "<NEXT_10>"), prefixes):
            assert report.count(placeholder) == 1
            report = report.replace(placeholder, prefix.replace("\r", " ").replace("\n", " "))
        with args.destination.open("x", encoding="utf-8", newline="\n") as out:
            out.write(report)
    else:
        dump(args.destination, summary)
        print("header", summary["file_header"])
        print("docinfo", summary["docinfo"])
        for stream in summary["streams"]:
            print("stream", stream)
        for table in summary["tables"]["deleted_review_tables"]:
            print("specific removal", table)
        print("table counts", {k: v for k, v in summary["tables"].items() if k != "deleted_review_tables"})
        print("direct body", summary["body"]["direct_comparison"]["edits"])
        change = summary["body"]["view_paragraph_ordinals_by_marked_text_status"]
        print("marked paragraphs", {k: len(v) for k, v in change.items()})
        print("filtered body", summary["body"]["after_filtering_delete_marked_text"]["edits"])
        print("join checks", summary["body"]["join_checks"])
        print("table 108 lookup positions", summary["table_108_neighbor_locations"])
