"""Persistencia SQLite: conexiones cortas por operación, sin compartirlas entre hilos."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from langchain_core.documents import Document

from api.contracts import ContentRequest, DocumentSummary
from schemas import EducationalResponse


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError("Versión de base de datos no compatible con esta API.")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documentos (
                    id TEXT PRIMARY KEY,
                    documento_titulo TEXT NOT NULL,
                    nombre_archivo TEXT NOT NULL,
                    tipo TEXT NOT NULL CHECK(tipo IN ('pdf', 'md', 'txt')),
                    tamano_bytes INTEGER NOT NULL CHECK(tamano_bytes > 0),
                    fragmentos_extraidos INTEGER NOT NULL CHECK(fragmentos_extraidos > 0),
                    creado_en TEXT NOT NULL,
                    original BLOB NOT NULL,
                    paginas_json TEXT NOT NULL CHECK(json_valid(paginas_json))
                );
                CREATE TABLE IF NOT EXISTS contenidos (
                    id TEXT PRIMARY KEY,
                    documento_id TEXT NOT NULL REFERENCES documentos(id),
                    titulo TEXT NOT NULL,
                    tema TEXT NOT NULL,
                    perfil_aplicado TEXT NOT NULL CHECK(perfil_aplicado IN ('Principiante', 'Intermedio', 'Avanzado')),
                    formato_generado TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('exito', 'requiere_revision')),
                    anclaje_fuente_score REAL NOT NULL CHECK(anclaje_fuente_score BETWEEN 0 AND 1),
                    creado_en TEXT NOT NULL,
                    solicitud_json TEXT NOT NULL CHECK(json_valid(solicitud_json)),
                    respuesta_json TEXT NOT NULL CHECK(json_valid(respuesta_json))
                );
                CREATE INDEX IF NOT EXISTS ix_contenidos_documento ON contenidos(documento_id, creado_en DESC);
                CREATE INDEX IF NOT EXISTS ix_contenidos_fecha ON contenidos(creado_en DESC);
                PRAGMA user_version = 1;
            """)

    def ping(self):
        with self.connection() as conn:
            conn.execute("SELECT count(*) FROM documentos").fetchone()

    def create_document(self, title: str, filename: str, kind: str, raw: bytes, documents: list[Document]) -> DocumentSummary:
        summary = DocumentSummary(
            id=uuid4().hex, documento_titulo=title, nombre_archivo=filename, tipo=kind,
            tamano_bytes=len(raw), fragmentos_extraidos=len(documents), creado_en=utc_now(),
        )
        pages = [{"page_content": d.page_content, "metadata": d.metadata} for d in documents]
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO documentos
                (id, documento_titulo, nombre_archivo, tipo, tamano_bytes, fragmentos_extraidos, creado_en, original, paginas_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (summary.id, summary.documento_titulo, summary.nombre_archivo, summary.tipo,
                 summary.tamano_bytes, summary.fragmentos_extraidos, summary.creado_en,
                 raw, json.dumps(pages, ensure_ascii=False)),
            )
        return summary

    def list_documents(self, limit: int, offset: int) -> dict:
        with self.connection() as conn:
            total = conn.execute("SELECT count(*) FROM documentos").fetchone()[0]
            rows = conn.execute(
                """SELECT id, documento_titulo, nombre_archivo, tipo, tamano_bytes, fragmentos_extraidos, creado_en
                FROM documentos ORDER BY creado_en DESC, id DESC LIMIT ? OFFSET ?""", (limit, offset),
            ).fetchall()
        return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def get_document(self, identifier: str):
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM documentos WHERE id = ?", (identifier,)).fetchone()
        return dict(row) if row is not None else None

    def save_content(self, request: ContentRequest, response: EducationalResponse) -> str:
        identifier = uuid4().hex
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO contenidos
                (id, documento_id, titulo, tema, perfil_aplicado, formato_generado, status,
                 anclaje_fuente_score, creado_en, solicitud_json, respuesta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    identifier, request.documento_id, response.contenido_adaptado.titulo,
                    request.tema, response.metadatos.perfil_aplicado, response.metadatos.formato_generado,
                    response.status, response.evaluacion_calidad.anclaje_fuente_score, utc_now(),
                    request.model_dump_json(), response.model_dump_json(),
                ),
            )
        return identifier

    def list_contents(self, limit: int, offset: int, *, documento_id=None, perfil=None, status=None) -> dict:
        filters, params = [], []
        for column, value in (("documento_id", documento_id), ("perfil_aplicado", perfil), ("status", status)):
            if value is not None:
                filters.append(f"{column} = ?")  # Los nombres vienen de esta lista fija.
                params.append(value)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection() as conn:
            total = conn.execute("SELECT count(*) FROM contenidos" + where, params).fetchone()[0]
            rows = conn.execute(
                """SELECT id, documento_id, titulo, tema, perfil_aplicado, formato_generado,
                status, anclaje_fuente_score, creado_en FROM contenidos"""
                + where + " ORDER BY creado_en DESC, id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def get_content(self, identifier: str) -> EducationalResponse | None:
        with self.connection() as conn:
            row = conn.execute("SELECT respuesta_json FROM contenidos WHERE id = ?", (identifier,)).fetchone()
        return EducationalResponse.model_validate_json(row[0]) if row is not None else None
