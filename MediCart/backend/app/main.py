import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.routers import (
    addresses,
    admin,
    auth,
    cart,
    catalogue,
    health,
    orders,
    pharmacist,
    prescriptions,
)

logger = logging.getLogger("medicart")

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "MediCart API starting: env=%s db=%s groq=%s ocr=%s",
        settings.app_env,
        "sqlite" if settings.is_sqlite else "postgresql",
        "configured" if settings.groq_configured else "off",
        settings.ocr_engine,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MediCart API",
        version="1.0.0",
        description="Online pharmacy with AI-assisted prescription reading.",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    api = APIRouter(prefix="/api")
    for module in (health, auth, catalogue, cart, addresses, orders, prescriptions, pharmacist, admin):
        api.include_router(module.router)
    app.include_router(api)

    # Serve the built React app from the same origin (locally after `npm run build`,
    # and on Vercel where the files are promoted to the CDN).
    if FRONTEND_DIST.is_dir():
        app.frontend("/", directory=str(FRONTEND_DIST), fallback="index.html")

    return app


app = create_app()
