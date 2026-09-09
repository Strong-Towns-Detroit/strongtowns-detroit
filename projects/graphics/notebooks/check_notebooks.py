"""Execute the examples in fresh kernels; never save output into source notebooks.

Run with the optional tools documented in README.md. This is an integration
check against prepared pinned data, not part of the offline unit-test suite.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient import NotebookClient


def main() -> int:
    folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebooks", nargs="*", help="Optional filenames to check; default: all notebooks.")
    args = parser.parse_args()
    available = {path.name: path for path in folder.glob("*.ipynb")}
    if any(name not in available for name in args.notebooks):
        parser.error("Choose notebook filenames from this directory.")
    paths = [available[name] for name in args.notebooks] if args.notebooks else sorted(available.values())
    output = folder.parent / "output/notebook-checks"
    output.mkdir(parents=True, exist_ok=True)
    failures = []
    # Use precisely the interpreter running this check, including uv's overlay.
    # Register the kernel in a temporary directory, not the user's Jupyter setup.
    with tempfile.TemporaryDirectory(prefix="strongtowns-notebook-kernel-") as temp:
        kernel = Path(temp) / "kernels/strongtowns-check"
        kernel.mkdir(parents=True)
        (kernel / "kernel.json").write_text(json.dumps({
            "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Strong Towns notebook check", "language": "python",
        }))
        previous = os.environ.get("JUPYTER_PATH")
        os.environ["JUPYTER_PATH"] = os.pathsep.join(filter(None, [temp, previous]))
        try:
            for path in paths:
                print(f"Running {path.name}", flush=True)
                notebook = nbformat.read(path, as_version=4)
                nbformat.validate(notebook)
                try:
                    NotebookClient(
                        notebook, timeout=900, kernel_name="strongtowns-check",
                        resources={"metadata": {"path": str(folder)}},
                    ).execute()
                except Exception as error:
                    failures.append(path.name)
                    print(f"FAILED {path.name}: {error}", flush=True)
                else:
                    print(f"Passed {path.name}", flush=True)
                nbformat.write(notebook, output / path.name)
        finally:
            if previous is None:
                os.environ.pop("JUPYTER_PATH", None)
            else:
                os.environ["JUPYTER_PATH"] = previous
    if failures:
        print("Failed notebooks: " + ", ".join(failures))
        return 1
    print("All selected notebooks passed. Executed copies: " + str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
