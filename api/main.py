"""API para documentos, generación estructurada e historial; sin frontend."""

from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
import sqlite3
from typing import Annotated, Callable, Literal
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.documents import Document
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from api.contracts import (
    Catalogs, ContentList, ContentRequest, DocumentDetail, DocumentList, DocumentSummary,
    HealthResponse, Identifier, MAX_DOCUMENT_CHARACTERS, MAX_PDF_PAGES, MAX_UPLOAD_BYTES,
    TextDocumentRequest,
)
from api import database
from api.database import Store
from api.routes.sesion import router as sesion_router
from api.routes.temas import router as temas_router
from api.routes.usuarios import router as usuarios_router
from api.documents import MIME_TYPES, extract_document
from api.errors import ApiError
from errors import ConfigurationError, NoContextError
from schemas import (
    DRAFT_SCHEMAS, PROFILE_GUIDANCE, EducationalResponse, ErrorDetail, ErrorResponse,
    GenerationRequest, UserProfile,
)

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
logger = logging.getLogger(__name__)


HTTP_ERROR_CODES = {
    400: "SOLICITUD_INVALIDA",
    401: "AUTENTICACION_REQUERIDA",
    403: "PERMISOS_INSUFICIENTES",
    404: "RECURSO_NO_ENCONTRADO",
    409: "CONFLICTO",
}


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_generator() -> Callable:
    from generation import generate_content

    return generate_content


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(codigo=code, mensaje=message))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def require_document(store: Store, identifier: str) -> dict:
    document = store.get_document(identifier)
    if document is None:
        raise ApiError(404, "DOCUMENTO_NO_ENCONTRADO", "No existe el documento solicitado.")
    return document


def require_content(store: Store, identifier: str) -> EducationalResponse:
    content = store.get_content(identifier)
    if content is None:
        raise ApiError(404, "CONTENIDO_NO_ENCONTRADO", "No existe el contenido solicitado.")
    return content


def create_app(db_path: str | Path | None = None) -> FastAPI:
    # Sin ruta explícita, la base se resuelve al iniciar (database.DB_PATH), compartida con auth y temas.
    if db_path is not None:
        database.DB_PATH = database.resolve_db_path(db_path)
    store = Store()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        store.initialize()
        yield

    application = FastAPI(
        title="NuevaMente API", version="1.0.0",
        description=(
            "Documentos, generación e historial. Perfiles: Principiante, Intermedio, Avanzado. "
            "La respuesta educativa mantiene el contrato JSON del proyecto. "
            "Incluye sesiones, usuarios, roles y temas asignados (F08)."
        ),
        lifespan=lifespan,
        responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 413, 415, 422, 500, 502, 503)},
    )
    application.state.store = store
    origins = [origin.strip() for origin in os.getenv("NUEVAMENTE_CORS_ORIGINS", "").split(",") if origin.strip()]
    if origins:
        application.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type", "Authorization"], expose_headers=["X-Contenido-ID", "Location", "Content-Disposition"],
        )

    @application.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return error_response(exc.code, exc.message, exc.status_code)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # No se incluye input, para no reflejar documentos o datos sensibles en el error.
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in exc.errors()})
        return error_response("ENTRADA_INVALIDA", "Revisa los campos: " + ", ".join(fields), 422)

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        code = HTTP_ERROR_CODES.get(exc.status_code, "ERROR_HTTP")
        message = exc.detail if isinstance(exc.detail, str) and exc.status_code in HTTP_ERROR_CODES else (
            "La ruta, el método o la solicitud no son válidos."
        )
        response = error_response(code, message, exc.status_code)
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

    @application.get("/health", response_model=HealthResponse, tags=["Sistema"])
    def health(db: Store = Depends(get_store)):
        db.ping()
        return HealthResponse()

    @application.get("/salud", tags=["Sistema"], include_in_schema=False)
    def salud(db: Store = Depends(get_store)):
        db.ping()
        return {"estado": "ok", "servicio": "NuevaMente API"}

    @application.get("/api/v1/catalogos", response_model=Catalogs, tags=["Sistema"])
    def catalogs():
        return Catalogs(
            perfiles=list(PROFILE_GUIDANCE), formatos=list(DRAFT_SCHEMAS),
            extensiones_documento=[".pdf", ".md", ".txt"], max_upload_bytes=MAX_UPLOAD_BYTES,
            max_documento_caracteres=MAX_DOCUMENT_CHARACTERS, max_paginas_pdf=MAX_PDF_PAGES,
        )

    @application.post("/api/v1/documentos", response_model=DocumentSummary, status_code=201, tags=["Documentos"])
    def upload_document(
        archivo: Annotated[UploadFile, File()],
        documento_titulo: Annotated[str | None, Form(min_length=1, max_length=200)] = None,
        db: Store = Depends(get_store),
    ):
        try:
            raw = archivo.file.read(MAX_UPLOAD_BYTES + 1)
        finally:
            archivo.file.close()
        name, kind, documents = extract_document(archivo.filename or "", raw)
        title = documento_titulo.strip() if documento_titulo is not None else Path(name).stem[:200]
        if not title:
            raise ApiError(422, "TITULO_INVALIDO", "El título no puede quedar vacío.")
        return db.create_document(title, name, kind, raw, documents)

    @application.post("/api/v1/documentos/texto", response_model=DocumentSummary, status_code=201, tags=["Documentos"])
    def create_text_document(body: TextDocumentRequest, db: Store = Depends(get_store)):
        raw = body.documento_contenido.encode("utf-8")
        name, kind, documents = extract_document("documento.txt", raw)
        return db.create_document(body.documento_titulo, name, kind, raw, documents)

    @application.get("/api/v1/documentos", response_model=DocumentList, tags=["Documentos"])
    def list_documents(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        db: Store = Depends(get_store),
    ):
        return db.list_documents(limit, offset)

    @application.get("/api/v1/documentos/{documento_id}", response_model=DocumentDetail, tags=["Documentos"])
    def get_document(documento_id: Identifier, db: Store = Depends(get_store)):
        document = require_document(db, documento_id)
        pages = json.loads(document.pop("paginas_json"))
        document.pop("original")
        return {**document, "documento_contenido": "\n\n".join(page["page_content"] for page in pages)}

    @application.get("/api/v1/documentos/{documento_id}/original", response_class=Response, tags=["Documentos"])
    def download_document(documento_id: Identifier, db: Store = Depends(get_store)):
        document = require_document(db, documento_id)
        return Response(
            content=document["original"], media_type=MIME_TYPES[document["tipo"]],
            headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(document["nombre_archivo"], safe="")},
        )

    @application.post(
        "/api/v1/contenidos", response_model=EducationalResponse, status_code=201, tags=["Contenidos"],
        responses={201: {"description": "JSON educativo persistido. Identificador en X-Contenido-ID y recurso en Location.",
                         "headers": {"X-Contenido-ID": {"schema": {"type": "string"}}, "Location": {"schema": {"type": "string"}}}}},
    )
    def generate(body: ContentRequest, response: Response, db: Store = Depends(get_store), generator: Callable = Depends(get_generator)):
        document = require_document(db, body.documento_id)
        pages = [Document(**page) for page in json.loads(document["paginas_json"])]
        request = GenerationRequest.model_validate(body.model_dump(exclude={"documento_id"}))
        try:
            result = generator(request, source_docs=pages)
            if isinstance(result, EducationalResponse):
                result = result.model_dump(mode="json")
            result = EducationalResponse.model_validate(result)
            actual = result.metadatos
            if (actual.perfil_aplicado, actual.formato_generado, actual.nicho_sector, actual.nivel_detalle) != (
                request.perfil_destinatario, request.formato_salida, request.nicho_sector, request.nivel_detalle,
            ):
                raise ApiError(502, "SALIDA_INVALIDA", "Los metadatos no corresponden a la solicitud.")
        except ApiError:
            raise
        except ConfigurationError as exc:
            raise ApiError(503, "CONFIGURACION_INCOMPLETA", "Configura GEMINI_API_KEY en el backend para generar contenido.") from exc
        except NoContextError as exc:
            raise ApiError(422, "SIN_CONTEXTO", "No se encontró contexto relevante para el tema en ese documento.") from exc
        except (ValidationError, OutputParserException) as exc:
            raise ApiError(502, "SALIDA_INVALIDA", "El modelo devolvió una respuesta incompatible con el contrato.") from exc
        except Exception as exc:
            logger.error("Fallo del generador: %s", type(exc).__name__)
            raise ApiError(502, "GENERACION_FALLIDA", "No se pudo generar. Revisa conexión, modelo y cuota del proveedor.") from exc

        # No se mantiene una transacción SQL abierta durante la llamada al LLM.
        identifier = db.save_content(body, result)
        response.headers["X-Contenido-ID"] = identifier
        response.headers["Location"] = f"/api/v1/contenidos/{identifier}"
        return result

    @application.get("/api/v1/contenidos", response_model=ContentList, tags=["Contenidos"])
    def list_contents(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        documento_id: Identifier | None = None,
        perfil: UserProfile | None = None,
        status: Literal["exito", "requiere_revision"] | None = None,
        db: Store = Depends(get_store),
    ):
        return db.list_contents(limit, offset, documento_id=documento_id, perfil=perfil, status=status)

    @application.get("/api/v1/contenidos/{contenido_id}", response_model=EducationalResponse, tags=["Contenidos"])
    def get_content(contenido_id: Identifier, db: Store = Depends(get_store)):
        return require_content(db, contenido_id)

    @application.get("/api/v1/contenidos/{contenido_id}/descarga", response_class=Response, tags=["Contenidos"])
    def download_content(contenido_id: Identifier, db: Store = Depends(get_store)):
        result = require_content(db, contenido_id)
        return Response(
            content=result.model_dump_json(indent=2).encode("utf-8"), media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="contenido-{contenido_id}.json"'},
        )

    application.include_router(sesion_router)
    application.include_router(temas_router)
    application.include_router(usuarios_router)
    return application


app = create_app()
