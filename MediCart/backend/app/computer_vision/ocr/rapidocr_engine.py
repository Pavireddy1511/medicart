import logging
import threading
from importlib.util import find_spec

import numpy as np

from app.computer_vision.ocr.base import OCREngine, OCRResult, group_into_lines

logger = logging.getLogger(__name__)


class RapidOCREngine(OCREngine):
    """PaddleOCR detection + recognition models running on ONNX Runtime (CPU, pip-only)."""

    name = "rapidocr"
    _instance = None
    _lock = threading.Lock()

    def is_available(self) -> bool:
        return find_spec("rapidocr_onnxruntime") is not None

    def _engine(self):
        if RapidOCREngine._instance is None:
            with RapidOCREngine._lock:
                if RapidOCREngine._instance is None:
                    from rapidocr_onnxruntime import RapidOCR

                    logger.info("Loading RapidOCR models")
                    RapidOCREngine._instance = RapidOCR()
        return RapidOCREngine._instance

    def recognise(self, image: np.ndarray) -> OCRResult:
        if image.ndim == 2:
            import cv2

            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        raw, _elapsed = self._engine()(image)
        if not raw:
            return OCRResult(engine=self.name)
        items = [(box, text, float(score)) for box, text, score in raw if text and text.strip()]
        return OCRResult(engine=self.name, lines=group_into_lines(items))
