from __future__ import annotations

import codecs
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from .config import settings

_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
}
_CHUNK_SIZE = 1024 * 1024


class InvalidUploadError(ValueError):
    pass


@dataclass(frozen=True)
class StoredUpload:
    filename: str
    content_type: str
    size: int
    path: Path


def _safe_filename(filename: str | None) -> str:
    if not filename:
        raise InvalidUploadError("Uploaded file must have a filename.")
    return filename.replace("\\", "/").rsplit("/", 1)[-1]


def _validate_content(extension: str, prefix: bytes, decoder: codecs.IncrementalDecoder | None) -> None:
    if extension == ".pdf" and b"%PDF-" not in prefix[:1024]:
        raise InvalidUploadError("File content does not look like a PDF.")
    if extension in {".jpg", ".jpeg"} and not prefix.startswith(b"\xff\xd8\xff"):
        raise InvalidUploadError("File content does not look like a JPEG image.")
    if extension == ".png" and not prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        raise InvalidUploadError("File content does not look like a PNG image.")
    if extension in {".tif", ".tiff"} and not prefix.startswith((b"II*\x00", b"MM\x00*")):
        raise InvalidUploadError("File content does not look like a TIFF image.")
    if extension == ".xlsx" and not prefix.startswith(b"PK\x03\x04"):
        raise InvalidUploadError("File content does not look like an XLSX workbook.")
    if extension == ".xls" and not prefix.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise InvalidUploadError("File content does not look like an XLS workbook.")
    if extension == ".csv":
        if not prefix.strip():
            raise InvalidUploadError("CSV file is empty.")
        if decoder is not None:
            try:
                decoder.decode(b"", final=True)
            except UnicodeDecodeError as error:
                raise InvalidUploadError("CSV file is not valid UTF-8 text.") from error


async def store_upload(upload: UploadFile) -> StoredUpload:
    filename = _safe_filename(upload.filename)
    extension = Path(filename).suffix.lower()
    content_type = _MIME_TYPES.get(extension)
    if content_type is None:
        raise InvalidUploadError("Unsupported file type.")

    directory = Path(settings.data_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid.uuid4()}{extension}"
    destination = directory / storage_name
    temporary_path = directory / f".{storage_name}.tmp"
    prefix = bytearray()
    size = 0
    decoder = codecs.getincrementaldecoder("utf-8-sig")() if extension == ".csv" else None

    try:
        with temporary_path.open("wb") as target:
            while chunk := await upload.read(_CHUNK_SIZE):
                if len(prefix) < 1024:
                    prefix.extend(chunk[: 1024 - len(prefix)])
                if decoder is not None:
                    try:
                        decoder.decode(chunk)
                    except UnicodeDecodeError as error:
                        raise InvalidUploadError("CSV file is not valid UTF-8 text.") from error
                target.write(chunk)
                size += len(chunk)

        if size == 0:
            raise InvalidUploadError("Uploaded file is empty.")
        _validate_content(extension, bytes(prefix), decoder)
        temporary_path.replace(destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise

    return StoredUpload(
        filename=filename,
        content_type=content_type,
        size=size,
        path=destination,
    )


def remove_stored_upload(upload: StoredUpload) -> None:
    upload.path.unlink(missing_ok=True)
