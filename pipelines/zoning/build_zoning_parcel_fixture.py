#!/usr/bin/env python3
"""Build one audited parcel-detail contract for the Land Forum prototype.

The default parcel, 1573 Livernois, is a straightforward R2 assessor parcel
with one current Base Units footprint and a high-confidence front edge. It is
an implementation fixture, not a claim about the structure's legal status.
"""

from __future__ import annotations

import argparse
import json
import mmap
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = ROOT / "projects/detroit-land-use-forum/base-units-geometry"
PARCELS = ROOT / "pipelines/parcel-data/Parcels.geojson"
BUILDINGS = GEOMETRY / "data/base_units_buildings.geojson"
FRONTAGES = GEOMETRY / "output/geometry_frontage_sample.gpkg"
DEFAULT_OUTPUT = (
    ROOT / "sites/land-forum/public/data/zoning/parcels/18007150.json"
)

sys.path.insert(0, str(ROOT / "projects/detroit-land-use-forum/parcel-geometry"))
from setback_envelope_model import (  # noqa: E402
    principal_footprint_outside_area,
    single_family_setback_envelope,
)

from strongtowns_detroit.zoning.parcel_evaluation import evaluate_parcel_json  # noqa: E402
from strongtowns_detroit.zoning.rules import EvaluationStatus  # noqa: E402

EXECUTABLE_RULES = ROOT / "data/zoning-ordinance/executable-rules.json"


def feature_by_property(path: Path, key: str, value: str) -> dict:
    """Read one feature from a flat GeoJSON FeatureCollection without loading it."""
    needle = json.dumps(key).encode() + b":" + json.dumps(value).encode()
    marker = b'{"type":"Feature"'
    with path.open("rb") as source:
        data = mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ)
        position = data.find(needle)
        if position < 0:
            raise KeyError(f"{key}={value!r} not found in {path}")
        start = data.rfind(marker, 0, position)
        end = data.find(b'},{"type":"Feature"', position)
        if end < 0:
            end = data.find(b"]}", position)
        else:
            end += 1
        return json.loads(data[start:end])


def in_crs(geometry, source_crs, target_crs):
    return gpd.GeoSeries([geometry], crs=source_crs).to_crs(target_crs).iloc[0]


def web_geometry(geometry, source_crs):
    return mapping(in_crs(geometry, source_crs, 4326))


def build(parcel_id: str, output: Path) -> dict:
    parcel_feature = feature_by_property(PARCELS, "parcel_id", parcel_id)
    building_feature = feature_by_property(BUILDINGS, "parcel_id", parcel_id)
    properties = parcel_feature["properties"]
    parcel = in_crs(shape(parcel_feature["geometry"]), 3857, 2898)
    building = in_crs(shape(building_feature["geometry"]), 4326, 2898)

    parcel_key = parcel_id.replace(".", "")
    frontages = gpd.read_file(
        FRONTAGES,
        where=f"parcel_key = '{parcel_key}'",
    ).to_crs(2898)
    if frontages.empty:
        # GeoJSON/GPKG driver support varies; this remains bounded to the
        # indexed GeoPackage and is safe as a fallback.
        frontages = gpd.read_file(FRONTAGES).to_crs(2898)
        frontages = frontages[frontages["parcel_key"].eq(parcel_key)]
    if len(frontages) != 1:
        raise ValueError(f"expected one front edge for {parcel_id}, got {len(frontages)}")
    frontage = frontages.iloc[0]
    front_edge = frontage.geometry

    package = json.loads(EXECUTABLE_RULES.read_text(encoding="utf-8"))
    scenario = "one_family_dwelling"
    rule_results = evaluate_parcel_json(
        package,
        district=properties["zoning_district"],
        use=scenario,
        building_role="principal",
        measurements={
            "lot_area": properties.get("total_square_footage"),
            "lot_width": properties.get("frontage"),
        },
    )
    envelope = single_family_setback_envelope(parcel, front_edge)
    if envelope is None:
        raise ValueError("representative parcel did not produce an envelope")
    alternatives = [envelope.option_left_4, envelope.option_right_4]
    outside_areas = [building.difference(item).area for item in alternatives]
    best_index = min(range(2), key=outside_areas.__getitem__)
    outside = building.difference(alternatives[best_index])
    outside_area = principal_footprint_outside_area(building, envelope)
    tolerance = max(10.0, building.area * .01)
    setback_status = (
        EvaluationStatus.FAILS if outside_area > tolerance
        else EvaluationStatus.MEETS
    )
    setback_metrics = {
        "front_setback", "side_setback", "combined_side_setback", "rear_setback"
    }
    source_refs = sorted({
        ref
        for result in rule_results
        if result["requirement"]["metric"] in setback_metrics
        for ref in result["source"]["sections"]
    })

    result = {
        "schemaVersion": "zoning-parcel-v1",
        "parcel": {
            "id": parcel_id,
            "address": properties.get("address"),
            "district": properties.get("zoning_district"),
            "recordedUse": properties.get("use_code_description"),
            "scenario": scenario,
            "geometry": web_geometry(parcel, 2898),
        },
        "buildings": [{
            "id": building_feature["properties"].get("building_id"),
            "status": building_feature["properties"].get("status"),
            "role": "principal_by_largest_current_footprint",
            "areaSqft": round(building.area, 2),
            "geometry": web_geometry(building, 2898),
        }],
        "frontEdge": {
            "confidence": frontage.get("frontage_confidence"),
            "source": frontage.get("frontage_source"),
            "geometry": web_geometry(front_edge, 2898),
        },
        "setbackEnvelope": {
            "status": setback_status.value,
            "outsideAreaSqft": round(outside_area, 2),
            "classificationToleranceSqft": round(tolerance, 2),
            "selectedAlternative": best_index + 1,
            "alternatives": [web_geometry(item, 2898) for item in alternatives],
            "footprintOutsideEnvelope": web_geometry(outside, 2898),
            "sourceRefs": source_refs,
            "explanation": (
                "The current principal footprint extends beyond both ordinary "
                "side-yard allocations." if setback_status == EvaluationStatus.FAILS
                else "The current principal footprint fits an ordinary setback envelope."
            ),
        },
        "dimensionalRules": [
            result for result in rule_results
            if result["requirement"]["metric"] in {"lot_area", "lot_width"}
        ],
        "limitations": [
            "This compares recorded geometry with current dimensional standards; it does not determine whether the existing structure is unlawful.",
            "The assessor parcel is treated as the candidate zoning lot for this prototype.",
            "Recorded assessor frontage is used as a lot-width proxy.",
            "Variances, adjustments, lot-of-record protection, combined zoning lots, and other approvals have not been researched for this parcel.",
        ],
        "sources": {
            "parcel": "City of Detroit assessor parcel data",
            "buildingAndStreet": "City of Detroit Base Units",
            "ordinance": "Detroit Zoning Ordinance, Chapter 50 repository snapshot",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parcel-id", default="18007150.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.parcel_id, args.output)
    print(json.dumps({
        "output": str(args.output),
        "parcel": result["parcel"],
        "setbackStatus": result["setbackEnvelope"]["status"],
    }, indent=2))


if __name__ == "__main__":
    main()
