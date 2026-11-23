"""Local audit of table values, spans and body-text order on the fixed public inputs."""

from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath
import re
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt


def normalize(value):
    return "".join(unicodedata.normalize("NFC", value).split())


@dataclass(frozen=True)
class Table:
    rows: int
    columns: int
    cells: tuple  # (row, column, rowspan, colspan, normalized visible text)

    @property
    def merged(self):
        return any(r > 1 or c > 1 for _, _, r, c, _ in self.cells)

    def geometry(self):
        return self.rows, self.columns, tuple(cell[:4] for cell in self.cells)


def source_table(element):
    cells = []
    for cell in element.findall("./{*}tr/{*}tc"):
        addr, span = cell.find("{*}cellAddr"), cell.find("{*}cellSpan")
        value = "".join("".join(t.itertext()) for t in cell.findall("./{*}subList/{*}p/{*}run/{*}t"))
        cells.append((int(addr.get("rowAddr")), int(addr.get("colAddr")), int(span.get("rowSpan")),
                      int(span.get("colSpan")), normalize(value)))
    return Table(int(element.get("rowCnt")), int(element.get("colCnt")), tuple(sorted(cells)))


def section_parts(parts):
    manifest = ET.fromstring(parts["Contents/content.hpf"])
    items = {i.get("id"): i.get("href") for i in manifest.findall(".//{*}manifest/{*}item")}
    sections = []
    for item in manifest.findall(".//{*}spine/{*}itemref"):
        path = PurePosixPath(items[item.get("idref")])
        if re.fullmatch(r"section\d+\.xml", path.name):
            key = str(path) if str(path) in parts else str(PurePosixPath("Contents") / path)
            sections.append(ET.fromstring(parts[key]))
    if not sections:
        raise ValueError("missing body sections in OPF spine")
    return sections


def original(path, *, review_view=False):
    """Read the HWPX XML or an independent record decoder's representation of HWP."""
    binary_geometry = None
    if path.suffix == ".hwp":
        from hwpx.hwp5 import records
        from hwpx.hwp5.controls import CellHeader, TableProps
        from hwpx.hwp5.reader import read_hwp5
        from hwpx.hwp5.section_xml import ConversionReport, build_section, table_lists

        source = read_hwp5(path.read_bytes())
        use_review_view = review_view and source.notes.get("view_text") == 1
        storage = "ViewText" if use_review_view else "BodyText"
        streams = []
        for index in range(len(source.sections)):
            name = f"{storage}/Section{index}"
            streams.append(records.parse_records(source.stream(name), name))
        metadata = {"format_or_producer": source.header.version_text,
                    "hwp_storage": storage, "change_tracking": source.header.has("track_changes")}
        xml_sections = [ET.fromstring(build_section(stream, ConversionReport())) for stream in streams]
        binary_geometry = []
        for section in streams:
            for ctrl in section.records:
                props = next((x for x in ctrl.children if x.tag == records.TABLE), None)
                if props is None:
                    continue
                grid = TableProps.decode(props.payload)
                _, entries = table_lists(ctrl)
                cells = [CellHeader.decode(header.payload) for header, _ in entries]
                binary_geometry.append((grid.rows, grid.cols, tuple(sorted(
                    (c.row, c.col, c.row_span, c.col_span) for c in cells))))
    else:
        with ZipFile(path) as z:
            parts = {n: z.read(n) for n in z.namelist() if n == "Contents/content.hpf" or
                     re.fullmatch(r"Contents/section\d+\.xml", n)}
            producer = ET.fromstring(z.read("version.xml"))
            version = producer.get("application", "") + " " + producer.get("appVersion", "")
        metadata = {"format_or_producer": version}
        xml_sections = section_parts(parts)
    tables, body = [], []
    for section in xml_sections:
        for tbl in section.findall(".//{*}tbl"):
            if tbl.find(".//{*}tbl") is not None:
                raise ValueError("nested tables require a separate reference")
            tables.append(source_table(tbl))
        for p in section.findall("./{*}p"):
            if p.find(".//{*}tbl") is None:
                text = normalize("".join("".join(t.itertext()) for t in p.findall("./{*}run/{*}t")))
                if text:
                    body.append(text)
    if binary_geometry is not None and binary_geometry != [t.geometry() for t in tables]:
        raise ValueError("HWP binary cell positions disagree with the XML reference")
    return tables, body, {"sections": len(xml_sections), **metadata}


def placed_table(rows):
    """Assign logical columns across HTML/JSON rows, including earlier rowspans."""
    cells, occupied = [], set()
    columns = 0
    for row, row_cells in enumerate(rows):
        col = 0
        for rs, cs, text in row_cells:
            while (row, col) in occupied:
                col += 1
            cells.append((row, col, rs, cs, text))
            for y in range(row, row + rs):
                for x in range(col, col + cs):
                    occupied.add((y, x))
            col += cs
            columns = max(columns, col)
    return Table(len(rows), columns, tuple(cells))


def rendered_table(element):
    rows = [r for r in element.find_all("tr") if r.find_parent("table") is element]
    return placed_table([[(int(td.get("rowspan", 1)), int(td.get("colspan", 1)), normalize(td.get_text()))
                          for td in tr.find_all(["th", "td"], recursive=False)] for tr in rows])


def grade(reference, markdown):
    tables, body, _ = reference
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    soup = BeautifulSoup(parser.render(markdown.decode("utf-8-sig")), "html.parser")
    elements = soup.find_all("table")
    output = [rendered_table(element) for element in elements]
    for element in elements:
        element.decompose()
    stream = normalize(soup.get_text())
    cursor = found = 0
    for text in body:
        index = stream.find(text, cursor)
        if index >= 0:
            found += 1
            cursor = index + len(text)
    exact = Counter(tables) & Counter(output)
    geometry = Counter(t.geometry() for t in tables) & Counter(t.geometry() for t in output)
    return {"output_tables": len(output), "table_geometry": geometry.total(),
            "table_values_and_geometry": exact.total(),
            "merged_values_and_geometry": sum(n for t, n in exact.items() if t.merged),
            "all_tables_in_order": tables == output, "ordered_body_texts": found}
