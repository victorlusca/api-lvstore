"""
FastAPI app factory for api.lvstore.site.
"""
import os
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.responses import SafeJSONResponse

from app.audit import clear_request_context, set_request_context

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.dirname(_THIS_DIR)
_REPO_ROOT = os.path.dirname(_API_ROOT)
for _path in (_API_ROOT, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

_data_dir = os.environ.get("API_DATA_DIR", "").strip()
if not _data_dir:
    _local_data = os.path.join(_API_ROOT, "data")
    _repo_data = os.path.join(_REPO_ROOT, "data")
    _data_dir = _local_data if os.path.isdir(_local_data) else _repo_data
os.environ["API_DATA_DIR"] = _data_dir

_workdir = os.path.dirname(_data_dir) if os.path.basename(_data_dir).lower() == "data" else _API_ROOT
if os.path.isdir(_workdir):
    os.chdir(_workdir)

_VERSION = "3.0.0"
_BASE_PATH = os.environ.get("API_BASE_PATH", "/v3").strip() or "/v3"
if not _BASE_PATH.startswith("/"):
    _BASE_PATH = f"/{_BASE_PATH}"
_BASE_PATH = _BASE_PATH.rstrip("/") or "/v3"


def create_app() -> FastAPI:
    app = FastAPI(
        title="LV Store API",
        version=_VERSION,
        docs_url=f"{_BASE_PATH}/docs" if os.environ.get("API_DEBUG") == "1" else None,
        openapi_url=f"{_BASE_PATH}/openapi.json",
        redoc_url=None,
        default_response_class=SafeJSONResponse,
    )

    cors_origins = os.environ.get("API_CORS_ORIGINS", "").strip()
    if cors_origins:
        origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        actor = "anonymous"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            actor = "token"

        ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not ip:
            ip = request.client.host if request.client else "unknown"

        set_request_context(actor=actor, ip=ip, method=request.method, route=request.url.path)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    from app.routes_admin import router as admin_router
    from app.routes_advanced import router as advanced_router
    from app.routes_audit import router as audit_router
    from app.routes_edital import router as edital_router
    from app.routes_embeds import router as emb_router
    from app.routes_operational import router as operational_router
    from app.routes_players import router as players_router
    from app.routes_ranking import router as ranking_router
    from app.routes_references import router as ref_router
    from app.routes_squarecloud import router as squarecloud_router
    from app.routes_security import router as security_router
    from app.routes_setup import router as setup_router
    from app.routes_status import router as status_router
    from app.routes_tasks import router as tasks_router
    from app.routes_warnings import router as warnings_router

    for router in (
        setup_router,
        tasks_router,
        ref_router,
        squarecloud_router,
        emb_router,
        status_router,
        admin_router,
        players_router,
        ranking_router,
        edital_router,
        warnings_router,
        operational_router,
        advanced_router,
        security_router,
        audit_router,
    ):
        app.include_router(router, prefix=_BASE_PATH)

    @app.get("/health")
    async def health_root():
        return {"ok": True, "service": "lvstore-api", "version": _VERSION, "base_path": _BASE_PATH}

    @app.get(f"{_BASE_PATH}/health")
    async def health_base():
        return {"ok": True, "service": "lvstore-api", "version": _VERSION, "base_path": _BASE_PATH}

    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        return SafeJSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})

    return app


app = create_app()

