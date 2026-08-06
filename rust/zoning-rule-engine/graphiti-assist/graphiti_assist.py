#!/usr/bin/env python3
"""Local, non-authoritative Graphiti memory for ontology authoring.

Graphiti proposes semantic entities and edges from exact ordinance source spans.
Nothing emitted here is automatically promoted into the typed ZDL ontology or
legal rules. The Rust compiler remains authoritative.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.nodes import EpisodeType
from pydantic import BaseModel, Field


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
RECEIPTS = HERE / "data" / "ingestion-receipts.jsonl"


class LegalThing(BaseModel):
    """A candidate thing named or described in legal text; not yet canonical."""

    source_term: Optional[str] = Field(
        None, description="Exact or minimally normalized term used by the source."
    )


class LegalActor(BaseModel):
    """A person, organization, office, board, agency, or other possible legal actor."""

    source_term: Optional[str] = Field(None, description="Source wording for the actor.")


class LegalMatter(BaseModel):
    """A notice, application, hearing, decision, order, approval, or similar matter."""

    source_term: Optional[str] = Field(None, description="Source wording for the matter.")


class LegalEvent(BaseModel):
    """An occurrence or legally meaningful action that may have participants and time."""

    source_verb: Optional[str] = Field(None, description="Verb or phrase evoking the event.")


class LegalQuantity(BaseModel):
    """A candidate exact threshold, duration, count, ratio, length, area, or other quantity."""

    source_expression: Optional[str] = Field(None, description="Exact quantitative expression.")


class LegalTerm(BaseModel):
    """A legally meaningful term whose definition or interpretation may need review."""

    source_term: Optional[str] = Field(None, description="Exact source term.")


class StructuralRelation(BaseModel):
    """A candidate durable association between independently typed things."""

    source_phrase: Optional[str] = Field(None, description="Phrase supporting the association.")


class FactualPredicate(BaseModel):
    """A candidate truth-valued fact that may be supplied as evidence to a rule."""

    source_phrase: Optional[str] = Field(None, description="Phrase supporting the predicate.")


class PossibleRuleDerivation(BaseModel):
    """A candidate edge that may actually encode a legal conclusion or procedure."""

    source_phrase: Optional[str] = Field(None, description="Phrase suggesting the derivation.")
    review_warning: Optional[str] = Field(
        None,
        description="Why this edge may belong in a legal rule rather than the ontology.",
    )


ENTITY_TYPES = {
    "LegalThing": LegalThing,
    "LegalActor": LegalActor,
    "LegalMatter": LegalMatter,
    "LegalEvent": LegalEvent,
    "LegalQuantity": LegalQuantity,
    "LegalTerm": LegalTerm,
}

EDGE_TYPES = {
    "StructuralRelation": StructuralRelation,
    "FactualPredicate": FactualPredicate,
    "PossibleRuleDerivation": PossibleRuleDerivation,
}

# This intentionally allows all three candidate classifications between broad
# types. The reviewed ZDL ontology will progressively generate a narrower map.
EDGE_TYPE_MAP = {
    ("Entity", "Entity"): [
        "StructuralRelation",
        "FactualPredicate",
        "PossibleRuleDerivation",
    ]
}


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("your_") or value.startswith("choose_"):
        raise SystemExit(f"Set {name} in {REPO_ROOT / '.env'}")
    return value


def make_graphiti() -> Graphiti:
    api_key = require_env("OPENAI_API_KEY")
    config = LLMConfig(
        api_key=api_key,
        model=os.getenv("GRAPHITI_LLM_MODEL", "gpt-5.4-mini"),
        small_model=os.getenv("GRAPHITI_SMALL_MODEL", "gpt-5.4-mini"),
    )
    # Graphiti 0.29.3's `auto` fallback resolves to the retired `minimal` tier
    # for gpt-5.4-mini. Pass a currently supported effort explicitly.
    llm = OpenAIClient(
        config=config,
        reasoning=os.getenv("GRAPHITI_REASONING_EFFORT", "low"),
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=api_key,
            embedding_model=os.getenv(
                "GRAPHITI_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
        )
    )
    return Graphiti(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        os.getenv("NEO4J_USER", "neo4j"),
        require_env("NEO4J_PASSWORD"),
        llm_client=llm,
        embedder=embedder,
        cross_encoder=OpenAIRerankerClient(client=llm, config=config),
    )


def source_text(args: argparse.Namespace) -> tuple[str, str]:
    if args.text is not None:
        return args.text, args.source_id
    path = Path(args.file).resolve()
    return path.read_text(encoding="utf-8"), args.source_id or str(path.relative_to(REPO_ROOT))


def append_receipt(source_id: str, text: str, episode_name: str) -> None:
    RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "episode": episode_name,
        "source_id": source_id,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "characters": len(text),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "group_id": os.getenv("GRAPHITI_GROUP_ID", "detroit-chapter-50-candidates"),
        "status": "candidate",
    }
    with RECEIPTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")


async def command_init() -> None:
    graphiti = make_graphiti()
    try:
        await graphiti.build_indices_and_constraints()
        print("Graphiti indices and constraints are ready.")
    finally:
        await graphiti.close()


async def command_ingest(args: argparse.Namespace) -> None:
    text, source_id = source_text(args)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    episode_name = args.name or f"chapter50:{source_id}:{digest}"
    graphiti = make_graphiti()
    try:
        await graphiti.add_episode(
            name=episode_name,
            episode_body=text,
            source=EpisodeType.text,
            source_description=f"Detroit Chapter 50 exact source span: {source_id}",
            reference_time=datetime.now(timezone.utc),
            group_id=os.getenv("GRAPHITI_GROUP_ID", "detroit-chapter-50-candidates"),
            entity_types=ENTITY_TYPES,
            edge_types=EDGE_TYPES,
            edge_type_map=EDGE_TYPE_MAP,
        )
        append_receipt(source_id, text, episode_name)
        print(f"Ingested candidate episode {episode_name}")
    finally:
        await graphiti.close()


async def command_search(args: argparse.Namespace) -> None:
    graphiti = make_graphiti()
    try:
        results = await graphiti.search(
            args.query,
            group_ids=[os.getenv("GRAPHITI_GROUP_ID", "detroit-chapter-50-candidates")],
            num_results=args.limit,
        )
        for result in results:
            print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    finally:
        await graphiti.close()


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create Graphiti indices and constraints.")

    ingest = commands.add_parser("ingest", help="Extract one exact legal source span.")
    source = ingest.add_mutually_exclusive_group(required=True)
    source.add_argument("--file")
    source.add_argument("--text")
    ingest.add_argument("--source-id", default="manual-source-span")
    ingest.add_argument("--name")

    search = commands.add_parser("search", help="Search candidate graph facts.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    return root


async def main() -> None:
    load_dotenv(HERE / ".env")
    load_dotenv(REPO_ROOT / ".env")
    args = parser().parse_args()
    if args.command == "init":
        await command_init()
    elif args.command == "ingest":
        await command_ingest(args)
    elif args.command == "search":
        await command_search(args)


if __name__ == "__main__":
    asyncio.run(main())
