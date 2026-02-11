"""Tests for strongtowns_detroit.geo.loader module."""

from unittest.mock import patch, MagicMock
import pytest
import geopandas as gpd
from shapely.geometry import box, Point

from strongtowns_detroit.geo.loader import load_geography, prepare_water, sync_crs


class TestSyncCrs:
    def test_single_gdf_reprojected(self):
        gdf = gpd.GeoDataFrame(
            {"geometry": [Point(0, 0)]}, crs="EPSG:4326"
        )
        result = sync_crs(gdf, target_crs="EPSG:3857")
        assert result.crs.to_epsg() == 3857

    def test_single_gdf_same_crs_unchanged(self):
        gdf = gpd.GeoDataFrame(
            {"geometry": [Point(0, 0)]}, crs="EPSG:4326"
        )
        result = sync_crs(gdf, target_crs="EPSG:4326")
        assert result.crs.to_epsg() == 4326

    def test_multiple_gdfs_reprojected(self):
        gdf1 = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:4326")
        gdf2 = gpd.GeoDataFrame({"geometry": [Point(1, 1)]}, crs="EPSG:3857")
        r1, r2 = sync_crs(gdf1, gdf2, target_crs="EPSG:4326")
        assert r1.crs.to_epsg() == 4326
        assert r2.crs.to_epsg() == 4326

    def test_default_target_is_first_crs(self):
        gdf1 = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:3857")
        gdf2 = gpd.GeoDataFrame({"geometry": [Point(1, 1)]}, crs="EPSG:4326")
        r1, r2 = sync_crs(gdf1, gdf2)
        assert r1.crs.to_epsg() == 3857
        assert r2.crs.to_epsg() == 3857

    def test_none_gdf_preserved(self):
        gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:4326")
        r1, r2 = sync_crs(gdf, None, target_crs="EPSG:4326")
        assert r2 is None


class TestPrepareWater:
    def _make_water(self, names=None):
        geom = [box(0, 0, 1, 1), box(0.5, 0.5, 1.5, 1.5)]
        data = {"geometry": geom}
        if names is not None:
            data["name"] = names
        return gpd.GeoDataFrame(data, crs="EPSG:4326")

    def _make_ref(self):
        return gpd.GeoDataFrame(
            {"geometry": [box(0, 0, 2, 2)]}, crs="EPSG:4326"
        )

    def test_filters_lake_st_clair(self):
        water = self._make_water(names=["Detroit River", "Lake St. Clair"])
        ref = self._make_ref()
        result = prepare_water(water, ref, filter_lake=True)
        assert len(result) == 1

    def test_no_filter_keeps_all(self):
        water = self._make_water(names=["Detroit River", "Lake St. Clair"])
        ref = self._make_ref()
        result = prepare_water(water, ref, filter_lake=False)
        assert len(result) == 2

    def test_none_water_returns_none(self):
        ref = self._make_ref()
        result = prepare_water(None, ref)
        assert result is None

    def test_empty_water_returns_empty(self):
        water = gpd.GeoDataFrame({"geometry": []}, crs="EPSG:4326")
        ref = self._make_ref()
        result = prepare_water(water, ref)
        assert len(result) == 0


class TestLoadGeography:
    def test_loads_boundary_and_water(self, tmp_path):
        # Create mock gpkg files
        boundary = gpd.GeoDataFrame({"geometry": [box(0, 0, 1, 1)]}, crs="EPSG:4326")
        water = gpd.GeoDataFrame({"geometry": [box(0, 0, 0.5, 0.5)]}, crs="EPSG:4326")
        boundary.to_file(tmp_path / "detroit_boundary.gpkg", driver="GPKG")
        water.to_file(tmp_path / "detroit_water.gpkg", driver="GPKG")

        b, w, e = load_geography(tmp_path)
        assert b is not None
        assert w is not None
        assert e is None  # load_streets=False by default

    def test_missing_files_return_none(self, tmp_path):
        b, w, e = load_geography(tmp_path)
        assert b is None
        assert w is None
        assert e is None
