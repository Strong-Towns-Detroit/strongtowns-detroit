import json

import geopandas as gpd
import pytest
from shapely.geometry import box

from render_map import render


def test_render_rejects_stale_thresholds(tmp_path):
    data_path = tmp_path / "data.geojson"
    spec_path = tmp_path / "spec.json"
    output_path = tmp_path / "map.html"
    gpd.GeoDataFrame(
        [
            {
                "mode": "walking",
                "minutes": 15,
                "provider": "test",
                "geometry": box(-83.1, 42.3, -83.0, 42.4),
            }
        ],
        crs="EPSG:4326",
    ).to_file(data_path, driver="GeoJSON")
    spec_path.write_text(
        json.dumps({"modes": ["walking"], "threshold_minutes": [5, 10, 15]})
    )

    with pytest.raises(SystemExit, match=r"expected \[5, 10, 15\], found \[15\]"):
        render(data_path, spec_path, output_path)
