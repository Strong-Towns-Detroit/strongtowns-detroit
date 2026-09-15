"""Read-only, content-addressed inputs shared by public atlas builders."""
from strongtowns_data import DataBuildSystem, DataLock, DataRepository
from strongtowns_detroit.repositories import data_repository

REQUIREMENTS = {
    "histories": ("detroit.bza.gemini.raw", "raw/case_histories.csv"),
    "occurrences": ("detroit.bza.gemini.raw", "raw/case_occurrences.csv"),
    "applications": ("detroit.bza.gemini.raw", "raw/atlas_applications.csv"),
    "sites": ("detroit.bza.gemini.raw", "raw/map_sites.gpkg"),
    "roads": ("detroit.spirit-plaza.accessibility", "road_context.geojson"),
    "boundary": ("detroit.osm.basemap.raw", "detroit_boundary.geojson"),
}


def resolve_inputs(lock_path, repository_path=None, requirements=None):
    requirements = REQUIREMENTS if requirements is None else requirements
    lock = DataLock.load(lock_path)
    repository = DataRepository(DataBuildSystem.find(repository_path or data_repository()))
    snapshots = {}
    paths = {}
    metadata = {}
    for alias, (dataset_id, artifact) in requirements.items():
        try:
            reference = lock.asset(dataset_id)
            if dataset_id not in snapshots:
                snapshots[dataset_id] = repository.resolve(reference)
            directory, manifest = snapshots[dataset_id]
            declared = {item["path"] for item in manifest["artifacts"]}
            if artifact not in declared:
                raise ValueError(f"undeclared artifact: {artifact}")
            path = (directory / artifact).resolve()
            path.relative_to(directory.resolve())
            paths[alias] = path
            metadata[dataset_id] = {
                "snapshot_id": reference.snapshot_id,
                "manifest_sha256": reference.manifest_sha256,
                "created_at": manifest["created_at"],
            }
        except (KeyError, ValueError, FileNotFoundError) as error:
            raise ValueError(
                f"Atlas input {alias} ({dataset_id}/{artifact}) is unavailable: {error}. "
                "Inspect strongtowns data status in the data repository and restore the "
                "pinned snapshot. Prepare and review any replacement there before an "
                "explicit lock update; this builder never fetches or changes locks."
            ) from error
    return paths, metadata
