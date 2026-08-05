"""Reviewed Detroit declarations compiled by the zoning codebook DSL."""

from __future__ import annotations

from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source, eq

ARTICLE_XIII = "ARTICLE_XIII.municode.json"
VERSION = "detroit-zoning-ordinance-chapter-50-repository-snapshot"


def build_detroit_code() -> OrdinanceBuilder:
    code = OrdinanceBuilder("Detroit", VERSION)
    for number in range(1, 7):
        code.district(f"R{number}", f"R{number} residential district", "residential")
    code.use("one_family_dwelling", "One-family dwelling", "residential")
    code.use("two_family_dwelling", "Two-family dwelling", "residential")

    for number in range(1, 7):
        district = f"R{number}"
        _residential_scenario(
            code, district, "one_family_dwelling", area=5_000, width=50
        )
    for number in range(2, 7):
        district = f"R{number}"
        _residential_scenario(
            code,
            district,
            "two_family_dwelling",
            area=6_000,
            width=60 if district == "R3" else 55,
        )
    return code


def _residential_scenario(
    code: OrdinanceBuilder,
    district: str,
    use: str,
    *,
    area: float,
    width: float,
) -> None:
    section = f"50-13-{int(district[1:]) + 1}"
    conditions = (
        eq("district", district),
        eq("use", use),
        eq("building_role", "principal"),
    )
    shared = dict(when=conditions)
    code.minimum(
        id=f"{district.lower()}:{use}:minimum_lot_area",
        label="Minimum lot area",
        metric="lot_area",
        value=area,
        unit="square_feet",
        source=Source(ARTICLE_XIII, (section, "50-13-222"), f"{area:,.0f}"),
        exceptions=("lot_of_record", "combined_zoning_lot", "approved_relief"),
        **shared,
    )
    code.minimum(
        id=f"{district.lower()}:{use}:minimum_lot_width",
        label="Minimum lot width",
        metric="lot_width",
        value=width,
        unit="feet",
        source=Source(ARTICLE_XIII, (section, "50-13-222"), f"{width:g}"),
        exceptions=("lot_of_record", "combined_zoning_lot", "approved_relief"),
        **shared,
    )
    for slug, label, metric, value, source_value, ref in (
        ("front", "Minimum front setback", "front_setback", 20, "20", "50-16-382"),
        ("side", "Minimum side setback", "side_setback", 4, "4 ft. minimum/ 14 ft. combined", "50-16-382"),
        ("combined-side", "Minimum combined side setback", "combined_side_setback", 14, "4 ft. minimum/ 14 ft. combined", "50-16-382"),
        ("rear", "Minimum rear setback", "rear_setback", 30, "30", "50-13-231"),
    ):
        code.minimum(
            id=f"{district.lower()}:{use}:minimum_{slug}_setback",
            label=label,
            metric=metric,
            value=value,
            unit="feet",
            source=Source(ARTICLE_XIII, (section, ref), source_value),
            exceptions=("approved_relief",),
            **shared,
        )
