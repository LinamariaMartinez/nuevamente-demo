"""Persistencia SQLite única para F06 (documentos/contenidos) y F08 (usuarios/sesiones/temas).

Conexiones cortas por operación, sin compartirlas entre hilos ni mantenerlas
abiertas durante llamadas al LLM.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.documents import Document

from api.contracts import ContentRequest, DocumentSummary
from schemas import EducationalResponse

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def resolve_db_path(value: str | Path | None = None) -> Path:
    path = Path(value or os.getenv("NUEVAMENTE_DB_PATH", "storage/nuevamente.sqlite3"))
    return path if path.is_absolute() else ROOT / path


# Ruta activa de la base. Las pruebas pueden sustituirla con monkeypatch.
DB_PATH = resolve_db_path()

SCHEMA = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        usuario TEXT NOT NULL UNIQUE,
        contrasena_hash TEXT NOT NULL,
        rol TEXT NOT NULL CHECK (rol IN ('admin', 'estudiante')),
        activo INTEGER NOT NULL DEFAULT 1,
        debe_cambiar_contrasena INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS temas (
        id_tema TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        descripcion TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS usuario_temas (
        id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
        id_tema TEXT NOT NULL REFERENCES temas(id_tema) ON DELETE CASCADE,
        PRIMARY KEY (id_usuario, id_tema)
    );
    CREATE TABLE IF NOT EXISTS sesiones (
        token_hash TEXT PRIMARY KEY,
        id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
        expires_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_sesiones_usuario ON sesiones(id_usuario);

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
"""
SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(path: Path | None = None):
    connection = sqlite3.connect(path or DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def get_connection():
    """Conexión con commit/rollback automático y cierre garantizado (uso: ``with get_connection() as c``)."""
    return connect()


def init_db(path: Path | None = None):
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError("Versión de base de datos no compatible con esta API.")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


class Store:
    """Acceso a documentos y contenidos. Sin ruta explícita usa ``DB_PATH``."""

    def __init__(self, path: Path | None = None):
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or DB_PATH

    def connection(self):
        return connect(self.path)

    def initialize(self):
        init_db(self.path)

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
