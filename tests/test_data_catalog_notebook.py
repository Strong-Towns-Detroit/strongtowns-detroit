from pathlib import Path


NOTEBOOK = Path("notebooks/data_catalog.py")


def test_catalog_notebook_is_git_friendly_python():
    source = NOTEBOOK.read_text()
    compile(source, str(NOTEBOOK), "exec")
    assert "DataBuildSystem.find()" in source
    assert "catalog_query" in source


def test_catalog_notebook_does_not_embed_credentials_or_network_clients():
    source = NOTEBOOK.read_text().lower()
    prohibited = (
        "api_key", "access_key", "secret_key", "requests.", "httpx.",
        "boto3", "allow-paid", "archive push", "fetch(",
    )
    assert not [term for term in prohibited if term in source]
