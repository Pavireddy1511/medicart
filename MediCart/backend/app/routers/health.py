from fastapi import APIRouter
from sqlalchemy import text

from app.computer_vision.ocr import engine_status
from app.core.dependencies import DbSession, SettingsDep

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession, settings: SettingsDep):
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - report, never leak the driver error
        database = "error"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "app": settings.app_name,
        "environment": settings.app_env,
        "database": database,
        "database_backend": "sqlite" if settings.is_sqlite else "postgresql",
        "groq_configured": settings.groq_configured,
        "groq_vision_configured": settings.groq_vision_configured,
        "ocr": engine_status(settings),
    }
