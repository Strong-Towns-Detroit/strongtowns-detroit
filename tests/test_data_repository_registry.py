from pathlib import Path

from strongtowns_detroit.data.engine import DataBuildSystem
from strongtowns_detroit.data.model import AcquisitionPolicy


ROOT = Path(__file__).resolve().parents[1]


def test_repository_catalog_is_a_local_derived_pipeline_with_explicit_inputs():
    system = DataBuildSystem.find(ROOT)
    pipeline = next(
        item for item in system.pipelines or () if item.name == "detroit-query-catalog"
    )
    assert pipeline.acquisition_policy is AcquisitionPolicy.LOCAL
    assert pipeline.inputs == (
        "detroit.parcels",
        "detroit.base-units.addresses",
        "detroit.base-units.streets",
        "detroit.base-units.buildings",
    )
    assert [asset.id for asset in pipeline.outputs] == ["detroit.query.catalog"]


def test_repository_registry_has_one_producer_for_every_asset():
    system = DataBuildSystem.find(ROOT)
    output_count = sum(len(pipeline.outputs) for pipeline in system.pipelines or ())
    assert len(system.assets) == output_count
    assert len(system.producers) == output_count


def test_repository_paid_pipelines_remain_explicit_acquisition_only():
    system = DataBuildSystem.find(ROOT)
    paid = [
        pipeline for pipeline in system.pipelines or ()
        if pipeline.acquisition_policy is AcquisitionPolicy.PAID
    ]
    assert {pipeline.name for pipeline in paid} == {
        "detroit-bza-gemini-source",
        "spirit-plaza-traveltime-legacy-source",
        "traveltime-smoke-results",
    }
    assert all(pipeline.build is None for pipeline in paid)
