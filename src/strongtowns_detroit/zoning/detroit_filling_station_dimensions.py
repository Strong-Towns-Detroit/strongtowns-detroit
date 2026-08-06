"""Reviewed filling-station lot standards from §§50-13-174 and 50-13-175."""

from __future__ import annotations

from strongtowns_detroit.zoning.codebook import (
    OrdinanceBuilder,
    Source,
    at_least,
    at_most,
    eq,
    greater_than,
)


def add_filling_station_lot_standards(
    code: OrdinanceBuilder, source_corpus: dict
) -> int:
    """Compile the fixed cells and additive rows as two general formulas."""
    code.use(
        "motor_vehicle_filling_station",
        "Motor vehicle filling station",
        "vehicle_service",
    )
    count = 0
    for section, base_area, size_slug, size_predicate in (
        ("50-13-174", 12_000, "up_to_600_sf", at_most("gross_floor_area", 600)),
        ("50-13-175", 14_000, "over_600_sf", greater_than("gross_floor_area", 600)),
    ):
        formula_id = f"filling_station_area_{size_slug}"
        increment = {
            "op": "add",
            "args": [
                base_area,
                {"op": "multiply", "args": [2000, {
                    "op": "max", "args": [
                        {"op": "subtract", "args": [{"var": "pump_islands"}, 2]}, 0,
                    ],
                }]},
                {"op": "multiply", "args": [2000, {
                    "op": "max", "args": [
                        {"op": "subtract", "args": [{"var": "service_bays"}, 2]}, 0,
                    ],
                }]},
            ],
        }
        source = Source(
            "ARTICLE_XIII.municode.json",
            (section,),
            f"{base_area:,} square feet; add 2,000 square feet per additional pump island or service bay",
            "Formula reproduces every fixed table cell and the additive rows.",
        )
        code.formula(
            id=formula_id, output_unit="square_feet", expression=increment,
            variables={"pump_islands": "count", "service_bays": "count"},
            minimum=None, source=source, review_status="structurally_verified",
        )
        when = (
            eq("use", "motor_vehicle_filling_station"),
            at_least("pump_islands", 2),
            at_least("service_bays", 0),
            size_predicate,
            eq("on_traditional_main_street", False),
            eq("includes_restaurant_service", False),
        )
        code.minimum(
            id=f"filling_station:{size_slug}:minimum_lot_width",
            label="Minimum filling-station lot width", metric="lot_width",
            value=120, unit="feet", when=when, source=source,
            review_status="structurally_verified",
        )
        code.computed_standard(
            id=f"filling_station:{size_slug}:minimum_lot_area",
            label="Minimum filling-station lot area", when=when,
            metric="lot_area", operator=">=", formula=formula_id,
            source=source, review_status="structurally_verified",
        )
        count += 2
    return count


def add_filling_station_general_standards(code: OrdinanceBuilder) -> int:
    """Compile direct numeric standards in §§50-13-173 and 50-13-177--179."""
    use = "motor_vehicle_filling_station"
    code.use(use, "Motor vehicle filling station", "vehicle_service")
    count = 0

    def standard(
        rule_id: str, metric: str, operator: str, value: float, unit: str,
        when, section: str, source_value: str,
    ) -> None:
        nonlocal count
        code.standard(
            id=f"filling_station:{rule_id}", label=rule_id.replace("_", " ").title(),
            metric=metric, operator=operator, value=value, unit=unit,
            when=(eq("use", use), *when),
            source=Source(
                "ARTICLE_XIII.municode.json",
                (section,), source_value,
            ),
            review_status="verified",
        )
        count += 1

    tms = (eq("on_traditional_main_street", True),)
    standard("tms_maximum_lot_width", "lot_width", "<=", 120, "feet", tms,
             "50-13-173", "shall not exceed 120 feet")
    standard("tms_maximum_lot_area", "lot_area", "<=", 16_000, "square_feet", tms,
             "50-13-173", "shall not exceed 16,000 square feet")
    standard("tms_maximum_pump_islands", "pump_islands", "<=", 4, "count", tms,
             "50-13-173", "shall not exceed four pump islands")
    standard("maximum_lot_coverage", "lot_coverage", "<=", 40, "percent", (),
             "50-13-177", "not more than 40 percent")
    standard("building_front_setback", "front_setback", ">=", 40, "feet",
             (eq("element_type", "building_or_structure"),
              eq("on_traditional_main_street", False)),
             "50-13-178", "minimum of 40 feet from street right-of-way lines")
    standard("tms_build_to_line", "front_setback", "==", 0, "feet",
             (eq("element_type", "principal_building_or_structure"),
              eq("on_traditional_main_street", True)),
             "50-13-178", "shall be built to the front lot line")
    standard("building_residential_property_line_setback", "property_line_setback", ">=", 10,
             "feet", (eq("element_type", "building_or_structure"),
                      eq("abuts_residential_residential_pd_or_tm", True)),
             "50-13-178", "minimum of ten feet")
    standard("fuel_pump_property_line_setback", "property_line_setback", ">=", 20, "feet",
             (eq("element_type", "fuel_pump_or_pump_island"),),
             "50-13-179", "minimum of 20 feet")
    standard("compressed_air_or_kerosene_setback", "property_line_setback", ">=", 15, "feet",
             (eq("element_type", "compressed_air_similar_equipment_or_kerosene_pump"),),
             "50-13-179", "minimum of 15 feet")
    standard("kerosene_pump_building_setback", "building_setback", ">=", 10, "feet",
             (eq("element_type", "kerosene_pump"),),
             "50-13-179", "at least ten feet from any building")
    return count
