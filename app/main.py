from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.routers import bots, players, ranking, management, system
from app.responses import SafeJSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url=None,
        default_response_class=SafeJSONResponse,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://meusitedeteste.squareweb.app",
            "http://localhost:5173",
            "http://localhost:3000",
            "https://lvstore.site",
            "https://www.lvstore.site",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include Routers
    app.include_router(bots.router)
    app.include_router(players.router)
    app.include_router(ranking.router)
    app.include_router(management.router)
    app.include_router(system.router)

    @app.get("/health")
    async def health():
        return {
            "status": "online",
            "version": settings.VERSION,
            "service": settings.APP_NAME
        }

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        import traceback
        error_msg = str(exc)
        stack_trace = traceback.format_exc()
        logger.error(f"Global error: {error_msg}\n{stack_trace}")
        
        # Obter a origem da requisição para o CORS
        origin = request.headers.get("origin")
        allowed_origins = [
            "https://meusitedeteste.squareweb.app",
            "http://localhost:5173",
            "http://localhost:3000",
            "https://lvstore.site",
            "https://www.lvstore.site",
        ]
        
        headers = {}
        if origin in allowed_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
        elif "*" in allowed_origins or not allowed_origins:
            headers["Access-Control-Allow-Origin"] = "*"

        # Incluir detalhes do erro para ajudar no debug do usuário
        content = {
            "ok": False, 
            "error": "Internal Server Error", 
            "detail": error_msg
        }
        
        if settings.DEBUG:
            content["traceback"] = stack_trace

        return SafeJSONResponse(
            status_code=500,
            content=content,
            headers=headers
        )

    return app

app = create_app()
