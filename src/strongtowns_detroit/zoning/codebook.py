"""Code-first DSL that compiles reviewed ordinance rules to canonical JSON."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Predicate:
    field: str
    operator: str
    value: Any


def eq(field: str, value: Any) -> Predicate:
    return Predicate(field, "eq", value)


def one_of(field: str, values: list[Any] | tuple[Any, ...]) -> Predicate:
    return Predicate(field, "in", list(values))


def less_than(field: str, value: Any) -> Predicate:
    return Predicate(field, "<", value)


def at_least(field: str, value: Any) -> Predicate:
    return Predicate(field, ">=", value)


def at_most(field: str, value: Any) -> Predicate:
    return Predicate(field, "<=", value)


def greater_than(field: str, value: Any) -> Predicate:
    return Predicate(field, ">", value)


@dataclass(frozen=True)
class Requirement:
    metric: str
    operator: str
    value: float
    unit: str


@dataclass(frozen=True)
class Source:
    document: str
    sections: tuple[str, ...]
    source_value: str
    note: str = ""


@dataclass(frozen=True)
class RuleDeclaration:
    id: str
    label: str
    when: tuple[Predicate, ...]
    requirement: Requirement
    source: Source
    exceptions: tuple[str, ...] = ()
    review_status: str = "verified"


@dataclass(frozen=True)
class PermissionDeclaration:
    id: str
    use: str
    district: str
    permission: str
    conditions: tuple[str, ...]
    source: Source
    when: tuple[Predicate, ...] = ()
    review_status: str = "verified"


@dataclass(frozen=True)
class DefinitionDeclaration:
    id: str
    term: str
    meaning: str
    source: Source
    review_status: str = "verified"


@dataclass(frozen=True)
class UseAssignmentDeclaration:
    id: str
    specific_use: str
    use_category: str
    source: Source
    review_status: str = "verified"


@dataclass(frozen=True)
class TextProvisionDeclaration:
    id: str
    effect: str
    text: str
    when: tuple[Predicate, ...]
    source: Source
    cross_references: tuple[str, ...] = ()
    review_status: str = "verified"


@dataclass(frozen=True)
class SourceProvisionDeclaration:
    id: str
    kind: str
    classes: tuple[str, ...]
    payload: Any
    source: Source
    cross_references: tuple[str, ...] = ()
    review_status: str = "source_encoded"


@dataclass(frozen=True)
class FormulaDeclaration:
    id: str
    output_unit: str
    expression: dict[str, Any]
    variables: dict[str, str]
    minimum: float | None
    source: Source
    review_status: str = "verified"


@dataclass(frozen=True)
class ComputedRuleDeclaration:
    id: str
    label: str
    when: tuple[Predicate, ...]
    metric: str
    operator: str
    formula: str
    source: Source
    exceptions: tuple[str, ...] = ()
    review_status: str = "structurally_verified"


@dataclass
class OrdinanceBuilder:
    municipality: str
    ordinance_version: str
    source_schema: str = "ordinance-source-v2"
    districts: dict[str, dict] = field(default_factory=dict)
    uses: dict[str, dict] = field(default_factory=dict)
    rules: list[RuleDeclaration] = field(default_factory=list)
    permissions: list[PermissionDeclaration] = field(default_factory=list)
    definitions: list[DefinitionDeclaration] = field(default_factory=list)
    use_assignments: list[UseAssignmentDeclaration] = field(default_factory=list)
    provisions: list[TextProvisionDeclaration] = field(default_factory=list)
    source_provisions: list[SourceProvisionDeclaration] = field(default_factory=list)
    formulas: list[FormulaDeclaration] = field(default_factory=list)
    computed_rules: list[ComputedRuleDeclaration] = field(default_factory=list)

    def district(self, code: str, label: str, category: str) -> None:
        self.districts[code] = {"code": code, "label": label, "category": category}

    def use(self, id: str, label: str, category: str) -> None:
        self.uses[id] = {"id": id, "label": label, "category": category}

    def minimum(
        self,
        *,
        id: str,
        label: str,
        metric: str,
        value: float,
        unit: str,
        when: tuple[Predicate, ...],
        source: Source,
        exceptions: tuple[str, ...] = (),
        review_status: str = "verified",
    ) -> None:
        self.standard(
            id=id, label=label, metric=metric, operator=">=", value=value,
            unit=unit, when=when, source=source, exceptions=exceptions,
            review_status=review_status,
        )

    def standard(
        self, *, id: str, label: str, metric: str, operator: str,
        value: float, unit: str, when: tuple[Predicate, ...], source: Source,
        exceptions: tuple[str, ...] = (), review_status: str = "verified",
    ) -> None:
        self.rules.append(RuleDeclaration(
            id=id,
            label=label,
            when=when,
            requirement=Requirement(metric, operator, value, unit),
            source=source,
            exceptions=exceptions,
            review_status=review_status,
        ))

    def permission(
        self, *, id: str, use: str, district: str, permission: str,
        source: Source, conditions: tuple[str, ...] = (),
        when: tuple[Predicate, ...] = (),
        review_status: str = "verified",
    ) -> None:
        self.permissions.append(PermissionDeclaration(
            id=id, use=use, district=district, permission=permission,
            conditions=conditions, source=source, when=when,
            review_status=review_status,
        ))

    def definition(
        self, *, id: str, term: str, meaning: str, source: Source,
        review_status: str = "verified",
    ) -> None:
        self.definitions.append(DefinitionDeclaration(
            id, term, meaning, source, review_status
        ))

    def assign_use(
        self, *, id: str, specific_use: str, use_category: str, source: Source,
        review_status: str = "verified",
    ) -> None:
        self.use_assignments.append(UseAssignmentDeclaration(
            id, specific_use, use_category, source, review_status
        ))

    def provision(
        self, *, id: str, effect: str, text: str, source: Source,
        when: tuple[Predicate, ...] = (), cross_references: tuple[str, ...] = (),
        review_status: str = "verified",
    ) -> None:
        self.provisions.append(TextProvisionDeclaration(
            id, effect, text, when, source, cross_references, review_status
        ))

    def source_provision(
        self, *, id: str, kind: str, classes: tuple[str, ...], payload: Any,
        source: Source, cross_references: tuple[str, ...] = (),
    ) -> None:
        self.source_provisions.append(SourceProvisionDeclaration(
            id, kind, classes, payload, source, cross_references
        ))

    def formula(
        self, *, id: str, output_unit: str, expression: dict[str, Any],
        variables: dict[str, str], source: Source, minimum: float | None = None,
        review_status: str = "verified",
    ) -> None:
        self.formulas.append(FormulaDeclaration(
            id, output_unit, expression, variables, minimum, source, review_status
        ))

    def computed_standard(
        self, *, id: str, label: str, when: tuple[Predicate, ...], metric: str,
        operator: str, formula: str, source: Source,
        exceptions: tuple[str, ...] = (),
        review_status: str = "structurally_verified",
    ) -> None:
        self.computed_rules.append(ComputedRuleDeclaration(
            id, label, when, metric, operator, formula, source, exceptions,
            review_status,
        ))

    def compile(self) -> dict:
        for label, declarations in (
            ("rule", self.rules),
            ("permission", self.permissions),
            ("definition", self.definitions),
            ("use assignment", self.use_assignments),
            ("provision", self.provisions),
            ("source provision", self.source_provisions),
            ("formula", self.formulas),
            ("computed rule", self.computed_rules),
        ):
            ids = [item.id for item in declarations]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {label} declaration ID")
        rule_dicts = []
        for rule in sorted(self.rules, key=lambda item: item.id):
            row = asdict(rule)
            row["when"] = {"all": row["when"]}
            rule_dicts.append(row)
        return {
            "schemaVersion": "executable-zoning-v3",
            "municipality": self.municipality,
            "ordinanceVersion": self.ordinance_version,
            "sourceSchema": self.source_schema,
            "districts": [self.districts[key] for key in sorted(self.districts)],
            "uses": [self.uses[key] for key in sorted(self.uses)],
            "rules": rule_dicts,
            "permissions": [
                {**asdict(item), "when": {"all": asdict(item)["when"]}}
                for item in sorted(self.permissions, key=lambda item: item.id)
            ],
            "definitions": [
                asdict(item) for item in sorted(self.definitions, key=lambda item: item.id)
            ],
            "useAssignments": [
                asdict(item) for item in sorted(self.use_assignments, key=lambda item: item.id)
            ],
            "provisions": [
                {**asdict(item), "when": {"all": asdict(item)["when"]}}
                for item in sorted(self.provisions, key=lambda item: item.id)
            ],
            "sourceProvisions": [
                asdict(item)
                for item in sorted(self.source_provisions, key=lambda item: item.id)
            ],
            "formulas": [
                asdict(item) for item in sorted(self.formulas, key=lambda item: item.id)
            ],
            "computedRules": [
                {**asdict(item), "when": {"all": asdict(item)["when"]}}
                for item in sorted(self.computed_rules, key=lambda item: item.id)
            ],
        }
