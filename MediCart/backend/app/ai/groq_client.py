import json
import logging

import openai
from pydantic import ValidationError as PydanticValidationError

from app.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas import StructuredPrescription
from app.core.config import Settings

logger = logging.getLogger(__name__)


class GroqUnavailable(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _client(settings: Settings) -> openai.OpenAI:
    return openai.OpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        timeout=settings.groq_timeout_seconds,
        max_retries=1,
    )


def _extract_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("no JSON object found", content, 0)
    return json.loads(content[start : end + 1])


def structure_with_groq(ocr_text: str, settings: Settings) -> tuple[StructuredPrescription, str]:
    if not settings.groq_configured:
        raise GroqUnavailable("not_configured", "Groq API is not configured")

    try:
        response = _client(settings).chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(ocr_text)},
            ],
            temperature=0,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
    except openai.AuthenticationError as exc:
        raise GroqUnavailable("auth_failed", "Groq rejected the API key") from exc
    except openai.RateLimitError as exc:
        raise GroqUnavailable("rate_limited", "Groq rate limit or quota reached") from exc
    except openai.APITimeoutError as exc:
        raise GroqUnavailable("timeout", "Groq did not answer in time") from exc
    except openai.NotFoundError as exc:
        raise GroqUnavailable("model_unavailable", "The configured Groq model is unavailable") from exc
    except openai.APIConnectionError as exc:
        raise GroqUnavailable("network", "Could not reach the Groq API") from exc
    except openai.APIStatusError as exc:
        raise GroqUnavailable("api_error", f"Groq returned HTTP {exc.status_code}") from exc
    except openai.OpenAIError as exc:
        raise GroqUnavailable("api_error", "Groq request failed") from exc

    try:
        content = response.choices[0].message.content or ""
    except (IndexError, AttributeError) as exc:
        raise GroqUnavailable("invalid_response", "Groq returned an empty response") from exc

    try:
        payload = _extract_json(content)
    except json.JSONDecodeError as exc:
        logger.warning("Groq returned non-JSON content: %.200s", content)
        raise GroqUnavailable("invalid_json", "Groq returned malformed JSON") from exc

    try:
        parsed = StructuredPrescription.model_validate(payload)
    except PydanticValidationError as exc:
        logger.warning("Groq JSON failed validation: %s", exc.errors()[:3])
        raise GroqUnavailable("invalid_schema", "Groq response did not match the schema") from exc

    model_name = getattr(response, "model", None) or settings.groq_model
    return parsed, str(model_name)
