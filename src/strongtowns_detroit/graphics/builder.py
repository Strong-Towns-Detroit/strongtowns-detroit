"""Automatic discovery and multi-target builds for graphics projects."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TypeAlias

from strongtowns_detroit.graphics.model import (
    GRAPHIC_FORMAT_SPECS,
    GraphicFormat,
    GraphicTheme,
)
from strongtowns_detroit.graphics.svg import Graphic, write_graphic_bundle


@dataclass(frozen=True)
class BuildRecord:
    """One graphic written for one publishing target."""

    target: str
    source: str
    name: str
    title: str
    files: Mapping[str, Path]


GraphicBuilder: TypeAlias = Callable[[], dict[str, Graphic]]


@dataclass(frozen=True)
class GraphicDefinition:
    """A named graphic builder registered independently of its file path."""

    name: str
    builder: GraphicBuilder
    module: Path | None = None

    @property
    def directory(self) -> Path:
        """Directory containing this definition and shared layout sidecars."""
        if self.module is None:
            raise ValueError(f"graphic definition {self.name!r} has no source module")
        return self.module.parent


def graphic_definition(name: str) -> Callable[[GraphicBuilder], GraphicBuilder]:
    """Register a graphic builder without tying its identity to its file path."""
    if not name or not name.strip():
        raise ValueError("graphic definition name cannot be empty")

    def register(builder: GraphicBuilder) -> GraphicBuilder:
        setattr(builder, "__graphic_definition__", GraphicDefinition(name, builder))
        return builder

    return register


@dataclass(frozen=True)
class GraphicProject:
    """A directory of graphic definitions rendered to named targets."""

    source_root: Path
    output_root: Path
    formats: tuple[GraphicFormat, ...] = tuple(GraphicFormat)
    artifact_formats: tuple[str, ...] = ("html", "svg", "png")
    theme: GraphicTheme = GraphicTheme()

    def definitions(self) -> tuple[GraphicDefinition, ...]:
        """Discover library-registered builders anywhere under ``source_root``."""
        found: list[GraphicDefinition] = []
        names: dict[str, Path] = {}
        for path in sorted(self.source_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            # Avoid importing ordinary helper modules during discovery. The
            # explicit library decorator is the registration boundary.
            if "graphic_definition" not in path.read_text(encoding="utf-8"):
                continue
            module = self._load_module(path)
            seen: set[int] = set()
            for value in vars(module).values():
                registered = getattr(value, "__graphic_definition__", None)
                if not isinstance(registered, GraphicDefinition):
                    continue
                if id(registered) in seen:
                    continue
                seen.add(id(registered))
                if registered.name in names:
                    raise ValueError(
                        f"duplicate graphic definition {registered.name!r}: "
                        f"{names[registered.name]} and {path}"
                    )
                names[registered.name] = path
                found.append(
                    GraphicDefinition(registered.name, registered.builder, path)
                )
        return tuple(sorted(found, key=lambda item: item.name))

    @staticmethod
    def _load_module(path: Path):
        module_name = f"graphics_source_{abs(hash(path.resolve()))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def load(self, definition: GraphicDefinition) -> dict[str, Graphic]:
        graphics = definition.builder()
        if not isinstance(graphics, dict) or not graphics:
            raise TypeError(
                f"{definition.name} builder must return a nonempty dict"
            )
        if not all(isinstance(name, str) and isinstance(item, Graphic)
                   for name, item in graphics.items()):
            raise TypeError(
                f"{definition.name} builder must return dict[str, Graphic]"
            )
        return graphics

    def build(
        self,
        *,
        formats: list[str | GraphicFormat] | None = None,
        sources: list[str] | None = None,
    ) -> tuple[BuildRecord, ...]:
        """Load each selected definition once and fan it out to targets."""
        try:
            selected_formats = (
                [GraphicFormat(item) for item in formats]
                if formats is not None
                else list(self.formats)
            )
        except ValueError as error:
            raise ValueError(f"unknown publishing format: {error.args[0]}") from error
        unavailable = set(selected_formats) - set(self.formats)
        if unavailable:
            raise ValueError(
                "publishing formats not configured for this project: "
                f"{sorted(item.value for item in unavailable)}"
            )

        definitions = list(self.definitions())
        if sources:
            requested = set(sources)
            definitions = [item for item in definitions if item.name in requested]
            missing = requested - {item.name for item in definitions}
            if missing:
                raise ValueError(f"unknown graphic sources: {sorted(missing)}")

        records: list[BuildRecord] = []
        for definition in definitions:
            graphics = self.load(definition)
            for graphic_format in selected_formats:
                target_name = graphic_format.value
                target = GRAPHIC_FORMAT_SPECS[graphic_format]
                output_dir = self.output_root / target_name / definition.name
                for name, graphic in graphics.items():
                    layout_path = (
                        self.source_root
                        / "layout"
                        / definition.name
                        / target_name
                        / f"{name}.json"
                    )
                    layout_sidecar = (
                        json.loads(layout_path.read_text(encoding="utf-8"))
                        if layout_path.exists()
                        else None
                    )
                    if layout_sidecar is not None:
                        identity = layout_sidecar.get("graphic", {})
                        expected = {
                            "target": target_name,
                            "source": definition.name,
                            "name": name,
                        }
                        if identity and identity != expected:
                            raise ValueError(
                                f"layout sidecar identity mismatch at {layout_path}"
                            )
                    files = write_graphic_bundle(
                        output_dir,
                        name,
                        graphic,
                        aspect_ratio=target.aspect_ratio,
                        formats=self.artifact_formats,
                        png_width=target.png_width,
                        theme=self.theme,
                        content_aspect_ratio=target.content_aspect_ratio,
                        content_top_padding=target.content_top_padding,
                        layout_sidecar=layout_sidecar,
                    )
                    records.append(
                        BuildRecord(
                            target=target_name,
                            source=definition.name,
                            name=name,
                            title=graphic.title_text,
                            files=files,
                        )
                    )

        self._write_manifests(
            records,
            [graphic_format.value for graphic_format in selected_formats],
            replace=sources is None,
        )
        return tuple(records)

    def _write_manifests(
        self,
        records: list[BuildRecord],
        target_names: list[str],
        *,
        replace: bool,
    ) -> None:
        for target_name in target_names:
            target_root = self.output_root / target_name
            manifest_path = target_root / "manifest.json"
            entries_by_key: dict[tuple[str, str], dict] = {}
            if not replace and manifest_path.exists():
                previous = json.loads(manifest_path.read_text(encoding="utf-8"))
                entries_by_key = {
                    (entry["source"], entry["name"]): entry
                    for entry in previous.get("graphics", [])
                }
            for record in records:
                if record.target != target_name:
                    continue
                entries_by_key[(record.source, record.name)] = {
                    "source": record.source,
                    "name": record.name,
                    "title": record.title,
                    "files": {
                        kind: str(path.relative_to(target_root))
                        for kind, path in record.files.items()
                    },
                }
            target_root.mkdir(parents=True, exist_ok=True)
            entries = [entries_by_key[key] for key in sorted(entries_by_key)]
            manifest_path.write_text(
                json.dumps({"graphics": entries}, indent=2) + "\n",
                encoding="utf-8",
            )


@dataclass(frozen=True)
class GraphicBuildSystem:
    """Library-owned build engine for a graphics project.

    Registered builders may live anywhere beneath ``src``. Their explicit
    library definition names, rather than their paths, determine build identity.
    """

    root: Path
    formats: tuple[GraphicFormat, ...] = tuple(GraphicFormat)
    artifact_formats: tuple[str, ...] = ("html", "svg", "png")
    theme: GraphicTheme = GraphicTheme()

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.resolve())

    @property
    def source_root(self) -> Path:
        return self.root / "src"

    @property
    def output_root(self) -> Path:
        return self.root / "output"

    @property
    def project(self) -> GraphicProject:
        return GraphicProject(
            self.source_root,
            self.output_root,
            self.formats,
            self.artifact_formats,
            self.theme,
        )

    def definitions(self) -> tuple[GraphicDefinition, ...]:
        return self.project.definitions()

    def build(
        self,
        *,
        formats: list[str | GraphicFormat] | None = None,
        sources: list[str] | None = None,
    ) -> tuple[BuildRecord, ...]:
        return self.project.build(formats=formats, sources=sources)

    @classmethod
    def find(cls, start: Path | str = ".") -> "GraphicBuildSystem":
        """Find a graphics project from its directory or an ancestor.

        Both a direct graphics root and the repository convention
        ``projects/graphics`` are recognized.
        """
        start_path = Path(start).resolve()
        if start_path.is_file():
            start_path = start_path.parent
        for directory in (start_path, *start_path.parents):
            direct = directory
            nested = directory / "projects" / "graphics"
            # Prefer the repository convention over an unrelated top-level
            # Python ``src`` directory.
            for candidate in (nested, direct):
                if (candidate / "src").is_dir():
                    return cls(candidate)
        raise FileNotFoundError(
            f"no graphics project found from {start_path}; expected a src directory "
            "or projects/graphics/src"
        )
