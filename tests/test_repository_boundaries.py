from pathlib import Path


def test_detroit_does_not_vendor_reusable_packages():
    package = Path(__file__).parents[1] / "src" / "strongtowns_detroit"

    assert not (package / "graphics").exists()
    assert not (package / "pipelines").exists()
    assert not (package / "models").exists()
    assert not (package / "zoning").exists()


def test_project_sources_use_public_package_names():
    root = Path(__file__).parents[1]
    source = "\n".join(
        source_path.read_text(errors="ignore")
        for base in (root / "src", root / "projects", root / "pipelines", root / "tests")
        for source_path in base.rglob("*.py")
    )

    prefix = "strongtowns_detroit"
    assert f"{prefix}.graphics" not in source
    assert f"{prefix}.pipelines" not in source
    assert f"{prefix}.models" not in source
