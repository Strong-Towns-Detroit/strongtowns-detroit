from pathlib import Path

from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.detroit_overlay_rules import add_gateway_overlay_prohibitions
from strongtowns_detroit.zoning.source_model import compile_source_corpus

ROOT = Path(__file__).resolve().parents[1]


def test_gateway_prohibitions_preserve_underlying_district_scope_and_exceptions():
    source = compile_source_corpus(ROOT / "resources")
    builder = build_detroit_code()
    count = add_gateway_overlay_prohibitions(builder, source)
    package = builder.compile()
    assert count == 61 == len(package["permissions"])
    assert {item["review_status"] for item in package["permissions"]} == {"verified"}
    assert all("overlay:a" in item["conditions"] for item in package["permissions"])
    assert not any("restaurant_carry_out" in item["use"] for item in package["permissions"])
    assert not any("wholesaling_warehousing" in item["use"] for item in package["permissions"])
    junkyard = next(item for item in package["permissions"] if item["use"] == "junkyard")
    assert junkyard["district"] == "*"
