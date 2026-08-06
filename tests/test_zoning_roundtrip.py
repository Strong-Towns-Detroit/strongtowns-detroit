import copy
from pathlib import Path

import pytest

from strongtowns_detroit.zoning.roundtrip import (
    RoundtripError,
    decode_archive,
    restore_document,
    verify_document,
)
from strongtowns_detroit.zoning.source_model import compile_source_document

ROOT = Path(__file__).resolve().parents[1]


def test_docx_json_docx_is_byte_exact_and_semantically_stable(tmp_path):
    source = sorted((ROOT / "resources").glob("*.docx"))[0]
    document = compile_source_document(source, include_archive=True)
    restored = restore_document(document, tmp_path)

    assert restored.read_bytes() == source.read_bytes()
    verify_document(document, restored)


def test_tampered_archive_is_rejected():
    source = sorted((ROOT / "resources").glob("*.docx"))[0]
    document = compile_source_document(source, include_archive=True)
    tampered = copy.deepcopy(document)
    tampered["archive"]["data"] = tampered["archive"]["data"][:-4] + "AAAA"

    with pytest.raises(RoundtripError, match="checksum mismatch|invalid base64"):
        decode_archive(tampered)
