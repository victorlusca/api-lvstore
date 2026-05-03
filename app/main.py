from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.routers import bots, players, ranking, management

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url=None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # Adjust in production if needed
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include Routers
    app.include_router(bots.router)
    app.include_router(players.router)
    app.include_router(ranking.router)
    app.include_router(management.router)

    @app.get("/health")
    async def health():
        return {
            "status": "online",
            "version": settings.VERSION,
            "service": settings.APP_NAME
        }

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Global error: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Internal Server Error", "detail": str(exc)}
        )

    return app

app = create_app()
