"""Carga y consulta de documentos fuente. Solo administradores."""

import json
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile

from api.contracts import (
    DocumentDetail, DocumentList, DocumentSummary, Identifier, MAX_UPLOAD_BYTES, TextDocumentRequest,
)
from api.database import Store
from api.dependencies import get_store, require_admin, require_document
from api.documents import MIME_TYPES, extract_document
from api.errors import ApiError

router = APIRouter(prefix="/api/v1/documentos", tags=["Documentos"], dependencies=[Depends(require_admin)])


@router.post("", response_model=DocumentSummary, status_code=201)
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


@router.post("/texto", response_model=DocumentSummary, status_code=201)
def create_text_document(body: TextDocumentRequest, db: Store = Depends(get_store)):
    raw = body.documento_contenido.encode("utf-8")
    name, kind, documents = extract_document("documento.txt", raw)
    return db.create_document(body.documento_titulo, name, kind, raw, documents)


@router.get("", response_model=DocumentList)
def list_documents(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Store = Depends(get_store),
):
    return db.list_documents(limit, offset)


@router.get("/{documento_id}", response_model=DocumentDetail)
def get_document(documento_id: Identifier, db: Store = Depends(get_store)):
    document = require_document(db, documento_id)
    pages = json.loads(document.pop("paginas_json"))
    document.pop("original")
    return {**document, "documento_contenido": "\n\n".join(page["page_content"] for page in pages)}


@router.get("/{documento_id}/original", response_class=Response)
def download_document(documento_id: Identifier, db: Store = Depends(get_store)):
    document = require_document(db, documento_id)
    return Response(
        content=document["original"], media_type=MIME_TYPES[document["tipo"]],
        headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(document["nombre_archivo"], safe="")},
    )
