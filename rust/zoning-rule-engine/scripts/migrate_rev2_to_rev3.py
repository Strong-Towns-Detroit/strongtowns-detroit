#!/usr/bin/env python3
"""Mechanically migrate authored Rev2 rule blocks to the Rev3 three-part form."""

from __future__ import annotations

import argparse
from pathlib import Path


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def migrate_rule(lines: list[str]) -> list[str]:
    if any(line.strip() == "if" and indent_of(line) == 2 for line in lines):
        return lines
    header, *content = lines
    metadata: list[str] = []
    parameters: list[str] = []
    conditions: list[str] = []
    consequents: list[str] = []
    index = 0
    while index < len(content):
        line = content[index]
        stripped = line.strip()
        if indent_of(line) == 2 and stripped in {"given", "given all", "for every"}:
            index += 1
            while index < len(content) and indent_of(content[index]) > 2:
                entry = content[index].strip()
                if ":" in entry and " " not in entry.split(":", 1)[0]:
                    parameters.append(entry)
                else:
                    conditions.append(entry)
                index += 1
            continue
        if indent_of(line) == 2 and (
            stripped.startswith("require ") or stripped.startswith("conclude ")
        ):
            start = index
            index += 1
            while index < len(content) and indent_of(content[index]) > 2:
                index += 1
            block = content[start:index]
            first = block[0].strip()
            if first == "require concurrence":
                first = "require concurrence_requirement"
            elif first.startswith("conclude "):
                first = "require " + first.removeprefix("conclude ")
            consequents.append("    " + first)
            consequents.extend("  " + nested for nested in block[1:])
            continue
        metadata.append(line)
        index += 1

    while metadata and not metadata[-1].strip():
        metadata.pop()
    output = [header, *metadata, ""]
    if parameters:
        output.append("  given")
        output.extend(f"    {parameter}" for parameter in parameters)
        output.append("")
    output.append("  if")
    output.extend(f"    {condition}" for condition in conditions)
    output.append("  then")
    output.extend(consequents)
    output.append("  end")
    return output


def migrate(source: str) -> str:
    lines = source.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("rule "):
            output.append(lines[index])
            index += 1
            continue
        end = index + 1
        while end < len(lines) and not lines[end].startswith("rule "):
            end += 1
        block = lines[index:end]
        while block and not block[-1].strip():
            block.pop()
        output.extend(migrate_rule(block))
        if end < len(lines):
            output.append("")
        index = end
    return "\n".join(output).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        path.write_text(migrate(path.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
