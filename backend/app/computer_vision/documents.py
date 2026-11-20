import base64
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath

import cv2
import numpy as np
from fastapi import UploadFile

from app.core.exceptions import ValidationError
from app.models.enums import SourceFormat

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
IMAGE_MIME = {"image/jpeg", "image/png", "image/jpg"}
PDF_MIME = {"application/pdf"}

_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"
_PDF = b"%PDF"


@dataclass
class LoadedDocument:
    pages: list[np.ndarray]
    source_format: SourceFormat
    total_pages: int


def safe_extension(filename: str | None) -> str:
    """Only the extension is ever used; the original name never touches the filesystem."""
    if not filename:
        return ""
    name = PureWindowsPath(PurePosixPath(filename).name).name
    dot = name.rfind(".")
    return name[dot:].lower() if dot != -1 else ""


async def read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await upload.read(512 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise ValidationError(
                f"File is larger than {max_bytes // (1024 * 1024)} MB",
                code="file_too_large",
                status_code=413,
            )
        chunks.append(chunk)
    if size == 0:
        raise ValidationError("The uploaded file is empty", code="empty_file")
    return b"".join(chunks)


def sniff_format(data: bytes, filename: str | None, content_type: str | None) -> SourceFormat:
    ext = safe_extension(filename)
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("Only JPG, PNG and PDF files are supported", code="unsupported_file_type")
    head = data[:16]
    if head.startswith(_PDF):
        detected = SourceFormat.PDF
    elif head.startswith(_JPEG) or head.startswith(_PNG):
        detected = SourceFormat.IMAGE
    else:
        raise ValidationError(
            "The file does not look like a valid JPG, PNG or PDF", code="unsupported_file_type"
        )
    if ext == ".pdf" and detected != SourceFormat.PDF:
        raise ValidationError("File extension does not match its contents", code="file_mismatch")
    if ext in {".jpg", ".jpeg", ".png"} and detected != SourceFormat.IMAGE:
        raise ValidationError("File extension does not match its contents", code="file_mismatch")
    return detected


def _decode_image(data: bytes) -> np.ndarray:
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ValidationError("The image could not be decoded", code="invalid_image")
    if image.shape[0] < 80 or image.shape[1] < 80:
        raise ValidationError("The image is too small to read", code="image_too_small")
    return image


def _render_pdf(data: bytes, max_pages: int) -> tuple[list[np.ndarray], int]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)
    except Exception as exc:  # noqa: BLE001
        raise ValidationError("The PDF could not be opened", code="invalid_pdf") from exc
    total = len(pdf)
    if total == 0:
        raise ValidationError("The PDF has no pages", code="invalid_pdf")
    pages: list[np.ndarray] = []
    for index in range(min(total, max_pages)):
        page = pdf[index]
        bitmap = page.render(scale=2.2)
        array = bitmap.to_numpy()
        if array.ndim == 3 and array.shape[2] == 4:
            array = cv2.cvtColor(array, cv2.COLOR_BGRA2BGR)
        elif array.ndim == 2:
            array = cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
        pages.append(np.ascontiguousarray(array))
        page.close()
    pdf.close()
    return pages, total


def load_document(data: bytes, fmt: SourceFormat, max_pages: int) -> LoadedDocument:
    if fmt == SourceFormat.PDF:
        pages, total = _render_pdf(data, max_pages)
        return LoadedDocument(pages=pages, source_format=fmt, total_pages=total)
    return LoadedDocument(pages=[_decode_image(data)], source_format=fmt, total_pages=1)


def encode_preview(image: np.ndarray, max_side: int = 1000, quality: int = 72) -> str:
    h, w = image.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")
