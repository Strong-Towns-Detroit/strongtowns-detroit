"""Tests for strongtowns_detroit.zoning.models dataclasses."""

from strongtowns_detroit.zoning.models import (
    DimensionalStandard,
    SectionNode,
    UsePermission,
    ZoningDefinition,
)


class TestUsePermission:
    def test_construction(self):
        p = UsePermission(use_name="One-family dwelling", district="R1", permission="R")
        assert p.use_name == "One-family dwelling"
        assert p.district == "R1"
        assert p.permission == "R"
        assert p.conditions == ""

    def test_with_conditions(self):
        p = UsePermission(
            use_name="Day care center",
            district="R2",
            permission="C",
            conditions="Subject to Sec. 50-12-132",
        )
        assert p.conditions == "Subject to Sec. 50-12-132"


class TestDimensionalStandard:
    def test_construction(self):
        d = DimensionalStandard(
            district="R1", standard_name="Minimum Lot Area", value="5,000 sq ft"
        )
        assert d.district == "R1"
        assert d.standard_name == "Minimum Lot Area"
        assert d.value == "5,000 sq ft"
        assert d.section_ref == ""

    def test_with_section_ref(self):
        d = DimensionalStandard(
            district="R2",
            standard_name="Maximum Height",
            value="35 ft",
            section_ref="50-13-201",
        )
        assert d.section_ref == "50-13-201"


class TestZoningDefinition:
    def test_construction(self):
        z = ZoningDefinition(term="Accessory building", definition="A subordinate building...")
        assert z.term == "Accessory building"
        assert z.definition == "A subordinate building..."
        assert z.section_ref == ""

    def test_with_section_ref(self):
        z = ZoningDefinition(
            term="Lot", definition="A parcel of land...", section_ref="50-16-100"
        )
        assert z.section_ref == "50-16-100"


class TestSectionNode:
    def test_defaults(self):
        node = SectionNode(number="50-12-101", title="Use Regulations", level=5)
        assert node.content == []
        assert node.children == []
        assert node.tables == []

    def test_mutable_defaults_not_shared(self):
        a = SectionNode(number="1", title="A", level=3)
        b = SectionNode(number="2", title="B", level=3)
        a.content.append("hello")
        assert b.content == []

    def test_nested_children(self):
        child = SectionNode(number="50-12-101", title="Uses Permitted", level=5)
        parent = SectionNode(
            number="50-12-100",
            title="Division 1",
            level=4,
            children=[child],
        )
        assert len(parent.children) == 1
        assert parent.children[0].title == "Uses Permitted"

    def test_tables_attached(self):
        grid = [["R1", "R2"], ["5000", "3000"]]
        node = SectionNode(number="50-13-201", title="Lot Standards", level=5, tables=[grid])
        assert len(node.tables) == 1
        assert node.tables[0][0][0] == "R1"
