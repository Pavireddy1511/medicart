import logging
import threading
from importlib.util import find_spec

import cv2
import numpy as np

from app.computer_vision.ocr.base import OCREngine, OCRLine, OCRResult

logger = logging.getLogger(__name__)


def segment_lines(binary: np.ndarray, min_height: int = 12) -> list[tuple[int, int]]:
    """Horizontal projection profile: returns (top, bottom) row ranges that contain ink."""
    ink = (binary < 128).astype(np.uint8)
    rows = ink.sum(axis=1)
    threshold = max(2, int(0.01 * binary.shape[1]))
    bands: list[tuple[int, int]] = []
    start = None
    for y, value in enumerate(rows):
        if value > threshold and start is None:
            start = y
        elif value <= threshold and start is not None:
            if y - start >= min_height:
                bands.append((start, y))
            start = None
    if start is not None and binary.shape[0] - start >= min_height:
        bands.append((start, binary.shape[0]))

    merged: list[tuple[int, int]] = []
    for top, bottom in bands:
        if merged and top - merged[-1][1] < min_height // 2:
            merged[-1] = (merged[-1][0], bottom)
        else:
            merged.append((top, bottom))
    return merged


class TrOCREngine(OCREngine):
    """Experimental handwritten text recognition with microsoft/trocr-*-handwritten.

    Needs the optional `handwriting` extra (torch + transformers, a large download) and
    ENABLE_HANDWRITING_OCR=true. TrOCR reads one text line at a time, so the page is first
    split into line crops (OCR detection boxes when available, projection profile otherwise).
    """

    name = "trocr"
    supports_handwriting = True
    _lock = threading.Lock()
    _loaded: tuple | None = None

    def __init__(self, model_name: str, enabled: bool):
        self.model_name = model_name
        self.enabled = enabled

    def is_available(self) -> bool:
        return self.enabled and find_spec("torch") is not None and find_spec("transformers") is not None

    def _load(self):
        if TrOCREngine._loaded is None:
            with TrOCREngine._lock:
                if TrOCREngine._loaded is None:
                    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

                    logger.info("Loading TrOCR model %s", self.model_name)
                    processor = TrOCRProcessor.from_pretrained(self.model_name)
                    model = VisionEncoderDecoderModel.from_pretrained(self.model_name)
                    model.eval()
                    TrOCREngine._loaded = (processor, model)
        return TrOCREngine._loaded

    def _read_crop(self, crop: np.ndarray) -> tuple[str, float | None]:
        import torch
        from PIL import Image

        processor, model = self._load()
        pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB) if crop.ndim == 2 else crop)
        pixel_values = processor(images=pil, return_tensors="pt").pixel_values
        with torch.no_grad():
            output = model.generate(
                pixel_values, max_new_tokens=64, output_scores=True, return_dict_in_generate=True
            )
        text = processor.batch_decode(output.sequences, skip_special_tokens=True)[0].strip()
        confidence = None
        try:
            scores = model.compute_transition_scores(output.sequences, output.scores, normalize_logits=True)
            confidence = float(torch.exp(scores.mean()).item())
        except Exception:  # noqa: BLE001 - confidence is best-effort
            pass
        return text, confidence

    def recognise(self, image: np.ndarray, boxes: list[list[list[float]]] | None = None) -> OCRResult:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        crops: list[tuple[np.ndarray, list[list[float]]]] = []
        if boxes:
            for box in boxes:
                xs = [int(p[0]) for p in box]
                ys = [int(p[1]) for p in box]
                x0, x1 = max(min(xs) - 4, 0), min(max(xs) + 4, gray.shape[1])
                y0, y1 = max(min(ys) - 4, 0), min(max(ys) + 4, gray.shape[0])
                if x1 - x0 > 8 and y1 - y0 > 8:
                    crops.append((gray[y0:y1, x0:x1], box))
        else:
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            for top, bottom in segment_lines(binary):
                y0, y1 = max(top - 4, 0), min(bottom + 4, gray.shape[0])
                box = [
                    [0.0, float(y0)],
                    [float(gray.shape[1]), float(y0)],
                    [float(gray.shape[1]), float(y1)],
                    [0.0, float(y1)],
                ]
                crops.append((gray[y0:y1, :], box))

        lines: list[OCRLine] = []
        for crop, box in crops[:60]:
            text, confidence = self._read_crop(crop)
            if text:
                lines.append(OCRLine(text=text, confidence=confidence, box=box))
        return OCRResult(engine=self.name, lines=lines)
