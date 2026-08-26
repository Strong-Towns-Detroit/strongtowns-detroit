"""Path-independent data pipeline registration and discovery."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import tomllib
from collections.abc import Callable, Iterable
from pathlib import Path

from .model import DataPipeline


PipelineFactory = Callable[[], DataPipeline]


def data_pipeline(name: str) -> Callable[[PipelineFactory], PipelineFactory]:
    if not name.strip():
        raise ValueError("pipeline name cannot be empty")

    def register(factory: PipelineFactory) -> PipelineFactory:
        setattr(factory, "__data_pipeline_name__", name)
        return factory

    return register


def _factories(module) -> Iterable[PipelineFactory]:
    seen: set[int] = set()
    for value in vars(module).values():
        if callable(value) and hasattr(value, "__data_pipeline_name__") and id(value) not in seen:
            seen.add(id(value))
            yield value


def load_definition_file(path: Path):
    name = f"strongtowns_data_definitions_{abs(hash(path.resolve()))}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover(root: Path) -> tuple[DataPipeline, ...]:
    config_path = root / "strongtowns-data.toml"
    modules = []
    if config_path.is_file():
        config = tomllib.loads(config_path.read_text())
        for relative in config.get("project", {}).get("definition_files", []):
            path = (root / relative).resolve()
            path.relative_to(root.resolve())
            modules.append(load_definition_file(path))
    for entry in importlib.metadata.entry_points(group="strongtowns.data_pipelines"):
        modules.append(entry.load())

    pipelines: dict[str, DataPipeline] = {}
    for module in modules:
        for factory in _factories(module):
            pipeline = factory()
            registered_name = getattr(factory, "__data_pipeline_name__")
            if pipeline.name != registered_name:
                raise ValueError(
                    f"registered pipeline name mismatch: {registered_name} != {pipeline.name}"
                )
            if pipeline.name in pipelines:
                raise ValueError(f"duplicate pipeline: {pipeline.name}")
            pipelines[pipeline.name] = pipeline
    return tuple(pipelines[name] for name in sorted(pipelines))
