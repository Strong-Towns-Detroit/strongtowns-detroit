#!/usr/bin/env python3
"""Compile, validate, and serve the legal-language review application."""

from __future__ import annotations

import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import build_data


ROOT = Path(__file__).resolve().parent
WATCHED = [
    *build_data.ALL_EXAMPLES,
    build_data.REPLIES,
    Path(__file__).with_name("build_data.py"),
]
LOCK = threading.Lock()
last_built_ns = 0


def latest_source_ns() -> int:
    return max(path.stat().st_mtime_ns for path in WATCHED if path.exists())


def ensure_compiled() -> None:
    global last_built_ns
    with LOCK:
        newest = latest_source_ns()
        if last_built_ns >= newest and build_data.OUTPUT.exists():
            return
        build_data.main()
        last_built_ns = max(newest, build_data.OUTPUT.stat().st_mtime_ns)


class CompilingHandler(SimpleHTTPRequestHandler):
    """Recompile changed DSL sources before returning any review artifact."""

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        try:
            ensure_compiled()
        except Exception as error:  # surface compiler failure in the browser
            self.send_error(500, f"Zoning compiler validation failed: {error}")
            return
        super().do_GET()


def main() -> None:
    os.chdir(ROOT)
    ensure_compiled()
    server = ThreadingHTTPServer(("", 8766), CompilingHandler)
    print("review tool: http://localhost:8766/")
    server.serve_forever()


if __name__ == "__main__":
    main()
