"""Contrato HTTP propuesto; no sustituye el src/contrato.py del equipo frontend."""

from typing import Annotated, Literal

from pydantic import Field

from schemas import GenerationRequest, OutputFormat, StrictModel, Text, UserProfile

Identifier = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
MAX_DOCUMENT_CHARACTERS = 250_000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100


class TextDocumentRequest(StrictModel):
    documento_titulo: Text = Field(max_length=200)
    documento_contenido: Text = Field(min_length=11, max_length=MAX_DOCUMENT_CHARACTERS)


class ContentRequest(GenerationRequest):
    documento_id: Identifier


class DocumentSummary(StrictModel):
    id: Identifier
    documento_titulo: Text
    nombre_archivo: Text
    tipo: Literal["pdf", "md", "txt"]
    tamano_bytes: int = Field(ge=1)
    fragmentos_extraidos: int = Field(ge=1)
    creado_en: Text = Field(description="Fecha ISO 8601 en UTC.")


class DocumentDetail(DocumentSummary):
    documento_contenido: Text


class DocumentList(StrictModel):
    items: list[DocumentSummary]
    total: int = Field(ge=0)
    limit: int
    offset: int


class ContentSummary(StrictModel):
    id: Identifier
    documento_id: Identifier
    titulo: Text
    tema: Text
    perfil_aplicado: UserProfile
    formato_generado: OutputFormat
    status: Literal["exito", "requiere_revision"]
    anclaje_fuente_score: float = Field(ge=0, le=1)
    creado_en: Text


class ContentList(StrictModel):
    items: list[ContentSummary]
    total: int = Field(ge=0)
    limit: int
    offset: int


class Catalogs(StrictModel):
    perfiles: list[UserProfile]
    formatos: list[OutputFormat]
    extensiones_documento: list[str]
    max_upload_bytes: int
    max_documento_caracteres: int
    max_paginas_pdf: int


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    base_datos: Literal["sqlite"] = "sqlite"
