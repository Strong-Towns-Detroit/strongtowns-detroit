import json
from pathlib import Path
import pytest

from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source, eq
from strongtowns_detroit.zoning.detroit_permissions import add_structural_permissions
from strongtowns_detroit.zoning.detroit_lexicon import add_structural_lexicon
from strongtowns_detroit.zoning.detroit_dimensions import add_structural_dimensions
from strongtowns_detroit.zoning.detroit_source_provisions import add_source_provisions
from strongtowns_detroit.zoning.detroit_text_candidates import add_text_candidates
from strongtowns_detroit.zoning.source_model import compile_source_corpus
from strongtowns_detroit.zoning.json_engine import applicable_rules, evaluate_package


def package():
    # Round-trip proves the evaluator consumes static JSON, not dataclasses.
    return json.loads(json.dumps(build_detroit_code().compile()))


def test_use_is_part_of_rule_applicability():
    code = package()
    one = applicable_rules(code, {
        "district": "R3", "use": "one_family_dwelling", "building_role": "principal"
    })
    two = applicable_rules(code, {
        "district": "R3", "use": "two_family_dwelling", "building_role": "principal"
    })
    assert len(one) == len(two) == 6
    one_width = next(r for r in one if r["requirement"]["metric"] == "lot_width")
    two_width = next(r for r in two if r["requirement"]["metric"] == "lot_width")
    assert one_width["requirement"]["value"] == 50
    assert two_width["requirement"]["value"] == 60


def test_r1_two_family_has_no_borrowed_rules():
    assert applicable_rules(package(), {
        "district": "R1", "use": "two_family_dwelling", "building_role": "principal"
    }) == []


def test_json_engine_preserves_unknowns_and_exception_disclosure():
    results = evaluate_package(
        package(),
        {"district": "R2", "use": "one_family_dwelling", "building_role": "principal"},
        {"lot_area": 4_000, "lot_width": None},
    )
    area = next(r for r in results if r["requirement"]["metric"] == "lot_area")
    width = next(r for r in results if r["requirement"]["metric"] == "lot_width")
    assert area["status"] == "fails"
    assert width["status"] == "unknown"
    assert "lot_of_record" in area["exceptionsNotEvaluated"]


def test_hypothetical_is_a_package_change_not_an_engine_change():
    code = package()
    target = next(
        rule for rule in code["rules"]
        if rule["id"] == "r2:one_family_dwelling:minimum_lot_area"
    )
    target["requirement"]["value"] = 3_000
    result = evaluate_package(
        code,
        {"district": "R2", "use": "one_family_dwelling", "building_role": "principal"},
        {"lot_area": 4_000},
    )
    area = next(r for r in result if r["requirement"]["metric"] == "lot_area")
    assert area["status"] == "meets"


def test_dsl_carries_permissions_definitions_and_text_provisions():
    code = OrdinanceBuilder("Test", "snapshot")
    source = Source("article.docx", ("50-1-1",), "raw")
    code.permission(
        id="permission:bakery:r1", use="bakery", district="R1",
        permission="conditional", source=source, conditions=("50-1-2",),
    )
    code.definition(id="definition:bakery", term="Bakery", meaning="A place", source=source)
    code.assign_use(
        id="assignment:bake-shop", specific_use="Bake shop",
        use_category="Retail", source=source,
    )
    code.provision(
        id="provision:hours", effect="requirement", text="Must close.",
        when=(eq("use", "bakery"),), source=source, cross_references=("50-1-2",),
    )
    package = code.compile()
    assert package["permissions"][0]["permission"] == "conditional"
    assert package["definitions"][0]["term"] == "Bakery"
    assert package["useAssignments"][0]["use_category"] == "Retail"
    assert package["provisions"][0]["when"]["all"][0]["field"] == "use"


def test_unambiguous_article_xii_cells_compile_with_honest_review_status():
    builder = build_detroit_code()
    count = add_structural_permissions(
        builder, compile_source_corpus(Path(__file__).resolve().parents[1] / "resources")
    )
    package = builder.compile()
    assert count == 7565 == len(package["permissions"])
    assert {item["review_status"] for item in package["permissions"]} == {
        "structurally_verified"
    }
    assert {item["permission"] for item in package["permissions"]} == {
        "not_allowed", "allowed_by_right", "conditional_use", "legislative_approval",
        "accessory_only",
    }
    accessory = [
        item for item in package["permissions"]
        if item["permission"] == "accessory_only"
    ]
    assert len(accessory) == 9
    assert all("50-12-521" in item["source"]["sections"] for item in accessory)


def test_article_xvi_and_appendix_compile_as_distinct_types():
    source = compile_source_corpus(Path(__file__).resolve().parents[1] / "resources")
    builder = build_detroit_code()
    counts = add_structural_lexicon(builder, source)
    package = builder.compile()
    assert counts == {"definitions": 467, "useAssignments": 478}
    assert len(package["definitions"]) == 467
    assert len(package["useAssignments"]) == 478
    assert all(item["source"]["sections"] == () for item in package["useAssignments"])


def test_duplicate_declaration_ids_fail_compilation():
    builder = OrdinanceBuilder("Test", "snapshot")
    source = Source("article.docx", ("50-1-1",), "R")
    for district in ("R1", "R2"):
        builder.permission(
            id="duplicate", use="bakery", district=district,
            permission="allowed_by_right", source=source,
        )
    with pytest.raises(ValueError, match="duplicate permission"):
        builder.compile()


def test_simple_district_dimensions_compile_without_colliding_with_reviewed_rules():
    source = compile_source_corpus(Path(__file__).resolve().parents[1] / "resources")
    builder = build_detroit_code()
    count = add_structural_dimensions(builder, source)
    package = builder.compile()
    assert count == 730
    assert len(package["rules"]) == 66 + 730
    structural = [item for item in package["rules"] if item["review_status"] == "structurally_verified"]
    assert len(structural) == 730


def test_every_source_block_can_be_encoded_by_the_dsl():
    source = compile_source_corpus(Path(__file__).resolve().parents[1] / "resources")
    builder = build_detroit_code()
    count = add_source_provisions(builder, source)
    package = builder.compile()
    assert count == 11643 == len(package["sourceProvisions"])
    assert {item["review_status"] for item in package["sourceProvisions"]} == {
        "source_encoded"
    }


def test_typed_text_candidates_remain_nonfinal():
    source = compile_source_corpus(Path(__file__).resolve().parents[1] / "resources")
    builder = build_detroit_code()
    counts = add_text_candidates(builder, source)
    package = builder.compile()
    assert counts["procedure"] > 500
    assert counts["exception"] > 300
    assert counts["nonconformity"] > 100
    assert all(
        item["review_status"] == "machine_classified"
        for item in package["provisions"]
    )
