from functools import lru_cache

from app.computer_vision.ocr.base import OCREngine, OCRLine, OCRResult
from app.computer_vision.ocr.rapidocr_engine import RapidOCREngine
from app.computer_vision.ocr.tesseract_engine import TesseractEngine
from app.computer_vision.ocr.trocr_engine import TrOCREngine
from app.core.config import Settings

__all__ = [
    "OCREngine",
    "OCRLine",
    "OCRResult",
    "get_engine",
    "get_handwriting_engine",
    "engine_status",
]


@lru_cache
def _engines(ocr_engine: str, tesseract_cmd: str | None) -> dict[str, OCREngine]:
    return {
        "rapidocr": RapidOCREngine(),
        "tesseract": TesseractEngine(tesseract_cmd),
    }


def get_engine(settings: Settings) -> OCREngine | None:
    engines = _engines(settings.ocr_engine, settings.tesseract_cmd)
    if settings.ocr_engine == "none":
        return None
    if settings.ocr_engine in engines:
        engine = engines[settings.ocr_engine]
        return engine if engine.is_available() else None
    for name in ("rapidocr", "tesseract"):
        if engines[name].is_available():
            return engines[name]
    return None


@lru_cache
def _handwriting(model_name: str, enabled: bool) -> TrOCREngine:
    return TrOCREngine(model_name, enabled)


def get_handwriting_engine(settings: Settings) -> TrOCREngine | None:
    engine = _handwriting(settings.handwriting_model, settings.enable_handwriting_ocr)
    return engine if engine.is_available() else None


def engine_status(settings: Settings) -> dict:
    engines = _engines(settings.ocr_engine, settings.tesseract_cmd)
    selected = get_engine(settings)
    handwriting = _handwriting(settings.handwriting_model, settings.enable_handwriting_ocr)
    return {
        "configured": settings.ocr_engine,
        "selected": selected.name if selected else None,
        "available": {name: engine.is_available() for name, engine in engines.items()},
        "handwriting": {
            "enabled": settings.enable_handwriting_ocr,
            "available": handwriting.is_available(),
            "model": settings.handwriting_model,
        },
    }
