#!/usr/bin/env python3
"""Build the self-contained data bundle for the DSL review viewer."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).with_name("data.js")

SYNTAXES = {
    "ontologies": [
        {"id": "o1", "name": "SDML-inspired", "character": "Module-oriented, low punctuation"},
        {"id": "o2", "name": "Manchester-inspired", "character": "Explicit labeled frames"},
        {"id": "o3", "name": "RDF/SHACL-inspired", "character": "Compact graph and constraint vocabulary"},
    ],
    "rules": [
        {"id": "r1", "name": "Provision + Boolean", "character": "Source-oriented named provisions"},
        {"id": "r2", "name": "Labeled provision", "character": "Verbose professional-review frames"},
        {"id": "r3", "name": "Datalog derivation", "character": "Compact normalized execution rules"},
    ],
}

EXAMPLES = [
    {
        "id": "notice",
        "citation": "§50-3-10",
        "title": "Published-hearing notice",
        "pressure": "Typed relations, applicability, provenance, and an inclusive duration",
        "crate": "matrix_harness",
        "ontology": {
            "o1": "sdml_style/ontology.sdmlish",
            "o2": "manchester_style/ontology.manchester",
            "o3": "rdf_datalog_style/ontology.zonto",
        },
        "rules": {
            "r1": "sdml_style/article_iii.rules",
            "r2": "manchester_style/article_iii.rule",
            "r3": "rdf_datalog_style/article_iii.rules",
        },
    },
    {
        "id": "votes", "citation": "§50-2-78", "title": "BZA voting threshold",
        "pressure": "Specialization, specific override, exact fraction, and rounding",
        "crate": "voting_threshold",
    },
    {
        "id": "finality", "citation": "§50-2-79", "title": "Decision finality",
        "pressure": "Events, business calendars, evidence, and a conjunctive exception",
        "crate": "decision_finality",
    },
    {
        "id": "lapse", "citation": "§50-3-386", "title": "Approval lapse and extension",
        "pressure": "Automatic state transition, bounded power, history, and precedence",
        "crate": "approval_lapse",
    },
    {
        "id": "eligibility", "citation": "§50-3-341", "title": "Eligibility and spacing",
        "pressure": "Independent exceptions, identity-aware spatial counting, and waiver",
        "crate": "regulated_use_eligibility",
    },
    {
        "id": "waiver", "citation": "§50-3-443", "title": "Controlled-use waiver",
        "pressure": "Discretion, hard constraint, and unresolved source coordination",
        "crate": "controlled_use_waiver",
    },
]

DEFAULT_FILES = {
    "ontology": {"o1": "ontology.sdmlish", "o2": "ontology.manchester", "o3": "ontology.zonto"},
    "rules": {"r1": "rule.provision", "r2": "rule.labeled", "r3": "rule.datalog"},
}


def test_result(crate: str) -> dict:
    directory = ROOT / crate
    completed = subprocess.run(
        ["cargo", "test", "--offline", "-q"], cwd=directory, text=True, capture_output=True
    )
    listed = subprocess.run(
        ["cargo", "test", "--offline", "--", "--list"], cwd=directory, text=True, capture_output=True
    )
    names = []
    if listed.returncode == 0:
        for line in listed.stdout.splitlines():
            if line.endswith(": test"):
                names.append(line.removesuffix(": test").removeprefix("tests::"))
    return {
        "passed": completed.returncode == 0,
        "tests": names,
        "count": len(names),
        "failure": "" if completed.returncode == 0 else completed.stderr[-2000:],
    }


def main() -> None:
    examples = []
    for definition in EXAMPLES:
        item = dict(definition)
        base = ROOT / item["crate"]
        ontology_paths = item.pop("ontology", {key: str(Path(item["crate"]) / value) for key, value in DEFAULT_FILES["ontology"].items()})
        rule_paths = item.pop("rules", {key: str(Path(item["crate"]) / value) for key, value in DEFAULT_FILES["rules"].items()})
        # The first fixture points to sibling prototype directories already.
        item["sources"] = {"ontologies": {}, "rules": {}}
        for key, relative in ontology_paths.items():
            path = ROOT / relative if item["crate"] == "matrix_harness" else ROOT / relative
            item["sources"]["ontologies"][key] = {"path": str(path.relative_to(ROOT)), "text": path.read_text()}
        for key, relative in rule_paths.items():
            path = ROOT / relative if item["crate"] == "matrix_harness" else ROOT / relative
            item["sources"]["rules"][key] = {"path": str(path.relative_to(ROOT)), "text": path.read_text()}
        item["test_result"] = test_result(item["crate"])
        examples.append(item)

    payload = {"syntaxes": SYNTAXES, "examples": examples}
    OUTPUT.write_text("window.DSL_REVIEW_DATA = " + json.dumps(payload, indent=2) + ";\n")
    print(f"wrote {OUTPUT} with {len(examples)} examples")


if __name__ == "__main__":
    main()
