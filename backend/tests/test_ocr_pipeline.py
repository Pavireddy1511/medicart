import cv2
import numpy as np
import pytest

from app.computer_vision.documents import encode_preview, load_document, sniff_format
from app.computer_vision.ocr.rapidocr_engine import RapidOCREngine
from app.computer_vision.preprocessing import preprocess
from app.models.enums import SourceFormat


def _prescription_image(angle: float = 0.0) -> np.ndarray:
    image = np.full((700, 1100, 3), 255, dtype=np.uint8)
    lines = [
        "Dr. Demo Clinic",
        "Rx",
        "Tab Paracetamol 500mg 1-0-1 x 5 days",
        "Cap Amoxicillin 500 mg TDS 7 days",
    ]
    for i, text in enumerate(lines):
        cv2.putText(image, text, (60, 120 + i * 110), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (20, 20, 20), 3)
    if angle:
        h, w = image.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        image = cv2.warpAffine(image, matrix, (w, h), borderValue=(255, 255, 255))
    return image


def test_preprocess_steps_and_deskew():
    result = preprocess(_prescription_image(angle=4.0))
    assert result.enhanced.ndim == 2 and result.binary.ndim == 2
    assert "grayscale" in result.steps and "adaptive threshold" in result.steps
    assert abs(result.deskew_angle - (-4.0)) <= 1.0 or abs(result.deskew_angle - 4.0) <= 1.0
    assert 0.0 <= result.handwriting_score <= 1.0


def test_sniff_and_load_png_and_preview():
    ok, buffer = cv2.imencode(".png", _prescription_image())
    data = buffer.tobytes()
    fmt = sniff_format(data, "rx.PNG", "image/png")
    assert fmt == SourceFormat.IMAGE
    doc = load_document(data, fmt, max_pages=3)
    assert doc.total_pages == 1 and doc.pages[0].shape[2] == 3
    assert encode_preview(doc.pages[0]).startswith("data:image/jpeg;base64,")


def test_pdf_rendering():
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    for _ in range(4):
        pdf.new_page(595, 842)
    data = pdf.save_to_bytes() if hasattr(pdf, "save_to_bytes") else None
    if data is None:
        import io

        buffer = io.BytesIO()
        pdf.save(buffer)
        data = buffer.getvalue()
    fmt = sniff_format(data, "scan.pdf", "application/pdf")
    assert fmt == SourceFormat.PDF
    doc = load_document(data, fmt, max_pages=3)
    assert doc.total_pages == 4 and len(doc.pages) == 3
    assert doc.pages[0].shape[2] == 3


@pytest.mark.slow
def test_rapidocr_reads_printed_text():
    engine = RapidOCREngine()
    if not engine.is_available():
        pytest.skip("rapidocr not installed")
    result = engine.recognise(preprocess(_prescription_image()).enhanced)
    text = result.text.lower()
    assert "paracetamol" in text
    assert "amoxicillin" in text
    assert result.mean_confidence is not None and result.mean_confidence > 0.7
