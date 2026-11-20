"""Optional transcription of a prescription page with a Groq vision model.

Printed-text OCR engines cannot read doctor handwriting. When GROQ_VISION_MODEL is set,
handwritten pages (or pages where OCR found nothing) are sent to the model, which is asked
only to transcribe what is written, line by line. The result feeds the same structuring and
matching pipeline and is subject to the same invention guard as any other OCR text.
"""

import base64
import json
import logging

import cv2
import numpy as np
import openai

from app.ai.groq_client import GroqUnavailable, _client, _extract_json
from app.core.config import Settings

logger = logging.getLogger(__name__)

TRANSCRIBE_PROMPT = (
    "This is a photo of a medical prescription. Transcribe the text exactly as written, one entry "
    "per line, in reading order. Keep medicine names, strengths, dose, frequency and duration on "
    "the same line as they appear. Do not correct, complete, translate or interpret anything; if a "
    'word is unreadable write "[illegible]". Do not add medicines or advice that are not written. '
    'Return only JSON: {"lines": ["..."], "handwritten": true|false, "legibility": "good|fair|poor"}'
)


def _encode(image: np.ndarray, max_side: int = 1400) -> str:
    h, w = image.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise GroqUnavailable("encode_failed", "Could not encode the page for transcription")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def transcribe_with_groq_vision(image: np.ndarray, settings: Settings) -> tuple[list[str], dict, str]:
    """Return (lines, meta, model). Raises GroqUnavailable on any failure."""
    if not settings.groq_api_key or not settings.groq_vision_model:
        raise GroqUnavailable("not_configured", "Groq vision model is not configured")

    try:
        response = _client(settings).chat.completions.create(
            model=settings.groq_vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": TRANSCRIBE_PROMPT},
                        {"type": "image_url", "image_url": {"url": _encode(image)}},
                    ],
                }
            ],
            temperature=0,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )
    except openai.AuthenticationError as exc:
        raise GroqUnavailable("auth_failed", "Groq rejected the API key") from exc
    except openai.RateLimitError as exc:
        raise GroqUnavailable("rate_limited", "Groq rate limit or quota reached") from exc
    except openai.APITimeoutError as exc:
        raise GroqUnavailable("timeout", "Groq did not answer in time") from exc
    except openai.NotFoundError as exc:
        raise GroqUnavailable("model_unavailable", "The configured Groq vision model is unavailable") from exc
    except openai.BadRequestError as exc:
        raise GroqUnavailable("api_error", "The Groq vision model rejected the request") from exc
    except openai.APIConnectionError as exc:
        raise GroqUnavailable("network", "Could not reach the Groq API") from exc
    except openai.APIStatusError as exc:
        raise GroqUnavailable("api_error", f"Groq returned HTTP {exc.status_code}") from exc
    except openai.OpenAIError as exc:
        raise GroqUnavailable("api_error", "Groq request failed") from exc

    try:
        content = response.choices[0].message.content or ""
        payload = _extract_json(content)
    except (IndexError, AttributeError, json.JSONDecodeError) as exc:
        raise GroqUnavailable("invalid_json", "Groq vision returned malformed JSON") from exc

    raw_lines = payload.get("lines") if isinstance(payload, dict) else None
    if not isinstance(raw_lines, list):
        raise GroqUnavailable("invalid_schema", "Groq vision response did not contain lines")
    lines = [str(line).strip() for line in raw_lines if str(line).strip()][:80]
    meta = {
        "handwritten": bool(payload.get("handwritten")) if isinstance(payload, dict) else None,
        "legibility": str(payload.get("legibility", "")) if isinstance(payload, dict) else "",
    }
    model_name = getattr(response, "model", None) or settings.groq_vision_model
    return lines, meta, str(model_name)
