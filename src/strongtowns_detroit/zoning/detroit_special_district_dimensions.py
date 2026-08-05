"""Reviewed SD1 and SD2 dimensional branches from §§50-11-245 and 50-11-275."""

from __future__ import annotations

from strongtowns_detroit.zoning.codebook import (
    OrdinanceBuilder,
    Source,
    at_least,
    at_most,
    eq,
    greater_than,
    less_than,
)

ARTICLE_XI = "ARTICLE_XI.municode.json"


def add_sd1_sd2_dimensions(code: OrdinanceBuilder) -> dict[str, int]:
    code.formula(
        id="sd_front_setback_adjacent_average_cap_20", output_unit="feet",
        expression={"op": "min", "args": [
            {"var": "adjacent_buildings_average_front_setback"}, 20,
        ]},
        variables={"adjacent_buildings_average_front_setback": "feet"}, minimum=None,
        source=Source(ARTICLE_XI, ("50-11-245", "50-11-275"),
                      "average adjacent front setback or 20 feet, whichever is less"),
    )
    for district, threshold, cap, section in (
        ("SD1", 50, 60, "50-11-245"),
        ("SD2", 60, 80, "50-11-275"),
    ):
        code.formula(
            id=f"{district.casefold()}_mixed_use_height_bonus", output_unit="feet",
            expression={"op": "min", "args": [
                {"var": "abutting_right_of_way_width"}, cap,
            ]},
            variables={"abutting_right_of_way_width": "feet"}, minimum=None,
            source=Source(
                ARTICLE_XI, (section,),
                f"one-foot increase above {threshold} feet, capped at {cap} feet",
            ),
        )

    rule_count = 0
    computed_count = 0
    provision_count = 0
    for district, nonmixed_height, mixed_height, row_threshold, cap, section in (
        ("SD1", 35, 50, 50, 60, "50-11-245"),
        ("SD2", 45, 60, 60, 80, "50-11-275"),
    ):
        code.district(district, f"{district} district", "special_or_overlay")
        source = Source(ARTICLE_XI, (section,), "reviewed dimensional branches")
        code.computed_standard(
            id=f"{district.casefold()}:maximum_front_setback",
            label="Maximum front setback", when=(eq("district", district),),
            metric="front_setback", operator="<=",
            formula="sd_front_setback_adjacent_average_cap_20", source=source,
            review_status="verified",
        )
        computed_count += 1
        code.computed_standard(
            id=f"{district.casefold()}:side_setback_adjacent_r1_r4",
            label="Side setback beside R1–R4", when=(
                eq("district", district), eq("adjacent_to_r1_r4", True),
            ), metric="side_setback", operator=">=", formula="formula_a",
            source=source, review_status="verified",
        )
        computed_count += 1

        def maximum(rule_id: str, value: float, when) -> None:
            nonlocal rule_count
            code.standard(
                id=f"{district.casefold()}:{rule_id}", label="Maximum building height",
                metric="height", operator="<=", value=value, unit="feet",
                when=(eq("district", district), *when), source=source,
                review_status="verified",
            )
            rule_count += 1

        maximum("nonmixed_height", nonmixed_height, (eq("mixed_use_building", False),))
        maximum("mixed_height_narrow_right_of_way", mixed_height, (
            eq("mixed_use_building", True), at_most("abutting_right_of_way_width", row_threshold),
        ))
        maximum("mixed_height_near_r1_r3", mixed_height, (
            eq("mixed_use_building", True), greater_than("abutting_right_of_way_width", row_threshold),
            less_than("distance_to_r1_r3", 40),
        ))
        code.computed_standard(
            id=f"{district.casefold()}:mixed_height_bonus",
            label="Maximum mixed-use building height", when=(
                eq("district", district), eq("mixed_use_building", True),
                greater_than("abutting_right_of_way_width", row_threshold),
                at_least("distance_to_r1_r3", 40),
            ), metric="height", operator="<=",
            formula=f"{district.casefold()}_mixed_use_height_bonus",
            source=source, review_status="verified",
        )
        computed_count += 1

        def rear(rule_id: str, value: float, when) -> None:
            nonlocal rule_count
            code.minimum(
                id=f"{district.casefold()}:{rule_id}", label="Minimum rear setback",
                metric="rear_setback", value=value, unit="feet",
                when=(eq("district", district), *when), source=source,
                review_status="verified",
            )
            rule_count += 1

        rear("single_story_no_rear_street", 10, (
            eq("building_stories", 1), eq("rear_street_or_alley", False),
        ))
        rear("multistory_protected_neighbor_across_rear_street", 10, (
            greater_than("building_stories", 1), eq("protected_rear_neighbor", True),
            eq("rear_street_or_alley", True),
        ))
        rear("multistory_protected_neighbor_no_rear_street", 20, (
            greater_than("building_stories", 1), eq("protected_rear_neighbor", True),
            eq("rear_street_or_alley", False),
        ))
        rear("dwelling_building_rear_street", 10, (
            eq("contains_dwellings_other_than_single_two_family", True),
            eq("rear_street_or_alley", True),
        ))
        rear("dwelling_building_no_rear_street", 20, (
            eq("contains_dwellings_other_than_single_two_family", True),
            eq("rear_street_or_alley", False),
        ))

        code.provision(
            id=f"{district.casefold()}:no_parking_before_front_facade",
            effect="prohibition",
            text="Off-street parking is prohibited between the street and front façade.",
            when=(eq("district", district),), source=source, review_status="verified",
        )
        provision_count += 1
    return {
        "rules": rule_count,
        "computedRules": computed_count,
        "formulas": 3,
        "provisions": provision_count,
    }
