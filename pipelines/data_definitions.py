"""Repository data contracts and pipeline registrations."""

from pathlib import Path

from strongtowns_detroit.data import (
    AcquisitionPolicy,
    ArchiveTier,
    DataAsset,
    DataPipeline,
    DatasetContract,
    data_pipeline,
)
from strongtowns_detroit.data.geospatial import canonical_geojson_builder
from strongtowns_detroit.data.arcgis import collect_layer
from strongtowns_detroit.data import BuildMetadata
from strongtowns_detroit.data.routing import build_routing_anchor_tables
import geopandas as gpd
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from strongtowns_detroit.data.traveltime import (
    build_request_ledger,
    execute_request_ledger,
)
from strongtowns_detroit.data.osm import collect_osm_pois, normalize_osm_features
from strongtowns_detroit.data.catalog import (
    build_query_catalog,
    validate_query_catalog_snapshot,
)


def raw_contract(name: str) -> DatasetContract:
    return DatasetContract(name=name, version="1.0.0")


def geo_contract(
    name: str, primary_key: str, geometry_types: tuple[str, ...]
) -> DatasetContract:
    return DatasetContract(
        name=name,
        version="1.0.0",
        required_columns={primary_key: "string", "source_row": "int64"},
        primary_key=(primary_key,),
        geometry_types=geometry_types,
        crs="EPSG:4326",
        accepted_artifact="accepted.parquet",
        rejects_artifact="rejects.parquet",
    )


PARCELS_RAW = DataAsset(
    "detroit.parcels.raw",
    Path("data/sources/detroit-parcels"),
    raw_contract("detroit.parcels.raw"),
    ArchiveTier.SOURCE,
    legacy_artifacts={"raw.geojson": Path("pipelines/parcel-data/Parcels.geojson")},
    legacy_counts={"records": 378_366},
)
ADDRESSES_RAW = DataAsset(
    "detroit.base-units.addresses.raw",
    Path("data/sources/detroit-base-units-addresses"),
    raw_contract("detroit.base-units.addresses.raw"),
    ArchiveTier.SOURCE,
    legacy_artifacts={
        "raw.geojson": Path(
            "projects/detroit-land-use-forum/base-units-geometry/data/base_units_addresses.geojson"
        )
    },
    legacy_counts={"records": 486_540},
)
STREETS_RAW = DataAsset(
    "detroit.base-units.streets.raw",
    Path("data/sources/detroit-base-units-streets"),
    raw_contract("detroit.base-units.streets.raw"),
    ArchiveTier.SOURCE,
    legacy_artifacts={
        "raw.geojson": Path(
            "projects/detroit-land-use-forum/base-units-geometry/data/base_units_streets.geojson"
        )
    },
    legacy_counts={"records": 36_104},
)
BUILDINGS_RAW = DataAsset(
    "detroit.base-units.buildings.raw",
    Path("data/sources/detroit-base-units-buildings"),
    raw_contract("detroit.base-units.buildings.raw"),
    ArchiveTier.SOURCE,
    legacy_artifacts={
        "raw.geojson": Path(
            "projects/detroit-land-use-forum/base-units-geometry/data/base_units_buildings.geojson"
        )
    },
    legacy_counts={"records": 364_095},
)


PARCEL_LAYER = (
    "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/"
    "parcel_file_current/FeatureServer/0"
)
BASE_UNITS_SERVICE = (
    "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/"
    "BaseUnitFeatures/FeatureServer"
)


def fetch_arcgis_outputs(endpoints: dict[str, str]):
    def fetch(context):
        metadata = {}
        for asset_id, endpoint in endpoints.items():
            collection = collect_layer(
                endpoint,
                context.staging[asset_id] / "raw.geojson",
                cache_root=context.root / "data" / ".cache" / "arcgis",
            )
            metadata[asset_id] = BuildMetadata(
                counts={"records": collection.feature_count},
                source={
                    "provider": "ArcGIS FeatureServer",
                    "url": endpoint,
                    "fingerprint": collection.cache_fingerprint,
                    "before": collection.before,
                    "after": collection.after,
                    "started_at": collection.started_at,
                    "completed_at": collection.completed_at,
                },
            )
        return metadata

    return fetch


@data_pipeline("detroit-parcels-source")
def detroit_parcels_source() -> DataPipeline:
    return DataPipeline(
        "detroit-parcels-source", (), (PARCELS_RAW,),
        fetch=fetch_arcgis_outputs({PARCELS_RAW.id: PARCEL_LAYER}),
        acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK,
        description="Immutable snapshots of Detroit's current parcel service.",
    )


@data_pipeline("detroit-base-units-source")
def detroit_base_units_source() -> DataPipeline:
    return DataPipeline(
        "detroit-base-units-source", (),
        (ADDRESSES_RAW, STREETS_RAW, BUILDINGS_RAW),
        fetch=fetch_arcgis_outputs({
            ADDRESSES_RAW.id: f"{BASE_UNITS_SERVICE}/0",
            STREETS_RAW.id: f"{BASE_UNITS_SERVICE}/1",
            BUILDINGS_RAW.id: f"{BASE_UNITS_SERVICE}/2",
        }),
        acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK,
        description="Immutable snapshots of the Detroit Base Units layers.",
    )


def canonical_asset(
    asset_id: str, directory: str, primary_key: str, geometry_types: tuple[str, ...]
) -> DataAsset:
    return DataAsset(
        asset_id,
        Path("data/derived") / directory,
        geo_contract(asset_id, primary_key, geometry_types),
    )


PARCELS = canonical_asset(
    "detroit.parcels", "detroit-parcels", "parcel_id", ("Polygon", "MultiPolygon")
)
ADDRESSES = canonical_asset(
    "detroit.base-units.addresses", "detroit-base-units-addresses", "address_id", ("Point",)
)
STREETS = canonical_asset(
    "detroit.base-units.streets", "detroit-base-units-streets", "street_id",
    ("LineString", "MultiLineString"),
)
BUILDINGS = canonical_asset(
    "detroit.base-units.buildings", "detroit-base-units-buildings", "building_id",
    ("Polygon", "MultiPolygon"),
)


def canonical_pipeline(
    name: str,
    raw: DataAsset,
    output: DataAsset,
    primary_key: str,
    geometry_types: tuple[str, ...],
) -> DataPipeline:
    return DataPipeline(
        name,
        (raw.id,),
        (output,),
        build=canonical_geojson_builder(
            input_asset=raw.id,
            input_artifact="raw.geojson",
            output_asset=output.id,
            primary_key=primary_key,
            geometry_types=geometry_types,
        ),
        description=f"Canonical GeoParquet for {output.id}.",
    )


@data_pipeline("canonical-detroit-parcels")
def canonical_detroit_parcels() -> DataPipeline:
    return canonical_pipeline(
        "canonical-detroit-parcels", PARCELS_RAW, PARCELS,
        "parcel_id", ("Polygon", "MultiPolygon"),
    )


@data_pipeline("canonical-detroit-base-units-addresses")
def canonical_detroit_addresses() -> DataPipeline:
    return canonical_pipeline(
        "canonical-detroit-base-units-addresses", ADDRESSES_RAW, ADDRESSES,
        "address_id", ("Point",),
    )


@data_pipeline("canonical-detroit-base-units-streets")
def canonical_detroit_streets() -> DataPipeline:
    return canonical_pipeline(
        "canonical-detroit-base-units-streets", STREETS_RAW, STREETS,
        "street_id", ("LineString", "MultiLineString"),
    )


@data_pipeline("canonical-detroit-base-units-buildings")
def canonical_detroit_buildings() -> DataPipeline:
    return canonical_pipeline(
        "canonical-detroit-base-units-buildings", BUILDINGS_RAW, BUILDINGS,
        "building_id", ("Polygon", "MultiPolygon"),
    )


QUERY_CATALOG = DataAsset(
    "detroit.query.catalog",
    Path("data/derived/detroit-query-catalog"),
    DatasetContract(
        "detroit.query.catalog", "1.0.0",
        custom_validator=validate_query_catalog_snapshot,
    ),
)


def build_detroit_query_catalog(context):
    metadata = build_query_catalog(
        context,
        output_asset=QUERY_CATALOG.id,
        tables={
            PARCELS.id: "parcels",
            ADDRESSES.id: "base_units_addresses",
            STREETS.id: "base_units_streets",
            BUILDINGS.id: "base_units_buildings",
        },
    )
    return {QUERY_CATALOG.id: metadata}


@data_pipeline("detroit-query-catalog")
def detroit_query_catalog() -> DataPipeline:
    return DataPipeline(
        "detroit-query-catalog",
        (PARCELS.id, ADDRESSES.id, STREETS.id, BUILDINGS.id),
        (QUERY_CATALOG,),
        build=build_detroit_query_catalog,
        description=(
            "Portable, read-only DuckDB mirror of promoted Detroit spatial tables."
        ),
    )


ANCHORS = DataAsset(
    "detroit.routing.anchors",
    Path("data/derived/detroit-routing-anchors"),
    DatasetContract(
        "detroit.routing.anchors", "1.0.0",
        required_columns={
            "anchor_id": "string", "parcel_id": "string", "parcel_key": "string",
            "street_key": "string", "method": "string", "review_status": "string",
            "street_distance_ft": "double", "parcel_boundary_distance_ft": "double",
        },
        allowed_values={
            "method": ("linked_address", "nearest_street_fallback"),
            "review_status": ("not_required", "required", "approved", "rejected"),
        },
        primary_key=("anchor_id",), geometry_types=("Point",), crs="EPSG:4326",
        accepted_artifact="accepted.parquet", rejects_artifact="blocked.parquet",
    ),
)
FRONTAGES = DataAsset(
    "detroit.routing.frontages",
    Path("data/derived/detroit-routing-frontages"),
    DatasetContract(
        "detroit.routing.frontages", "1.0.0",
        required_columns={
            "anchor_id": "string", "frontage_length_ft": "double",
            "street_distance_ft": "double", "angle_difference": "double",
        },
        primary_key=("anchor_id",), geometry_types=("LineString",), crs="EPSG:4326",
        accepted_artifact="accepted.parquet",
    ),
)
EVIDENCE = DataAsset(
    "detroit.routing.anchor-evidence",
    Path("data/derived/detroit-routing-anchor-evidence"),
    DatasetContract(
        "detroit.routing.anchor-evidence", "1.0.0",
        required_columns={
            "evidence_id": "string", "anchor_id": "string", "address_id": "string",
        },
        primary_key=("evidence_id",), accepted_artifact="accepted.parquet",
    ),
)
DISPOSITIONS = DataAsset(
    "detroit.routing.review-dispositions",
    Path("data/derived/detroit-routing-review-dispositions"),
    DatasetContract(
        "detroit.routing.review-dispositions", "1.0.0",
        required_columns={"anchor_id": "string", "review_status": "string"},
        allowed_values={
            "review_status": ("not_required", "required", "approved", "rejected")
        },
        primary_key=("anchor_id",), accepted_artifact="accepted.parquet",
    ),
)


def build_routing_contract(context):
    tables = build_routing_anchor_tables(
        gpd.read_parquet(context.inputs[PARCELS.id] / "accepted.parquet"),
        gpd.read_parquet(context.inputs[ADDRESSES.id] / "accepted.parquet"),
        gpd.read_parquet(context.inputs[STREETS.id] / "accepted.parquet"),
        gpd.read_parquet(context.inputs[BUILDINGS.id] / "accepted.parquet"),
    )
    tables["anchors"].to_parquet(
        context.staging[ANCHORS.id] / "accepted.parquet", index=False
    )
    tables["blocked"].to_parquet(
        context.staging[ANCHORS.id] / "blocked.parquet", index=False
    )
    tables["frontages"].to_parquet(
        context.staging[FRONTAGES.id] / "accepted.parquet", index=False
    )
    tables["evidence"].to_parquet(
        context.staging[EVIDENCE.id] / "accepted.parquet", index=False
    )
    tables["dispositions"].to_parquet(
        context.staging[DISPOSITIONS.id] / "accepted.parquet", index=False
    )
    anchor_counts = {
        "parcels_input": len(tables["anchors"].parcel_key.unique()) + len(tables["blocked"]),
        "anchors": len(tables["anchors"]),
        "multi_anchor_parcels": int(
            (tables["anchors"].groupby("parcel_key").size() > 1).sum()
        ),
        "fallbacks": int(tables["anchors"].method.eq("nearest_street_fallback").sum()),
        "default_ready": int(tables["anchors"].review_status.eq("not_required").sum()),
        "review_required": int(tables["anchors"].review_status.eq("required").sum()),
        "blocked_parcels": len(tables["blocked"]),
    }
    return {
        ANCHORS.id: BuildMetadata(counts=anchor_counts, parameters={"identity": "routing-anchor-v1"}),
        FRONTAGES.id: BuildMetadata(counts={"records": len(tables["frontages"])}),
        EVIDENCE.id: BuildMetadata(counts={"records": len(tables["evidence"])}),
        DISPOSITIONS.id: BuildMetadata(counts={"records": len(tables["dispositions"])}),
    }


@data_pipeline("detroit-routing-anchors")
def detroit_routing_anchors() -> DataPipeline:
    return DataPipeline(
        "detroit-routing-anchors",
        (PARCELS.id, ADDRESSES.id, STREETS.id, BUILDINGS.id),
        (ANCHORS, FRONTAGES, EVIDENCE, DISPOSITIONS),
        build=build_routing_contract,
        description="Stable parcel routing anchors, evidence, frontages, and review status.",
    )


TRAVELTIME_REQUESTS = DataAsset(
    "detroit.traveltime.requests",
    Path("data/provider/traveltime-requests"),
    DatasetContract(
        "detroit.traveltime.requests", "1.0.0",
        required_columns={
            "request_id": "string", "provider_search_id": "string",
            "anchor_id": "string", "direction": "string", "mode": "string",
            "horizon_seconds": "int64", "required_override": "bool",
        },
        allowed_values={
            "direction": ("arrival", "departure"),
            "mode": ("walking", "cycling", "driving", "public_transport"),
        },
        primary_key=("request_id",), geometry_types=("Point",), crs="EPSG:4326",
        accepted_artifact="accepted.parquet", rejects_artifact="blocked.parquet",
    ),
)
TRAVELTIME_RESULTS = DataAsset(
    "detroit.traveltime.results",
    Path("data/provider/traveltime-results"),
    DatasetContract(
        "detroit.traveltime.results", "1.0.0",
        required_columns={
            "request_id": "string", "provider_search_id": "string", "anchor_id": "string",
        },
        primary_key=("request_id",),
        geometry_types=("Polygon", "MultiPolygon"), crs="EPSG:4326",
        accepted_artifact="accepted.parquet", rejects_artifact="errors.parquet",
    ),
    ArchiveTier.CRITICAL,
)


def build_traveltime_smoke_requests(context):
    anchors = gpd.read_parquet(context.inputs[ANCHORS.id] / "accepted.parquet")
    eligible = anchors[anchors.review_status.isin({"not_required", "approved"})]
    if eligible.empty:
        raise ValueError("no default-ready anchor is available for the smoke request")
    selected = eligible.sort_values("anchor_id", kind="stable").head(1)
    requests, blocked = build_request_ledger(
        selected,
        directions=("arrival", "departure"),
        mode="walking",
        horizon_seconds=3600,
        reference_time=datetime(2026, 8, 26, 12, tzinfo=ZoneInfo("America/Detroit")),
    )
    requests.to_parquet(
        context.staging[TRAVELTIME_REQUESTS.id] / "accepted.parquet", index=False
    )
    blocked.to_parquet(
        context.staging[TRAVELTIME_REQUESTS.id] / "blocked.parquet", index=False
    )
    return {
        TRAVELTIME_REQUESTS.id: BuildMetadata(
            counts={"requests": len(requests), "blocked": len(blocked)},
            parameters={
                "scope": "opt-in-smoke",
                "maximum_anchors": 1,
                "directions": ["arrival", "departure"],
                "mode": "walking",
                "horizon_seconds": 3600,
                "required_override": False,
            },
        )
    }


@data_pipeline("traveltime-smoke-requests")
def traveltime_smoke_requests() -> DataPipeline:
    return DataPipeline(
        "traveltime-smoke-requests", (ANCHORS.id,), (TRAVELTIME_REQUESTS,),
        build=build_traveltime_smoke_requests,
        description="Two opt-in TravelTime requests for one default-ready anchor.",
    )


def fetch_traveltime_smoke(context):
    app_id = os.environ.get("TRAVELTIME_APP_ID")
    api_key = os.environ.get("TRAVELTIME_API_KEY")
    if not app_id or not api_key:
        raise ValueError("TRAVELTIME_APP_ID and TRAVELTIME_API_KEY are required")
    requests = gpd.read_parquet(
        context.inputs[TRAVELTIME_REQUESTS.id] / "accepted.parquet"
    )
    run = execute_request_ledger(
        requests,
        context.staging[TRAVELTIME_RESULTS.id] / "raw",
        app_id=app_id,
        api_key=api_key,
    )
    run.results.to_parquet(
        context.staging[TRAVELTIME_RESULTS.id] / "accepted.parquet", index=False
    )
    run.errors.to_parquet(
        context.staging[TRAVELTIME_RESULTS.id] / "errors.parquet", index=False
    )
    return {
        TRAVELTIME_RESULTS.id: BuildMetadata(
            counts={
                "requests": len(requests),
                "responses": len(run.results),
                "errors": len(run.errors),
                "retries": run.retries,
            },
            source={"provider": "TravelTime", "endpoint": "v4/time-map"},
            transaction_quality="provider_reconciled",
        )
    }


@data_pipeline("traveltime-smoke-results")
def traveltime_smoke_results() -> DataPipeline:
    return DataPipeline(
        "traveltime-smoke-results", (TRAVELTIME_REQUESTS.id,), (TRAVELTIME_RESULTS,),
        fetch=fetch_traveltime_smoke,
        acquisition_policy=AcquisitionPolicy.PAID,
        description="Opt-in, exactly reconciled TravelTime smoke-test results.",
    )


OSM_POIS_RAW = DataAsset(
    "detroit.osm.pois.raw",
    Path("data/sources/detroit-osm-pois"),
    DatasetContract(
        "detroit.osm.pois.raw", "1.0.0",
        required_columns={
            "source_id": "string", "osm_type": "string", "osm_id": "string",
            "tag_keys": "list<element: string>", "tag_values": "list<element: string>",
        },
        primary_key=("source_id",),
        geometry_types=(
            "Point", "MultiPoint", "LineString", "MultiLineString",
            "Polygon", "MultiPolygon",
        ),
        crs="EPSG:4326", accepted_artifact="raw.parquet",
        rejects_artifact="rejects.parquet",
    ),
    ArchiveTier.SOURCE,
)
OSM_POIS = DataAsset(
    "detroit.osm.pois",
    Path("data/derived/detroit-osm-pois"),
    DatasetContract(
        "detroit.osm.pois", "1.0.0",
        required_columns={
            "source_id": "string", "osm_type": "string", "osm_id": "string",
            "tag_keys": "list<element: string>", "tag_values": "list<element: string>",
            "primary_category": "string", "routing_point_method": "string",
        },
        primary_key=("source_id",), geometry_types=("Point",), crs="EPSG:4326",
        accepted_artifact="accepted.parquet", rejects_artifact="rejects.parquet",
    ),
)


def fetch_osm_pois(context):
    source = collect_osm_pois(
        context.staging[OSM_POIS_RAW.id] / "raw.parquet",
        cache_root=context.root / "data" / ".cache" / "osmnx",
    )
    counts = {key: source.pop(key) for key in ("input", "accepted", "rejected")}
    return {
        OSM_POIS_RAW.id: BuildMetadata(
            counts=counts,
            source=source,
            transaction_quality="best_effort",
        )
    }


@data_pipeline("detroit-osm-pois-source")
def detroit_osm_pois_source() -> DataPipeline:
    return DataPipeline(
        "detroit-osm-pois-source", (), (OSM_POIS_RAW,),
        fetch=fetch_osm_pois,
        acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK,
        description="Source-faithful Detroit OSM POI geometries and selected tags.",
    )


def build_osm_pois(context):
    source = gpd.read_parquet(context.inputs[OSM_POIS_RAW.id] / "raw.parquet")
    candidates, rejected = normalize_osm_features(source, return_rejected=True)
    candidates.to_parquet(
        context.staging[OSM_POIS.id] / "accepted.parquet", index=False
    )
    rejected.to_parquet(
        context.staging[OSM_POIS.id] / "rejects.parquet", index=False
    )
    return {
        OSM_POIS.id: BuildMetadata(
            counts={"input": len(source), "accepted": len(candidates), "rejected": len(source) - len(candidates)},
            parameters={"routing_interpretation": "osm-poi-v1"},
        )
    }


@data_pipeline("canonical-detroit-osm-pois")
def canonical_detroit_osm_pois() -> DataPipeline:
    return DataPipeline(
        "canonical-detroit-osm-pois", (OSM_POIS_RAW.id,), (OSM_POIS,),
        build=build_osm_pois,
        description="Routing candidates derived from preserved OSM source geometry.",
    )


def legacy_source_asset(
    asset_id: str,
    directory: str,
    legacy: dict[str, str],
    *,
    tier: ArchiveTier,
    counts: dict[str, int],
) -> DataAsset:
    return DataAsset(
        asset_id,
        Path("data/sources") / directory,
        raw_contract(asset_id),
        tier,
        legacy_artifacts={name: Path(path) for name, path in legacy.items()},
        legacy_counts=counts,
    )


MUNICODE_RAW = legacy_source_asset(
    "detroit.municode.chapter-50.raw", "detroit-municode-chapter-50",
    {"raw": "resources/municode/2025-10-09_job-429936"},
    tier=ArchiveTier.CRITICAL, counts={"files": 153},
)
BZA_MINUTES_RAW = legacy_source_asset(
    "detroit.bza.minutes.raw", "detroit-bza-minutes",
    {"raw": "pipelines/zoning/bza_minutes"},
    tier=ArchiveTier.CRITICAL, counts={"files": 261},
)
BZA_GEMINI_RAW = legacy_source_asset(
    "detroit.bza.gemini.raw", "detroit-bza-gemini",
    {"raw": "pipelines/zoning/bza_dataset_gemini"},
    tier=ArchiveTier.CRITICAL, counts={"files": 798},
)
ASSESSMENT_REPORTS_RAW = legacy_source_asset(
    "michigan.assessment-history.reports.raw", "michigan-assessment-history-reports",
    {"raw": "pipelines/assessment-history/data/pdf"},
    tier=ArchiveTier.SOURCE, counts={"files": 58},
)
PARCEL_ATTRIBUTES_RAW = legacy_source_asset(
    "detroit.parcels.attributes.raw", "detroit-parcel-attributes",
    {"raw.csv": "pipelines/parcel-data/parcel-data.csv"},
    tier=ArchiveTier.SOURCE, counts={"records": 378_366},
)
LIHTC_QCT_RAW = legacy_source_asset(
    "hud.lihtc.qct-2026-wayne.raw", "hud-lihtc-qct-2026-wayne",
    {"raw.geojson": "data/lihtc/qct_2026_wayne.geojson"},
    tier=ArchiveTier.SOURCE, counts={"files": 1},
)
DETROIT_BASEMAP_RAW = legacy_source_asset(
    "detroit.osm.basemap.raw", "detroit-osm-basemap",
    {
        "detroit_boundary.geojson": "pipelines/housingDataAnalysis/street_simplification/output/detroit_boundary.geojson",
        "detroit_water.geojson": "pipelines/housingDataAnalysis/street_simplification/output/detroit_water.geojson",
    },
    tier=ArchiveTier.SOURCE, counts={"files": 2},
)
SPIRIT_TRAVELTIME_RAW = legacy_source_asset(
    "detroit.spirit-plaza.traveltime.raw", "detroit-spirit-plaza-traveltime",
    {"raw": "projects/detroit-land-use-forum/spirit-plaza-accessibility/output/raw"},
    tier=ArchiveTier.CRITICAL, counts={"files": 180},
)


def source_pipeline(
    name: str,
    outputs: tuple[DataAsset, ...],
    policy: AcquisitionPolicy,
    description: str,
) -> DataPipeline:
    return DataPipeline(
        name, (), outputs, acquisition_policy=policy, description=description
    )


@data_pipeline("detroit-municode-source")
def detroit_municode_source() -> DataPipeline:
    return source_pipeline(
        "detroit-municode-source", (MUNICODE_RAW,), AcquisitionPolicy.PUBLIC_NETWORK,
        "Immutable Detroit Chapter 50 Municode snapshot.",
    )


@data_pipeline("detroit-bza-minutes-source")
def detroit_bza_minutes_source() -> DataPipeline:
    return source_pipeline(
        "detroit-bza-minutes-source", (BZA_MINUTES_RAW,), AcquisitionPolicy.PUBLIC_NETWORK,
        "Scraped Detroit BZA minutes PDFs.",
    )


@data_pipeline("detroit-bza-gemini-source")
def detroit_bza_gemini_source() -> DataPipeline:
    return source_pipeline(
        "detroit-bza-gemini-source", (BZA_GEMINI_RAW,), AcquisitionPolicy.PAID,
        "Raw and consolidated Gemini extraction evidence.",
    )


@data_pipeline("michigan-assessment-history-source")
def michigan_assessment_history_source() -> DataPipeline:
    return source_pipeline(
        "michigan-assessment-history-source", (ASSESSMENT_REPORTS_RAW,),
        AcquisitionPolicy.PUBLIC_NETWORK, "Michigan Treasury levy-report snapshots.",
    )


@data_pipeline("detroit-parcel-attributes-source")
def detroit_parcel_attributes_source() -> DataPipeline:
    return source_pipeline(
        "detroit-parcel-attributes-source", (PARCEL_ATTRIBUTES_RAW,),
        AcquisitionPolicy.PUBLIC_NETWORK, "Detroit parcel attribute snapshot.",
    )


@data_pipeline("hud-lihtc-qct-source")
def hud_lihtc_qct_source() -> DataPipeline:
    return source_pipeline(
        "hud-lihtc-qct-source", (LIHTC_QCT_RAW,), AcquisitionPolicy.PUBLIC_NETWORK,
        "HUD 2026 QCT designation snapshot for Wayne County.",
    )


@data_pipeline("detroit-osm-basemap-source")
def detroit_osm_basemap_source() -> DataPipeline:
    return source_pipeline(
        "detroit-osm-basemap-source", (DETROIT_BASEMAP_RAW,),
        AcquisitionPolicy.PUBLIC_NETWORK, "Detroit boundary and water snapshot.",
    )


@data_pipeline("spirit-plaza-traveltime-legacy-source")
def spirit_plaza_traveltime_legacy_source() -> DataPipeline:
    return source_pipeline(
        "spirit-plaza-traveltime-legacy-source", (SPIRIT_TRAVELTIME_RAW,),
        AcquisitionPolicy.PAID, "Legacy immutable TravelTime response evidence.",
    )
