from pathlib import Path

from strongtowns_detroit.zoning.applicability_scopes import compile_applicability_scopes
from strongtowns_detroit.zoning.source_model import compile_source_corpus

ROOT = Path(__file__).resolve().parents[1]


def scopes():
    return compile_applicability_scopes(compile_source_corpus(ROOT / "resources"))


def test_article_xi_distinguishes_districts_from_overlays():
    package = scopes()
    assert package["coverage"]["specialPurposeDistricts"] == 12
    assert package["coverage"]["overlayAreas"] == 6
    assert {item.get("code") for item in package["scopes"] if item.get("code")} == {
        "PD", "P1", "PC", "PCA", "TM", "PR", "W1", "MKT",
        "SD1", "SD2", "SD4", "SD5",
    }


def test_overlay_sections_follow_their_subdivision_heading():
    package = scopes()
    gateway = next(item for item in package["scopes"] if item["id"] == "overlay:a")
    traditional = next(item for item in package["scopes"] if item["id"] == "overlay:b")
    assert gateway["sections"][0] == "50-11-361"
    assert traditional["sections"][0] == "50-11-381"
    assert not set(gateway["sections"]) & set(traditional["sections"])
