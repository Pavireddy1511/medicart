from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class PreprocessResult:
    original: np.ndarray
    enhanced: np.ndarray
    binary: np.ndarray
    deskew_angle: float
    handwriting_score: float
    steps: list[str] = field(default_factory=list)


def _resize(image: np.ndarray, min_side: int, max_side: int) -> tuple[np.ndarray, float]:
    h, w = image.shape[:2]
    scale = 1.0
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
    elif min(h, w) < min_side:
        scale = min(2.0, min_side / min(h, w))
    if abs(scale - 1.0) < 0.01:
        return image, 1.0
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=interpolation), scale


def _estimate_skew(binary: np.ndarray, max_angle: float = 10.0, step: float = 0.5) -> float:
    """Pick the rotation that makes text rows line up (maximises row-sum variance)."""
    h, w = binary.shape[:2]
    scale = 600 / max(h, w)
    small = cv2.resize(binary, (max(1, int(w * scale)), max(1, int(h * scale))))
    ink = (small < 128).astype(np.uint8)
    if ink.sum() < 50:
        return 0.0
    center = (ink.shape[1] / 2, ink.shape[0] / 2)
    best_angle, best_score = 0.0, -1.0
    for angle in np.arange(-max_angle, max_angle + step, step):
        matrix = cv2.getRotationMatrix2D(center, float(angle), 1.0)
        rotated = cv2.warpAffine(ink, matrix, (ink.shape[1], ink.shape[0]), flags=cv2.INTER_NEAREST)
        score = float(np.var(rotated.sum(axis=1)))
        if score > best_score:
            best_score, best_angle = score, float(angle)
    return best_angle


def _rotate(image: np.ndarray, angle: float, border: int) -> np.ndarray:
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(border, border, border) if image.ndim == 3 else border,
    )


def _handwriting_score(binary: np.ndarray) -> float:
    """Rough 0..1 estimate: handwriting has far more varied stroke heights than print."""
    ink = (binary < 128).astype(np.uint8)
    count, _labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    heights = stats[1:, cv2.CC_STAT_HEIGHT]
    widths = stats[1:, cv2.CC_STAT_WIDTH]
    keep = (heights > 6) & (heights < binary.shape[0] * 0.2) & (widths < binary.shape[1] * 0.5)
    heights = heights[keep].astype(np.float32)
    if len(heights) < 15:
        return 0.5
    cv = float(heights.std() / max(heights.mean(), 1e-6))
    return float(np.clip((cv - 0.35) / 0.65, 0.0, 1.0))


def preprocess(image: np.ndarray, *, min_side: int = 1400, max_side: int = 2600) -> PreprocessResult:
    steps: list[str] = []
    resized, scale = _resize(image, min_side, max_side)
    if scale != 1.0:
        steps.append(f"resize x{scale:.2f}")

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if resized.ndim == 3 else resized.copy()
    steps.append("grayscale")

    denoised = cv2.bilateralFilter(gray, d=7, sigmaColor=60, sigmaSpace=60)
    steps.append("bilateral denoise")

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(denoised)
    steps.append("CLAHE contrast")

    _, otsu = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    angle = _estimate_skew(otsu)
    if abs(angle) >= 0.5:
        contrast = _rotate(contrast, angle, 255)
        resized = _rotate(resized, angle, 255)
        steps.append(f"deskew {angle:+.1f} deg")
    else:
        angle = 0.0

    blurred = cv2.GaussianBlur(contrast, (0, 0), sigmaX=1.2)
    sharpened = cv2.addWeighted(contrast, 1.4, blurred, -0.4, 0)
    steps.append("unsharp mask")

    binary = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    steps.append("adaptive threshold")

    return PreprocessResult(
        original=resized,
        enhanced=sharpened,
        binary=binary,
        deskew_angle=angle,
        handwriting_score=_handwriting_score(binary),
        steps=steps,
    )
