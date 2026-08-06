"""Reviewed permission branches whose table codes depend on operative prose."""

from __future__ import annotations

import re

from strongtowns_detroit.zoning.codebook import (
    OrdinanceBuilder,
    Predicate,
    Source,
    at_least,
    at_most,
    eq,
    greater_than,
    less_than,
)

ARTICLE_XII = "ARTICLE_XII.municode.json"


def add_reviewed_conditional_permissions(code: OrdinanceBuilder) -> int:
    declarations: list[tuple[str, str, str, str, tuple[Predicate, ...], str, str]] = []

    def add(
        use: str, label: str, district: str, permission: str,
        when: tuple[Predicate, ...], section: str, source_value: str,
    ) -> None:
        slug = _slug(label)
        branch = _slug(source_value)
        declarations.append((
            f"{district.casefold()}:{slug}:{branch}", use, label, district,
            when, permission, section,
        ))

    # §50-12-162(2), (6): multiple-family dwellings.
    add("multiple_family_dwelling", "Multiple-family dwelling", "R3", "allowed_by_right",
        (less_than("efficiency_unit_share", 0.5),), "50-12-162", "efficiency share under half")
    add("multiple_family_dwelling", "Multiple-family dwelling", "R3", "conditional_use",
        (at_least("efficiency_unit_share", 0.5),), "50-12-162", "efficiency share half or more")
    for district in ("B5", "PCA"):
        add("multiple_family_dwelling", "Multiple-family dwelling", district, "allowed_by_right",
            (eq("ground_floor_commercial_or_pedestrian_space", True),), "50-12-162",
            "pedestrian ground floor")
        add("multiple_family_dwelling", "Multiple-family dwelling", district, "conditional_use",
            (eq("ground_floor_commercial_or_pedestrian_space", False),), "50-12-162",
            "no pedestrian ground floor")

    # §50-12-217(3), (4): classifications and neighborhood/size conditions.
    for district in ("M1", "M2", "M3", "M4"):
        add("brewpub_microproducer", "Brewpub or micro-producer", district, "conditional_use",
            (eq("regulated_or_controlled_use", True),), "50-12-217", "regulated or controlled")
        add("brewpub_microproducer", "Brewpub or micro-producer", district, "allowed_by_right",
            (eq("regulated_or_controlled_use", False),), "50-12-217", "not regulated or controlled")
    add("brewpub_microproducer", "Brewpub or micro-producer", "SD1", "allowed_by_right",
        (at_most("gross_floor_area", 3000), eq("adjacent_low_density_home_off_thoroughfare", False)),
        "50-12-217", "small and not adjacent")
    add("brewpub_microproducer", "Brewpub or micro-producer", "SD1", "conditional_use",
        (greater_than("gross_floor_area", 3000),), "50-12-217", "over 3000 square feet")
    add("brewpub_microproducer", "Brewpub or micro-producer", "SD1", "conditional_use",
        (at_most("gross_floor_area", 3000), eq("adjacent_low_density_home_off_thoroughfare", True)),
        "50-12-217", "small and adjacent")

    # §50-12-186: post offices in SD4.
    add("post_office", "Post office", "SD4", "allowed_by_right",
        (eq("part_of_multitenant_mixed_use_multistory_building", True),), "50-12-186",
        "part of multitenant mixed use multistory building")
    add("post_office", "Post office", "SD4", "conditional_use",
        (eq("part_of_multitenant_mixed_use_multistory_building", False),), "50-12-186",
        "not part of multitenant mixed use multistory building")

    # §50-12-159(4)--(6): lofts and residential-commercial combinations.
    for district in ("B2", "B3"):
        add("loft", "Loft", district, "allowed_by_right",
            (eq("traditional_main_street_overlay", True), eq("combined_with_permitted_commercial_or_industrial_use", True)),
            "50-12-159", "traditional main street combined use")
        add("loft", "Loft", district, "conditional_use",
            (eq("traditional_main_street_overlay", False),), "50-12-159", "outside traditional main street")
        add("loft", "Loft", district, "conditional_use",
            (eq("traditional_main_street_overlay", True), eq("combined_with_permitted_commercial_or_industrial_use", False)),
            "50-12-159", "traditional main street not combined")
    add("loft", "Loft", "B4", "allowed_by_right",
        (eq("central_business_district", True),), "50-12-159", "central business district")
    add("loft", "Loft", "B4", "allowed_by_right",
        (eq("traditional_main_street_overlay", True),), "50-12-159", "traditional main street")
    add("loft", "Loft", "B4", "conditional_use",
        (eq("central_business_district", False), eq("traditional_main_street_overlay", False)),
        "50-12-159", "outside cbd and traditional main street")
    for district in ("B2", "B3", "B4"):
        add("residential_with_commercial", "Residential use combined with commercial uses",
            district, "allowed_by_right", (eq("traditional_main_street_overlay", True),),
            "50-12-159", "traditional main street")
        add("residential_with_commercial", "Residential use combined with commercial uses",
            district, "conditional_use", (eq("traditional_main_street_overlay", False),),
            "50-12-159", "outside traditional main street")

    # §50-12-298(b): MKT offices.
    add("business_or_professional_office", "Business or professional office", "MKT",
        "conditional_use", (eq("newly_constructed_building", True),), "50-12-298", "new building")
    add("business_or_professional_office", "Business or professional office", "MKT",
        "conditional_use", (eq("newly_constructed_building", False), greater_than("expansion_to_first_floor_area_ratio", 2)),
        "50-12-298", "existing building expansion over 200 percent")
    add("business_or_professional_office", "Business or professional office", "MKT",
        "allowed_by_right", (eq("newly_constructed_building", False), at_most("expansion_to_first_floor_area_ratio", 2)),
        "50-12-298", "existing building expansion at most 200 percent")

    # §50-12-301(3): parking structures.
    for district in ("B5", "PC", "PCA"):
        add("parking_structure", "Parking structure", district, "allowed_by_right",
            (at_least("street_facing_ground_floor_pedestrian_space_share", 0.30),),
            "50-12-301", "at least 30 percent pedestrian ground floor")
        add("parking_structure", "Parking structure", district, "conditional_use",
            (less_than("street_facing_ground_floor_pedestrian_space_share", 0.30),),
            "50-12-301", "under 30 percent pedestrian ground floor")

    # Simple numeric/use-type branches.
    for district, threshold in (("SD1", 3000),):
        add("rental_hall", "Rental hall", district, "allowed_by_right",
            (at_most("gross_floor_area", threshold),), "50-12-309", "at most 3000 square feet")
        add("rental_hall", "Rental hall", district, "conditional_use",
            (greater_than("gross_floor_area", threshold),), "50-12-309", "over 3000 square feet")
    add("printing_or_engraving_shop", "Printing or engraving shop", "SD2", "allowed_by_right",
        (at_most("gross_floor_area", 5000), at_least("retail_floor_area_share", 0.10)),
        "50-12-323", "at most 5000 square feet and ten percent retail")
    add("printing_or_engraving_shop", "Printing or engraving shop", "SD2", "conditional_use",
        (greater_than("gross_floor_area", 5000), at_least("retail_floor_area_share", 0.10)),
        "50-12-323", "over 5000 square feet and ten percent retail")
    add("theater_excluding_concert_cafe", "Theater excluding concert cafe", "SD2",
        "allowed_by_right", (at_most("fixed_seats", 150),), "50-12-317", "at most 150 seats")
    add("theater_excluding_concert_cafe", "Theater excluding concert cafe", "SD2",
        "conditional_use", (greater_than("fixed_seats", 150),), "50-12-317", "over 150 seats")
    add("poultry_or_small_game_processing", "Poultry or small game processing", "MKT",
        "allowed_by_right", (at_most("gross_floor_area", 5000),), "50-12-315", "at most 5000 square feet")
    add("poultry_or_small_game_processing", "Poultry or small game processing", "MKT",
        "conditional_use", (greater_than("gross_floor_area", 5000),), "50-12-315", "over 5000 square feet")
    add("warehousing_or_storage", "Warehousing or storage", "MKT", "allowed_by_right",
        (eq("stores_food_related_products", True),), "50-12-358", "food related products")
    add("warehousing_or_storage", "Warehousing or storage", "MKT", "conditional_use",
        (eq("stores_food_related_products", False),), "50-12-358", "non food related products")

    # §50-12-353: general trade services in B2, SD1, and SD2.
    add("general_trade_service", "General trade service", "B2", "allowed_by_right",
        (eq("cabinet_making", False), at_most("gross_floor_area", 4000),
         at_least("retail_floor_area_share", 0.10), eq("traditional_main_street_overlay", True)),
        "50-12-353", "non cabinet compliant traditional main street")
    add("general_trade_service", "General trade service", "B2", "conditional_use",
        (eq("cabinet_making", False), eq("traditional_main_street_overlay", False)),
        "50-12-353", "non cabinet outside traditional main street")
    add("general_trade_service", "General trade service", "B2", "conditional_use",
        (eq("cabinet_making", True), at_most("gross_floor_area", 4000),
         at_least("retail_floor_area_share", 0.10), eq("traditional_main_street_overlay", True)),
        "50-12-353", "cabinet compliant traditional main street")
    for district, maximum in (("SD1", 4000), ("SD2", 5000)):
        for cabinet, permission in ((False, "allowed_by_right"), (True, "conditional_use")):
            add("general_trade_service", "General trade service", district, permission,
                (eq("cabinet_making", cabinet), at_most("gross_floor_area", maximum),
                 at_least("retail_floor_area_share", 0.10)),
                "50-12-353", f"{'cabinet' if cabinet else 'non cabinet'} compliant")

    # §50-12-310(7): B5/PCA carry-out and fast-food project form.
    for use, label in (
        ("carry_out_restaurant", "Carry-out restaurant"),
        ("fast_food_restaurant", "Fast-food restaurant"),
    ):
        for district in ("B5", "PCA"):
            add(use, label, district, "allowed_by_right",
                (eq("has_drive_up_or_drive_through", False),
                 eq("integrated_multistory_mixed_or_multitenant", True)),
                "50-12-310", "no drive through integrated multistory")
            add(use, label, district, "conditional_use",
                (eq("has_drive_up_or_drive_through", False),
                 eq("integrated_multistory_mixed_or_multitenant", False)),
                "50-12-310", "no drive through stand alone")
        add(use, label, "B5", "conditional_use",
            (eq("has_drive_up_or_drive_through", True),),
            "50-12-310", "drive up or drive through")

    # §50-12-299(9)e: B4 commercial versus accessory parking on a Gateway.
    add("parking_lot_or_area", "Parking lot or parking area", "B4", "conditional_use",
        (eq("parking_function", "commercial"), eq("gateway_radial_thoroughfare", True)),
        "50-12-299", "commercial parking on gateway")
    add("parking_lot_or_area", "Parking lot or parking area", "B4", "allowed_by_right",
        (eq("parking_function", "accessory"),), "50-12-299", "accessory parking")

    # Small-production branches share the 4,000-square-foot / ten-percent
    # retail / Traditional Main Street test stated in their respective sections.
    def production_branches(
        use: str, label: str, district: str, section: str,
        *, b2_maximum: float | None = None, outside_always_conditional: bool = True,
    ) -> None:
        compliant = (
            at_most("gross_floor_area", 4000),
            at_least("retail_floor_area_share", 0.10),
            eq("traditional_main_street_overlay", True),
        )
        add(use, label, district, "allowed_by_right", compliant, section,
            "small retail component traditional main street")
        if outside_always_conditional:
            outside = (eq("traditional_main_street_overlay", False),)
            if b2_maximum is not None:
                outside += (at_most("gross_floor_area", b2_maximum),)
            add(use, label, district, "conditional_use", outside, section,
                "outside traditional main street")
        add(use, label, district, "conditional_use",
            (eq("traditional_main_street_overlay", True),
             at_most("gross_floor_area", 4000),
             less_than("retail_floor_area_share", 0.10)),
            section, "small traditional main street under ten percent retail")
        over_small_limit = (
            eq("traditional_main_street_overlay", True),
            greater_than("gross_floor_area", 4000),
        )
        if b2_maximum is not None:
            over_small_limit += (at_most("gross_floor_area", b2_maximum),)
        add(use, label, district, "conditional_use", over_small_limit,
            section, "traditional main street over 4000 square feet")

    production_branches(
        "confection_manufacturing", "Confection manufacturing", "B2", "50-12-334",
        b2_maximum=6000,
    )
    add("confection_manufacturing", "Confection manufacturing", "B2", "not_allowed",
        (greater_than("gross_floor_area", 6000),), "50-12-334", "over 6000 square feet")
    production_branches(
        "confection_manufacturing", "Confection manufacturing", "B4", "50-12-334")
    for use, label, section in (
        ("food_catering_establishment", "Food catering establishment", "50-12-336"),
        ("jewelry_manufacturing", "Jewelry manufacturing", "50-12-340"),
        ("wearing_apparel_manufacturing", "Wearing apparel manufacturing", "50-12-360"),
    ):
        districts = ("B2", "B4") if use == "food_catering_establishment" else ("B4",)
        for district in districts:
            production_branches(use, label, district, section)
    # B2 lithographing is only conditionally authorized outside the overlay
    # when it remains at or below 4,000 square feet; other omitted cases stay unknown.
    add("lithographing_shop", "Lithographing shop", "B2", "allowed_by_right",
        (at_most("gross_floor_area", 4000), at_least("retail_floor_area_share", 0.10),
         eq("traditional_main_street_overlay", True)),
        "50-12-342", "small retail component traditional main street")
    add("lithographing_shop", "Lithographing shop", "B2", "conditional_use",
        (at_most("gross_floor_area", 4000), eq("traditional_main_street_overlay", False)),
        "50-12-342", "small outside traditional main street")
    production_branches(
        "lithographing_shop", "Lithographing shop", "B4", "50-12-342")

    # MKT barber/beauty text resolves two building-form cases; upper floors of
    # multi-story buildings are not assigned an outcome by this section.
    add("barber_or_beauty_shop", "Barber or beauty shop", "MKT", "not_allowed",
        (eq("single_story_building", False), eq("located_on_first_floor", True)),
        "50-12-235", "first floor of multistory building")
    add("barber_or_beauty_shop", "Barber or beauty shop", "MKT", "conditional_use",
        (eq("single_story_building", True),), "50-12-235", "single story building")

    # §50-12-220(4): SD1 alcohol-serving establishments.
    alcohol = "alcohol_for_on_premises_consumption"
    label = "Alcohol for on-premises consumption"
    add(alcohol, label, "SD1", "allowed_by_right",
        (at_most("gross_floor_area", 3000),
         eq("adjacent_low_density_home_off_thoroughfare", False)),
        "50-12-220", "small and not adjacent")
    add(alcohol, label, "SD1", "conditional_use",
        (greater_than("gross_floor_area", 3000),), "50-12-220", "over 3000 square feet")
    add(alcohol, label, "SD1", "conditional_use",
        (at_most("gross_floor_area", 3000),
         eq("adjacent_low_density_home_off_thoroughfare", True)),
        "50-12-220", "small and adjacent")

    for rule_id, use, label, district, when, permission, section in declarations:
        code.district(district, f"{district} district", _district_category(district))
        code.use(use, label, "ordinance_use")
        code.permission(
            id=rule_id, use=use, district=district, permission=permission, when=when,
            conditions=(section,),
            source=Source(
                ARTICLE_XII, (section,), label,
                "Reviewed branch of a composite C/R or R/C permission cell.",
            ),
            review_status="verified",
        )
    return len(declarations)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _district_category(district: str) -> str:
    if district.startswith("R"):
        return "residential"
    if district.startswith("B"):
        return "business"
    if district.startswith("M"):
        return "industrial"
    return "special_or_overlay"
