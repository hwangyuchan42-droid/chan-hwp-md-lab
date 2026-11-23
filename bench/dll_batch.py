"""PHASE 1 throughput probe for the official unhwp 0.24.0 Windows DLL."""

import argparse
import ctypes
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


class Extractor:
    def __init__(self, library, *, merged_html=False, preserve_tables=False):
        self.dll = ctypes.CDLL(str(library.resolve()))
        self.render_options = None
        if merged_html:
            self.render_options = b'{"table_fallback":"html"}'
        if preserve_tables:
            self.render_options = b'{"table_fallback":"preserve"}'
        ptr = ctypes.c_void_p
        for name, arguments, result in [
            ("unhwp_parse_file", [ctypes.c_char_p], ptr),
            ("unhwp_to_markdown", [ptr, ctypes.c_uint32], ptr),
            ("unhwp_to_markdown_with_options", [ptr, ctypes.c_char_p], ptr),
            ("unhwp_free_string", [ptr], None),
            ("unhwp_free_document", [ptr], None),
            ("unhwp_last_error_kind", [], ctypes.c_int),
        ]:
            function = getattr(self.dll, name)
            function.argtypes = arguments
            function.restype = result

    def markdown(self, path):
        document = self.dll.unhwp_parse_file(str(path).encode("utf-8"))
        if not document:
            raise ValueError(f"parse error {self.dll.unhwp_last_error_kind()}")
        try:
            if self.render_options:
                string = self.dll.unhwp_to_markdown_with_options(document, self.render_options)
            else:
                string = self.dll.unhwp_to_markdown(document, 0)
            if not string:
                kind = self.dll.unhwp_last_error_kind()
                raise ValueError(f"render error {kind}" +
                                 (" (preserve mode requires the patched DLL)"
                                  if self.render_options == b'{"table_fallback":"preserve"}' else ""))
            try:
                return ctypes.string_at(string)
            finally:
                self.dll.unhwp_free_string(string)
        finally:
            self.dll.unhwp_free_document(document)


def run(library, source, output, workers, *, merged_html=False, preserve_tables=False):
    # A benchmark invocation owns a fresh output directory. It never replaces existing files.
    output.mkdir()
    engine = Extractor(library, merged_html=merged_html, preserve_tables=preserve_tables)

    def convert(path):
        data = engine.markdown(path)
        with (output / (path.name + ".md")).open("xb") as file:
            file.write(data)

    paths = (path for path in source.iterdir() if path.suffix.lower() in {".hwp", ".hwpx"})
    if workers == 1:
        for path in paths:
            convert(path)
    else:
        # Limit submitted work even on Python versions with eager Executor.map.
        from itertools import islice
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while chunk := list(islice(paths, workers * 8)):
                for _ in pool.map(convert, chunk):
                    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("library", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("workers", type=int, choices=[1, 4])
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--merged-html", action="store_true", help="Use HTML tables for merged cells in Markdown")
    modes.add_argument("--preserve-tables", action="store_true", help="Keep every table (patched unhwp DLL)")
    args = parser.parse_args()
    run(args.library, args.source, args.output, args.workers, merged_html=args.merged_html,
        preserve_tables=args.preserve_tables)
