"""Public types for contract-driven data builds."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias


class ArchiveTier(str, Enum):
    NONE = "none"
    CRITICAL = "critical"
    SOURCE = "source"
    DELIVERABLE = "deliverable"


class AcquisitionPolicy(str, Enum):
    LOCAL = "local"
    PUBLIC_NETWORK = "public_network"
    CREDENTIALED = "credentialed"
    PAID = "paid"


class ProvenanceGrade(str, Enum):
    CAPTURED = "captured"
    LEGACY = "legacy"


@dataclass(frozen=True)
class DatasetContract:
    """Versioned validation contract for one canonical dataset."""

    name: str
    version: str
    required_columns: Mapping[str, str] = field(default_factory=dict)
    allowed_values: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)
    primary_key: tuple[str, ...] = ()
    geometry_types: tuple[str, ...] = ()
    crs: str | None = None
    accepted_artifact: str | None = None
    rejects_artifact: str | None = None
    custom_validator: Callable[[Path, Mapping[str, Any]], None] | None = field(
        default=None, compare=False, repr=False
    )

    @property
    def schema(self) -> dict[str, Any]:
        schema = {
            "name": self.name,
            "version": self.version,
            "required_columns": dict(sorted(self.required_columns.items())),
            "primary_key": list(self.primary_key),
            "geometry_types": list(self.geometry_types),
            "crs": self.crs,
            "accepted_artifact": self.accepted_artifact,
            "rejects_artifact": self.rejects_artifact,
        }
        # Preserve existing v1 hashes for contracts that do not declare enums.
        if self.allowed_values:
            schema["allowed_values"] = {
                name: list(values) for name, values in sorted(self.allowed_values.items())
            }
        return schema

    @property
    def schema_hash(self) -> str:
        payload = json.dumps(
            self.schema, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class DataAsset:
    """A registered dataset whose snapshots live below ``path``."""

    id: str
    path: Path
    contract: DatasetContract
    archive_tier: ArchiveTier = ArchiveTier.NONE
    legacy_artifacts: Mapping[str, Path] = field(default_factory=dict)
    legacy_counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class BuildMetadata:
    """Metadata supplied by a builder after writing one output staging tree."""

    counts: Mapping[str, int] = field(default_factory=dict)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    source: Mapping[str, Any] = field(default_factory=dict)
    provenance_grade: ProvenanceGrade = ProvenanceGrade.CAPTURED
    transaction_quality: str = "atomic"


@dataclass(frozen=True)
class PipelineContext:
    """Explicit paths and immutable parents supplied to a pipeline builder."""

    root: Path
    pipeline_name: str
    inputs: Mapping[str, Path]
    input_manifests: Mapping[str, Mapping[str, Any]]
    staging: Mapping[str, Path]


PipelineBuilder: TypeAlias = Callable[[PipelineContext], Mapping[str, BuildMetadata]]
PipelineFetcher: TypeAlias = Callable[[PipelineContext], Mapping[str, BuildMetadata]]


@dataclass(frozen=True)
class DataPipeline:
    """One registered producer in the repository data DAG."""

    name: str
    inputs: tuple[str, ...]
    outputs: tuple[DataAsset, ...]
    build: PipelineBuilder | None = field(default=None, compare=False, repr=False)
    fetch: PipelineFetcher | None = field(default=None, compare=False, repr=False)
    acquisition_policy: AcquisitionPolicy = AcquisitionPolicy.LOCAL
    description: str = ""
