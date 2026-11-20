from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class OCRLine:
    text: str
    confidence: float | None = None
    box: list[list[float]] | None = None


@dataclass
class OCRResult:
    engine: str
    lines: list[OCRLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text.strip() for line in self.lines if line.text.strip())

    @property
    def mean_confidence(self) -> float | None:
        values = [line.confidence for line in self.lines if line.confidence is not None]
        return float(sum(values) / len(values)) if values else None

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class OCREngine(ABC):
    name: str = "base"
    supports_handwriting: bool = False

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def recognise(self, image: np.ndarray) -> OCRResult: ...


def group_into_lines(items: list[tuple[list[list[float]], str, float | None]]) -> list[OCRLine]:
    """Merge word/segment boxes that sit on the same visual line, left to right."""
    if not items:
        return []
    entries = []
    for box, text, conf in items:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        entries.append(
            {"top": min(ys), "bottom": max(ys), "left": min(xs), "text": text, "conf": conf, "box": box}
        )
    entries.sort(key=lambda e: (e["top"], e["left"]))

    lines: list[list[dict]] = []
    for entry in entries:
        height = max(entry["bottom"] - entry["top"], 1.0)
        centre = (entry["top"] + entry["bottom"]) / 2
        placed = False
        for line in lines:
            line_top = min(e["top"] for e in line)
            line_bottom = max(e["bottom"] for e in line)
            line_height = max(line_bottom - line_top, 1.0)
            overlap = min(entry["bottom"], line_bottom) - max(entry["top"], line_top)
            if (
                overlap > 0.5 * min(height, line_height)
                or abs(centre - (line_top + line_bottom) / 2) < 0.35 * line_height
            ):
                line.append(entry)
                placed = True
                break
        if not placed:
            lines.append([entry])

    result: list[OCRLine] = []
    for line in lines:
        line.sort(key=lambda e: e["left"])
        confs = [e["conf"] for e in line if e["conf"] is not None]
        xs = [p[0] for e in line for p in e["box"]]
        ys = [p[1] for e in line for p in e["box"]]
        result.append(
            OCRLine(
                text=" ".join(e["text"] for e in line).strip(),
                confidence=float(sum(confs) / len(confs)) if confs else None,
                box=[[min(xs), min(ys)], [max(xs), min(ys)], [max(xs), max(ys)], [min(xs), max(ys)]],
            )
        )
    result.sort(key=lambda line: line.box[0][1] if line.box else 0)
    return result
