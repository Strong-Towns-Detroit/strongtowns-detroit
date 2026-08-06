"""Exact recovery and semantic verification for ordinance source packages."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from strongtowns_detroit.zoning.source_model import compile_source_document


class RoundtripError(ValueError):
    """A lossless package failed integrity or semantic verification."""


def decode_archive(document: dict) -> bytes:
    archive = document.get("archive") or {}
    if archive.get("encoding") != "base64" or not archive.get("data"):
        raise RoundtripError(f"{document.get('document')}: missing base64 archive")
    try:
        payload = base64.b64decode(archive["data"], validate=True)
    except (ValueError, TypeError) as error:
        raise RoundtripError(f"{document.get('document')}: invalid base64 archive") from error
    digest = hashlib.sha256(payload).hexdigest()
    if digest != document.get("archiveSha256"):
        raise RoundtripError(
            f"{document.get('document')}: archive checksum mismatch "
            f"({digest} != {document.get('archiveSha256')})"
        )
    if len(payload) != document.get("archiveBytes"):
        raise RoundtripError(f"{document.get('document')}: archive byte count mismatch")
    return payload


def restore_document(document: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / document["document"]
    target.write_bytes(decode_archive(document))
    return target


def verify_document(document: dict, restored_path: Path) -> None:
    payload = restored_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != document["archiveSha256"]:
        raise RoundtripError(f"{document['document']}: restored bytes are not exact")
    extracted = compile_source_document(restored_path)
    if extracted["blocks"] != document["blocks"]:
        raise RoundtripError(f"{document['document']}: extracted block model changed")

