"""Reviewed antenna rules from Article XII, Division 3, Subdivision G."""

from __future__ import annotations

from strongtowns_detroit.zoning.codebook import (
    OrdinanceBuilder,
    Source,
    at_most,
    eq,
    greater_than,
    less_than,
)

ARTICLE_XI = "ARTICLE_XI.municode.json"
ARTICLE_XII = "ARTICLE_XII.municode.json"


def add_reviewed_antenna_rules(code: OrdinanceBuilder) -> dict[str, int]:
    code.use("antenna", "Antenna", "other_use")
    code.use("category_d_antenna_tower", "Category D antenna tower", "other_use")
    permission_count = 0

    def permission(
        district: str, outcome: str, branch: str, when=(),
        sections=("50-12-396",), document=ARTICLE_XII,
    ) -> None:
        nonlocal permission_count
        code.district(district, f"{district} district", _district_category(district))
        code.permission(
            id=f"{district.casefold()}:category_d_antenna:{branch}",
            use="category_d_antenna_tower", district=district,
            permission=outcome, when=tuple(when), conditions=sections,
            source=Source(
                document, sections, branch.replace("_", " "),
                "Reviewed Category D branch; exact 120-foot boundary remains unresolved "
                "where the source contrasts 'more than' with 'less than'.",
            ),
            review_status="verified",
        )
        permission_count += 1

    # §50-12-371 excludes all antennas from P1.
    code.district("P1", "P1 district", "special_or_overlay")
    code.permission(
        id="p1:antenna:not_permitted", use="antenna", district="P1",
        permission="not_allowed", conditions=("50-12-371",),
        source=Source(ARTICLE_XII, ("50-12-371",), "except the P1 District"),
        review_status="verified",
    )
    permission_count += 1

    # R1--R3: conditional only on a lighted athletic field; otherwise prohibited.
    for district in ("R1", "R2", "R3"):
        permission(district, "conditional_use", "lighted_athletic_field",
                   (eq("on_lighted_athletic_field", True),))
        permission(district, "not_allowed", "not_on_lighted_athletic_field",
                   (eq("on_lighted_athletic_field", False),))

    # R4--R6, B1--B4, PR: distance from both low-density zoning and homes controls.
    for district in ("R4", "R5", "R6", "B1", "B2", "B3", "B4", "PR"):
        permission(district, "conditional_use", "farther_than_120_feet",
                   (greater_than("distance_to_r1_r3_or_single_two_family_home", 120),))
        permission(district, "not_allowed", "within_120_feet",
                   (at_most("distance_to_r1_r3_or_single_two_family_home", 120),))

    # B5/B6/PCA/SD2 have an express by-right branch beyond 120 feet from a home.
    for district in ("B5", "B6", "PCA", "SD2"):
        permission(district, "allowed_by_right", "farther_than_120_feet_from_home",
                   (greater_than("distance_to_single_two_family_home", 120),))

    # Industrial districts and TM pair the by-right and less-than-120 prohibition.
    for district in ("M1", "M2", "M3", "M4", "M5", "TM"):
        permission(district, "allowed_by_right", "farther_than_120_feet_from_home",
                   (greater_than("distance_to_single_two_family_home", 120),))
        permission(district, "not_allowed", "less_than_120_feet_from_home",
                   (less_than("distance_to_single_two_family_home", 120),))

    # SD4's special-purpose article supplies the by-right accessory exception.
    permission("SD4", "allowed_by_right", "accessory_to_allowed_principal_use",
               (eq("accessory_to_allowed_sd4_principal_use", True),),
               sections=("50-11-294", "50-12-396"), document=ARTICLE_XI)
    permission("SD4", "not_allowed", "not_accessory_to_allowed_principal_use",
               (eq("accessory_to_allowed_sd4_principal_use", False),))

    # Promote general provisions that are explicit and independently useful.
    provisions = (
        ("antenna:permit_threshold", "procedure",
         "A building permit is required above the height, dish-diameter, or area thresholds.",
         "50-12-373"),
        ("antenna:no_property_line_encroachment", "prohibition",
         "Antennas may not cross property lines or project into required setbacks.",
         "50-12-378"),
        ("antenna:power_line_clearance", "requirement",
         "Antennas must remain at least 24 inches from telephone or power lines.",
         "50-12-378"),
        ("antenna:no_sign_markings", "prohibition",
         "Lettering, numbers, symbols, illustrations, and artistic renderings are prohibited.",
         "50-12-379"),
        ("antenna:same_lot", "requirement",
         "An accessory antenna must be on the same zoning lot as the principal structure.",
         "50-12-381"),
        ("antenna:category_d_committee_review", "procedure",
         "Every Category D antenna requires Wireless Telecommunications Site Review Committee review.",
         "50-12-396"),
    )
    for provision_id, effect, text, section in provisions:
        code.provision(
            id=provision_id, effect=effect, text=text,
            when=(eq("use_category", "antenna"),),
            source=Source(ARTICLE_XII, (section,), text),
            review_status="verified",
        )
    return {"permissions": permission_count, "provisions": len(provisions)}


def _district_category(district: str) -> str:
    if district.startswith("R"):
        return "residential"
    if district.startswith("B"):
        return "business"
    if district.startswith("M"):
        return "industrial"
    return "special_or_overlay"
