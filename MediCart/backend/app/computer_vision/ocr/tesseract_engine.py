import shutil
from importlib.util import find_spec
from pathlib import Path

import numpy as np

from app.computer_vision.ocr.base import OCREngine, OCRResult, group_into_lines

WINDOWS_DEFAULTS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


class TesseractEngine(OCREngine):
    name = "tesseract"

    def __init__(self, command: str | None = None):
        self.command = command

    def _binary(self) -> str | None:
        if self.command and Path(self.command).exists():
            return self.command
        found = shutil.which("tesseract")
        if found:
            return found
        for candidate in WINDOWS_DEFAULTS:
            if Path(candidate).exists():
                return candidate
        return None

    def is_available(self) -> bool:
        return find_spec("pytesseract") is not None and self._binary() is not None

    def recognise(self, image: np.ndarray) -> OCRResult:
        import pytesseract

        binary = self._binary()
        if binary:
            pytesseract.pytesseract.tesseract_cmd = binary
        data = pytesseract.image_to_data(image, config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT)
        items = []
        for i, word in enumerate(data["text"]):
            if not word or not word.strip():
                continue
            conf = float(data["conf"][i])
            left, top = float(data["left"][i]), float(data["top"][i])
            width, height = float(data["width"][i]), float(data["height"][i])
            box = [[left, top], [left + width, top], [left + width, top + height], [left, top + height]]
            items.append((box, word.strip(), conf / 100.0 if conf >= 0 else None))
        return OCRResult(engine=self.name, lines=group_into_lines(items))
