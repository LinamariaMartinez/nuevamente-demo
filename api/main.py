"""Aplicación FastAPI de NuevaMente: configuración, manejo de errores y registro de routers."""

from contextlib import asynccontextmanager
from http import HTTPStatus
import logging
import os
from pathlib import Path
import sqlite3

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from api import database
from api.auth import require_password_updated
from api.contracts import Catalogs, HealthResponse, MAX_DOCUMENT_CHARACTERS, MAX_PDF_PAGES, MAX_UPLOAD_BYTES
from api.database import Store
from api.dependencies import get_oci_storage, get_store
from api.errors import ApiError
from api.routes.contenidos import get_generator, router as contenidos_router
from api.routes.documentos import router as documentos_router
from api.routes.sesion import router as sesion_router
from api.routes.temas import router as temas_router
from api.routes.temas_recursos import router as temas_recursos_router
from api.routes.usuarios import router as usuarios_router
from oci_storage import OCIStorageManager
from schemas import DRAFT_SCHEMAS, NICHE_CATALOG, PROFILE_GUIDANCE, ErrorDetail, ErrorResponse

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
logger = logging.getLogger(__name__)

__all__ = ["app", "create_app", "get_generator", "get_oci_storage"]

HTTP_ERROR_CODES = {
    400: "SOLICITUD_INVALIDA",
    401: "AUTENTICACION_REQUERIDA",
    403: "PERMISOS_INSUFICIENTES",
    404: "RECURSO_NO_ENCONTRADO",
    409: "CONFLICTO",
}
# Mensajes por defecto cuando la excepción trae la frase estándar en inglés (p. ej. "Not Found").
HTTP_DEFAULT_MESSAGES = {
    400: "La solicitud no es válida.",
    401: "Debes iniciar sesión.",
    403: "No tienes permisos para realizar esta acción.",
    404: "La ruta o el recurso solicitado no existe.",
    409: "La operación entra en conflicto con el estado actual.",
}
GENERIC_HTTP_MESSAGE = "La ruta, el método o la solicitud no son válidos."


def error_response(code: str, message: str, status_code: int, headers: dict[str, str] | None = None) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(codigo=code, mensaje=message))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"), headers=headers)


def http_error_message(exc: HTTPException) -> str:
    if exc.status_code not in HTTP_ERROR_CODES:
        return GENERIC_HTTP_MESSAGE
    if isinstance(exc.detail, str) and exc.detail and exc.detail != HTTPStatus(exc.status_code).phrase:
        return exc.detail
    return HTTP_DEFAULT_MESSAGES[exc.status_code]


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return error_response(exc.code, exc.message, exc.status_code, exc.headers)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # No se incluye input, para no reflejar documentos o datos sensibles en el error.
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in exc.errors()})
        return error_response("ENTRADA_INVALIDA", "Revisa los campos: " + ", ".join(fields), 422)

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        code = HTTP_ERROR_CODES.get(exc.status_code, "ERROR_HTTP")
        response = error_response(code, http_error_message(exc), exc.status_code)
        response.headers.update(getattr(exc, "headers", None) or {})
        return response

    @application.exception_handler(sqlite3.Error)
    async def database_error_handler(request: Request, exc: sqlite3.Error):
        logger.error("Fallo de persistencia: %s", type(exc).__name__)
        return error_response("BASE_DATOS_NO_DISPONIBLE", "No se pudo acceder a la base de datos.", 503)

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.error("Fallo de backend: %s", type(exc).__name__)
        return error_response("ERROR_INTERNO", "No se pudo completar la operación.", 500)


def register_system_routes(application: FastAPI) -> None:
    @application.get("/health", response_model=HealthResponse, tags=["Sistema"])
    def health(db: Store = Depends(get_store)):
        db.ping()
        return HealthResponse()

    @application.get("/api/v1/catalogos", response_model=Catalogs, tags=["Sistema"])
    def catalogs(_: dict = Depends(require_password_updated)):
        return Catalogs(
            perfiles=list(PROFILE_GUIDANCE), formatos=list(DRAFT_SCHEMAS), sectores=list(NICHE_CATALOG),
            extensiones_documento=[".pdf", ".md", ".txt"], max_upload_bytes=MAX_UPLOAD_BYTES,
            max_documento_caracteres=MAX_DOCUMENT_CHARACTERS, max_paginas_pdf=MAX_PDF_PAGES,
        )


def create_app(db_path: str | Path | None = None) -> FastAPI:
    # Sin ruta explícita, la base se resuelve en cada operación (database.DB_PATH), compartida con auth y temas.
    if db_path is not None:
        database.DB_PATH = database.resolve_db_path(db_path)
    store = Store()
    oci_storage = OCIStorageManager()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        store.initialize()
        yield

    application = FastAPI(
        title="NuevaMente API", version="1.2.0",
        description=(
            "Documentos, temas, generación, historial y revisión. Perfiles: Principiante, Intermedio, Avanzado. "
            "Todas las rutas, salvo /health y POST /api/v1/sesion, requieren `Authorization: Bearer <token>`. "
            "Los estudiantes generan solo sobre temas asignados y ven únicamente su material aprobado."
        ),
        lifespan=lifespan,
        responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 413, 415, 422, 500, 502, 503)},
    )
    application.state.store = store
    application.state.oci_storage = oci_storage
    origins = [origin.strip() for origin in os.getenv("NUEVAMENTE_CORS_ORIGINS", "").split(",") if origin.strip()]
    if origins:
        application.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "Authorization"], expose_headers=["X-Contenido-ID", "Location", "Content-Disposition"],
        )

    register_error_handlers(application)
    register_system_routes(application)
    for router in (
        documentos_router, contenidos_router, sesion_router, temas_router, temas_recursos_router, usuarios_router,
    ):
        application.include_router(router)
    return application


app = create_app()
