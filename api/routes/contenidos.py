"""Generación de material educativo, historial y revisión por el administrador."""

import logging
from typing import Annotated, Callable, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from langchain_core.documents import Document
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from api.auth import require_password_updated
from api.contracts import (
    ContentList, ContentRequest, ContentResponse, Fuente, Identifier, PendingReviewResponse, TopicId,
)
from api.database import Store, is_pending, pages_from_document
from api.dependencies import get_oci_storage, get_store, is_admin, require_admin, require_document, require_topic_access
from api.errors import ApiError
from errors import ConfigurationError, NoContextError
from oci_storage import OCIStorageManager
from schemas import DEFAULT_DETAIL, DEFAULT_NICHE, EducationalResponse, GenerationRequest, UserProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/contenidos", tags=["Contenidos"])

MAX_EXTRACT_CHARACTERS = 300


def get_generator() -> Callable:
    """Devuelve (EducationalResponse, fragmentos recuperados). Se sustituye en pruebas."""
    from generation import generate_content_with_sources

    return generate_content_with_sources


def backup_content_to_oci(oci: OCIStorageManager, content: ContentResponse, topic: str | None = None) -> None:
    """Persiste el paquete educativo JSON aprobado en el bucket Always Free de OCI."""
    _, result = oci.upload_educational_json(
        content,
        topic=topic,
        profile=content.metadatos.perfil_aplicado,
        output_format=content.metadatos.formato_generado,
        raise_on_error=False,
    )
    if result.status_upload == "error":
        logger.warning("No se pudo respaldar el contenido '%s' en OCI (%s).", content.id, result.objeto_id)


def require_visible_content(store: Store, user: dict, identifier: str) -> dict:
    """Un estudiante solo ve su propio material visible; el resto responde 404 para no filtrar ids."""
    record = store.get_content(identifier)
    if record is None or (not is_admin(user) and (record["id_usuario"] != user["id_usuario"] or is_pending(record))):
        raise ApiError(404, "CONTENIDO_NO_ENCONTRADO", "No existe el contenido solicitado.")
    return record


def require_pending_content(store: Store, identifier: str) -> dict:
    record = store.get_content(identifier)
    if record is None:
        raise ApiError(404, "CONTENIDO_NO_ENCONTRADO", "No existe el contenido solicitado.")
    if not is_pending(record):
        raise ApiError(409, "CONTENIDO_NO_PENDIENTE", "El contenido no está pendiente de revisión.")
    return record


def build_sources(documents: list[Document]) -> list[Fuente]:
    sources = []
    for document in documents:
        metadata = document.metadata or {}
        text = " ".join(document.page_content.split())
        if not (metadata.get("documento_id") and metadata.get("documento_titulo") and text):
            continue
        page = metadata.get("page")
        extract = text if len(text) <= MAX_EXTRACT_CHARACTERS else text[:MAX_EXTRACT_CHARACTERS].rstrip() + "…"
        sources.append(Fuente(
            documento_id=metadata["documento_id"], documento=metadata["documento_titulo"],
            fragmento=len(sources) + 1, pagina=page if isinstance(page, int) and page >= 1 else None,
            extracto=extract,
        ))
    return sources


def content_response(record: dict) -> ContentResponse:
    return ContentResponse.model_validate({
        **record["respuesta"].model_dump(mode="json"),
        "id": record["id"], "creado_en": record["creado_en"], "id_tema": record["id_tema"],
        "aprobado_en": record["aprobado_en"],
        "fuentes": [source.model_dump(mode="json") for source in record["fuentes"]],
    })


def resolve_source(db: Store, user: dict, body: ContentRequest) -> tuple[list[Document], str, str, str]:
    """Páginas fuente, nicho, nivel y consulta según el origen pedido (tema asignado o documento para admin)."""
    if body.documento_id is not None:
        if not is_admin(user):
            raise ApiError(403, "PERMISOS_INSUFICIENTES", "Genera material a partir de un tema asignado (id_tema).")
        pages = pages_from_document(require_document(db, body.documento_id))
        return pages, body.nicho_sector or DEFAULT_NICHE, body.nivel_detalle or DEFAULT_DETAIL, body.tema
    topic = require_topic_access(db, user, body.id_tema)
    pages = db.topic_pages(body.id_tema)
    if not pages:
        raise ApiError(422, "SIN_DOCUMENTOS_ASOCIADOS", "El tema todavía no tiene documentos asociados.")
    return pages, topic["nicho_sector"], topic["nivel_detalle"], body.tema or topic["nombre"]


def run_generator(
    generator: Callable, request: GenerationRequest, pages: list[Document],
) -> tuple[EducationalResponse, list[Fuente]]:
    """Ejecuta el generador y traduce sus fallos a errores HTTP amigables."""
    try:
        generated, retrieved = generator(request, source_docs=pages)
        result = EducationalResponse.model_validate(generated)
    except ConfigurationError as exc:
        raise ApiError(503, "CONFIGURACION_INCOMPLETA", "Configura GEMINI_API_KEY en el backend para generar contenido.") from exc
    except NoContextError as exc:
        raise ApiError(422, "SIN_CONTEXTO", "No se encontró contexto relevante para la consulta en los documentos del tema.") from exc
    except (ValidationError, OutputParserException) as exc:
        raise ApiError(502, "SALIDA_INVALIDA", "El modelo devolvió una respuesta incompatible con el contrato.") from exc
    except Exception as exc:
        logger.error("Fallo del generador: %s", type(exc).__name__)
        raise ApiError(502, "GENERACION_FALLIDA", "No se pudo generar. Revisa conexión, modelo y cuota del proveedor.") from exc
    actual = result.metadatos
    if (actual.perfil_aplicado, actual.formato_generado, actual.nicho_sector, actual.nivel_detalle) != (
        request.perfil_destinatario, request.formato_salida, request.nicho_sector, request.nivel_detalle,
    ):
        raise ApiError(502, "SALIDA_INVALIDA", "Los metadatos no corresponden a la solicitud.")
    return result, build_sources(retrieved)


@router.post(
    "", response_model=ContentResponse, status_code=201,
    responses={
        201: {"description": "JSON educativo persistido, con id, creado_en y fuentes.",
              "headers": {"X-Contenido-ID": {"schema": {"type": "string"}}, "Location": {"schema": {"type": "string"}}}},
        202: {"model": PendingReviewResponse,
              "description": "Solo estudiantes: el material no superó la revisión y queda pendiente para un administrador."},
    },
)
def generate(
    body: ContentRequest, response: Response,
    user: dict = Depends(require_password_updated),
    db: Store = Depends(get_store), generator: Callable = Depends(get_generator),
    oci: OCIStorageManager = Depends(get_oci_storage),
):
    pages, niche, detail, query = resolve_source(db, user, body)
    body = body.model_copy(update={"tema": query})
    request = GenerationRequest(
        tema=query, perfil_destinatario=body.perfil_destinatario, formato_salida=body.formato_salida,
        nicho_sector=niche, nivel_detalle=detail,
    )
    result, sources = run_generator(generator, request, pages)

    # No se mantiene una transacción SQL abierta durante la llamada al LLM.
    identifier, created = db.save_content(body, result, id_usuario=user["id_usuario"], fuentes=sources)
    if not is_admin(user) and result.status == "requiere_revision":
        pending = PendingReviewResponse(id=identifier, creado_en=created)
        return JSONResponse(status_code=202, content=pending.model_dump(mode="json"), headers={"X-Contenido-ID": identifier})
    response.headers["X-Contenido-ID"] = identifier
    response.headers["Location"] = f"/api/v1/contenidos/{identifier}"
    content = content_response({
        "id": identifier, "creado_en": created, "id_tema": body.id_tema, "aprobado_en": None,
        "respuesta": result, "fuentes": sources,
    })
    if result.status == "exito":
        backup_content_to_oci(oci, content, topic=query)
    return content


@router.get("", response_model=ContentList)
def list_contents(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    documento_id: Identifier | None = None,
    id_tema: TopicId | None = None,
    id_usuario: Annotated[int | None, Query(description="Solo administradores.")] = None,
    perfil: UserProfile | None = None,
    status: Literal["exito", "requiere_revision"] | None = None,
    pendiente: Annotated[bool | None, Query(description="Solo administradores: true lista lo que falta revisar.")] = None,
    user: dict = Depends(require_password_updated),
    db: Store = Depends(get_store),
):
    if not is_admin(user):
        id_usuario, pendiente = user["id_usuario"], False
    return db.list_contents(
        limit, offset, documento_id=documento_id, perfil=perfil, status=status, id_tema=id_tema,
        id_usuario=id_usuario, pendiente=pendiente,
    )


@router.get("/{contenido_id}", response_model=ContentResponse)
def get_content(contenido_id: Identifier, user: dict = Depends(require_password_updated), db: Store = Depends(get_store)):
    return content_response(require_visible_content(db, user, contenido_id))


@router.get("/{contenido_id}/descarga", response_class=Response)
def download_content(contenido_id: Identifier, user: dict = Depends(require_password_updated), db: Store = Depends(get_store)):
    result = content_response(require_visible_content(db, user, contenido_id))
    return Response(
        content=result.model_dump_json(indent=2).encode("utf-8"), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="contenido-{contenido_id}.json"'},
    )


@router.post("/{contenido_id}/aprobar", response_model=ContentResponse)
def approve_content(
    contenido_id: Identifier,
    _: dict = Depends(require_admin),
    db: Store = Depends(get_store),
    oci: OCIStorageManager = Depends(get_oci_storage),
):
    """El material pasa a ser visible para el estudiante; se conserva la evaluación original."""
    require_pending_content(db, contenido_id)
    db.approve_content(contenido_id)
    record = db.get_content(contenido_id)
    content = content_response(record)
    backup_content_to_oci(oci, content, topic=record.get("tema"))
    return content


@router.post("/{contenido_id}/rechazar", status_code=204, response_class=Response)
def reject_content(contenido_id: Identifier, _: dict = Depends(require_admin), db: Store = Depends(get_store)):
    """Elimina el material pendiente; el estudiante puede volver a generarlo."""
    require_pending_content(db, contenido_id)
    db.delete_content(contenido_id)
    return Response(status_code=204)
