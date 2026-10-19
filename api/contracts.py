"""Contrato HTTP propuesto; no sustituye el src/contrato.py del equipo frontend."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from schemas import EducationalResponse, OutputFormat, StrictModel, Text, UserProfile

Identifier = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
TopicId = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")]
MAX_DOCUMENT_CHARACTERS = 250_000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100


class TextDocumentRequest(StrictModel):
    documento_titulo: Text = Field(max_length=200)
    documento_contenido: Text = Field(min_length=11, max_length=MAX_DOCUMENT_CHARACTERS)


class ContentRequest(StrictModel):
    """Solicitud de generación. Con ``id_tema`` el nicho y el nivel salen de la configuración del tema."""

    tema: Text | None = Field(
        default=None, max_length=2000,
        description="Consulta o subtema a desarrollar. Si se omite con id_tema, se usa el nombre del tema completo.",
    )
    perfil_destinatario: UserProfile
    formato_salida: OutputFormat
    id_tema: TopicId | None = Field(default=None, description="Tema asignado; fuente recomendada.")
    documento_id: Identifier | None = Field(default=None, description="Solo administradores: generar desde un documento.")
    nicho_sector: Text | None = Field(default=None, max_length=200, description="Solo con documento_id.")
    nivel_detalle: Text | None = Field(default=None, max_length=200, description="Solo con documento_id.")

    @field_validator("tema", mode="before")
    @classmethod
    def blank_tema_is_omitted(cls, value):
        """Un tema vacío equivale a no enviarlo."""
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def check_source(self):
        if (self.id_tema is None) == (self.documento_id is None):
            raise ValueError("Indica exactamente uno de id_tema o documento_id.")
        if self.documento_id is not None and self.tema is None:
            raise ValueError("Con documento_id, indica el tema a desarrollar.")
        if self.id_tema is not None and (self.nicho_sector is not None or self.nivel_detalle is not None):
            raise ValueError("Con id_tema, el nicho y el nivel de detalle se configuran en el tema.")
        return self


class Fuente(StrictModel):
    documento_id: Identifier
    documento: Text = Field(description="Título del documento de origen.")
    fragmento: int = Field(ge=1, description="Posición del fragmento entre los recuperados.")
    pagina: int | None = Field(default=None, ge=1)
    extracto: Text


class ContentResponse(EducationalResponse):
    id: Identifier
    creado_en: Text = Field(description="Fecha ISO 8601 en UTC.")
    id_tema: TopicId | None = None
    aprobado_en: Text | None = Field(default=None, description="Fecha de aprobación manual por un administrador.")
    fuentes: list[Fuente]


class PendingReviewResponse(StrictModel):
    id: Identifier
    creado_en: Text
    status: Literal["requiere_revision"] = "requiere_revision"
    mensaje: Text = "El material quedó pendiente de revisión por un administrador."


class TopicDetail(StrictModel):
    id_tema: TopicId
    nombre: Text
    descripcion: str
    nicho_sector: Text
    nivel_detalle: Text


class TopicUpdate(StrictModel):
    nombre: Text | None = Field(default=None, max_length=150)
    descripcion: str | None = Field(default=None, max_length=1000)
    nicho_sector: Text | None = Field(default=None, max_length=200)
    nivel_detalle: Text | None = Field(default=None, max_length=200)


class TopicStudent(StrictModel):
    id_usuario: int
    nombre: Text
    usuario: Text
    activo: bool


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
    documento_id: Identifier | None
    id_tema: TopicId | None
    id_usuario: int | None
    titulo: Text
    tema: Text
    perfil_aplicado: UserProfile
    formato_generado: OutputFormat
    status: Literal["exito", "requiere_revision"]
    anclaje_fuente_score: float = Field(ge=0, le=1)
    creado_en: Text
    aprobado_en: Text | None = None


class ContentList(StrictModel):
    items: list[ContentSummary]
    total: int = Field(ge=0)
    limit: int
    offset: int


class Catalogs(StrictModel):
    perfiles: list[UserProfile]
    formatos: list[OutputFormat]
    sectores: list[str]
    extensiones_documento: list[str]
    max_upload_bytes: int
    max_documento_caracteres: int
    max_paginas_pdf: int


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    base_datos: Literal["sqlite"] = "sqlite"
