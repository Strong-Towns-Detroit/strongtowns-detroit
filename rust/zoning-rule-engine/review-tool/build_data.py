#!/usr/bin/env python3
"""Build the static three-representation legal review bundle."""

from __future__ import annotations

import json
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).with_name("data.js")
VERSIONS = Path(__file__).with_name("versions.json")
REPLIES = Path(__file__).with_name("replies.json")
MODULE_SOURCES = [
    (
        ROOT / "examples/minimum_bseed_notice.zdl",
        ROOT / "examples/ontologies/detroit.article_iii.notice.ontology.zdl",
    ),
    (
        ROOT / "examples/reviewed_rules.zdl",
        ROOT / "examples/ontologies/detroit.reviewed_rules.ontology.zdl",
    ),
]
ALL_EXAMPLES = sorted((ROOT / "examples").rglob("*.zdl"))


def validate_all_examples() -> None:
    """Fail the build unless every authored example compiles together."""
    command = [
        "cargo",
        "run",
        "--offline",
        "--quiet",
        "--bin",
        "zoning-dsl",
        "--",
        "compile-all",
        *[str(path) for path in ALL_EXAMPLES],
    ]
    subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)


def compile_modules() -> list[dict]:
    command = [
        "cargo",
        "run",
        "--offline",
        "--quiet",
        "--bin",
        "zoning-dsl",
        "--",
        "compile-all",
        *[str(path) for path, _ in MODULE_SOURCES],
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    return json.loads(completed.stdout)


def rule_blocks(source: str) -> dict[str, str]:
    lines = source.splitlines()
    blocks: dict[str, str] = {}
    index = 0
    while index < len(lines):
        if not lines[index].startswith("rule "):
            index += 1
            continue
        name = lines[index].removeprefix("rule ").strip()
        end = index + 1
        while end < len(lines) and not lines[end].startswith("rule "):
            end += 1
        block = "\n".join(lines[index:end]).rstrip()
        blocks[name] = block
        index = end
    return blocks


def source_text(rule: dict) -> str:
    chunks = []
    for source in rule["sources"]:
        chunks.append(f'{source["citation"]}\n{source["quote"]}')
    return "\n\n".join(chunks)


def interpretive_relations(rule: dict) -> list[str]:
    relations = []
    for proposition in rule["body"]["propositions"]:
        if proposition["interpretive"]:
            relations.append(proposition["relation"])
    for consequent in rule["consequents"]:
        value = consequent["value"]
        if consequent["type"] == "duty" and value.get("using"):
            for application in value["using"]["satisfying"]:
                if application["interpretive"]:
                    relations.append(application["relation"])
        if consequent["type"] == "proposition" and value["application"]["interpretive"]:
            relations.append(value["application"]["relation"])
    return sorted(set(relations))


def artifact_fingerprint(rule: dict) -> str:
    material = json.dumps(rule, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def version_rules(rules: list[dict]) -> list[dict]:
    archive = load_json(VERSIONS, {"schemaVersion": 1, "rules": {}})
    archived_rules = archive.setdefault("rules", {})
    now = datetime.now(timezone.utc).isoformat()
    result = []
    for rule in rules:
        fingerprint = artifact_fingerprint(rule)
        versions = archived_rules.setdefault(rule["id"], [])
        if not versions or versions[-1]["fingerprint"] != fingerprint:
            snapshot = {
                **rule,
                "versionId": f"v{len(versions) + 1}",
                "fingerprint": fingerprint,
                "createdAt": now,
            }
            versions.append(snapshot)
        result.append(
            {
                **rule,
                "currentVersion": versions[-1]["versionId"],
                "versions": versions,
            }
        )
    VERSIONS.write_text(
        json.dumps(archive, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    validate_all_examples()
    compiled_modules = compile_modules()
    rules = []
    for (path, ontology_path), module in zip(
        MODULE_SOURCES, compiled_modules, strict=True
    ):
        source = path.read_text(encoding="utf-8")
        blocks = rule_blocks(source)
        complete_ontology = ontology_path.read_text(encoding="utf-8")
        for rule in module["rules"]:
            rules.append(
                {
                    "id": rule["id"],
                    "name": rule["name"],
                    "module": module["module"],
                    "file": str(path.relative_to(ROOT)),
                    "citations": [item["citation"] for item in rule["sources"]],
                    "interpretiveGaps": interpretive_relations(rule),
                    "panes": {
                        "text": {
                            "label": "Legal text",
                            "language": "text",
                            "text": source_text(rule),
                        },
                        "presented": {
                            "label": "Presented rule",
                            "language": "zdl",
                            "text": blocks[rule["name"]],
                            "ontology": {
                                "label": "Ontology",
                                "language": "zdl",
                                "file": str(ontology_path.relative_to(ROOT)),
                                "text": complete_ontology,
                            },
                        },
                        "compiled": {
                            "label": "Compiled form",
                            "language": "json",
                            "text": json.dumps(rule, indent=2, ensure_ascii=False),
                        },
                    },
                }
            )
    rules = version_rules(rules)
    replies = load_json(REPLIES, {"schemaVersion": 1, "replies": {}})
    payload = {"schemaVersion": 2, "rules": rules, "replies": replies["replies"]}
    OUTPUT.write_text(
        "window.LEGAL_REVIEW_DATA = " + json.dumps(payload, indent=2, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT} with {len(rules)} rules")


if __name__ == "__main__":
    main()
