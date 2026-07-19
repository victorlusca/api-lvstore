from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.routers import bots, players, ranking, management, system, edital, embeds, transcripts, audit, security
from app.core.exceptions import TranscriptException
from app.responses import SafeJSONResponse
from app.core.audit import audit_log
import json

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

    # Middleware de Auditoria AutomÃ¡tica
    @app.middleware("http")
    async def auto_audit_middleware(request: Request, call_next):
        method = request.method
        path = request.url.path
        
        # SÃ³ auditamos alteraÃ§Ãµes (POST, PUT, DELETE)
        if method in ["POST", "PUT", "DELETE"] and not path.endswith("/audit/bot"):
            # Tentar extrair app_id do path
            parts = path.strip("/").split("/")
            app_id = "unknown"
            if len(parts) >= 1:
                if parts[0] == "bots" and len(parts) >= 2:
                    app_id = parts[1]
                else:
                    app_id = parts[0]

            # Para nÃ£o consumir o corpo definitivamente e quebrar os handlers,
            # usamos o receive do Starlette para re-disponibilizar o corpo
            body = None
            if method != "DELETE":
                try:
                    body_bytes = await request.body()
                    if body_bytes:
                        body = json.loads(body_bytes)
                    
                    # Re-injetar o corpo para que o prÃ³ximo handler possa ler
                    async def receive():
                        return {"type": "http.request", "body": body_bytes}
                    request._receive = receive
                except:
                    body = "[Binary or unparseable]"

            # Log inicial
            audit_log(
                app_id=app_id,
                action=f"{method}_{path}",
                details={"path": path, "method": method, "body": body},
                event_type="AUTO_AUDIT"
            )

        response = await call_next(request)
        return response

    # Include Routers
    app.include_router(bots.router)
    app.include_router(players.router)
    app.include_router(ranking.router)
    app.include_router(management.router)
    app.include_router(system.router)
    app.include_router(edital.router)
    app.include_router(embeds.router)
    app.include_router(transcripts.router)
    app.include_router(audit.router)
    app.include_router(security.router)

    @app.exception_handler(TranscriptException)
    async def transcript_exception_handler(request: Request, exc: TranscriptException):
        return SafeJSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "code": exc.code,
                "message": exc.message
            }
        )

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

        # Detalhes do erro só são expostos ao cliente em DEBUG (evita vazamento
        # de mensagens internas em produção). O log server-side acima preserva o
        # error_msg + stack_trace para diagnóstico.
        content = {
            "ok": False,
            "error": "Internal Server Error"
        }

        if settings.DEBUG:
            content["detail"] = error_msg
            content["traceback"] = stack_trace

        return SafeJSONResponse(
            status_code=500,
            content=content,
            headers=headers
        )

    return app

app = create_app()
