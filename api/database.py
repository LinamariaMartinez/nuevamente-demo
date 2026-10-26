"""Persistencia SQLite única para documentos, contenidos, usuarios, sesiones y temas.

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

from api.contracts import ContentRequest, DocumentSummary, Fuente
from schemas import DEFAULT_DETAIL, DEFAULT_NICHE, EducationalResponse

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def resolve_db_path(value: str | Path | None = None) -> Path:
    path = Path(value or os.getenv("NUEVAMENTE_DB_PATH", "storage/nuevamente.sqlite3"))
    return path if path.is_absolute() else ROOT / path


# Ruta activa de la base. Las pruebas pueden sustituirla con monkeypatch.
DB_PATH = resolve_db_path()

SCHEMA_VERSION = 4

CONTENIDOS_TABLE = """
    CREATE TABLE IF NOT EXISTS contenidos (
        id TEXT PRIMARY KEY,
        documento_id TEXT REFERENCES documentos(id),
        id_tema TEXT REFERENCES temas(id_tema) ON DELETE SET NULL,
        id_usuario INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
        titulo TEXT NOT NULL,
        tema TEXT NOT NULL,
        perfil_aplicado TEXT NOT NULL CHECK(perfil_aplicado IN ('Principiante', 'Intermedio', 'Avanzado')),
        formato_generado TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('exito', 'requiere_revision')),
        anclaje_fuente_score REAL NOT NULL CHECK(anclaje_fuente_score BETWEEN 0 AND 1),
        creado_en TEXT NOT NULL,
        solicitud_json TEXT NOT NULL CHECK(json_valid(solicitud_json)),
        respuesta_json TEXT NOT NULL CHECK(json_valid(respuesta_json)),
        fuentes_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(fuentes_json)),
        aprobado_en TEXT
    );
"""

TOPIC_CONFIG_COLUMNS = (
    ("nicho_sector", f"TEXT NOT NULL DEFAULT '{DEFAULT_NICHE}'"),
    ("nivel_detalle", f"TEXT NOT NULL DEFAULT '{DEFAULT_DETAIL}'"),
)

SCHEMA = f"""
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
        descripcion TEXT NOT NULL DEFAULT '',
        {", ".join(f"{name} {definition}" for name, definition in TOPIC_CONFIG_COLUMNS)}
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
    CREATE TABLE IF NOT EXISTS intentos_login (
        clave TEXT PRIMARY KEY,
        fallos INTEGER NOT NULL DEFAULT 0,
        ventana_inicio REAL NOT NULL,
        bloqueos INTEGER NOT NULL DEFAULT 0,
        bloqueado_hasta REAL NOT NULL DEFAULT 0
    );

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
    CREATE TABLE IF NOT EXISTS tema_documentos (
        id_tema TEXT NOT NULL REFERENCES temas(id_tema) ON DELETE CASCADE,
        documento_id TEXT NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
        asociado_en TEXT NOT NULL,
        PRIMARY KEY (id_tema, documento_id)
    );
"""

CONTENIDOS_SCHEMA = CONTENIDOS_TABLE + """
    CREATE INDEX IF NOT EXISTS ix_contenidos_documento ON contenidos(documento_id, creado_en DESC);
    CREATE INDEX IF NOT EXISTS ix_contenidos_fecha ON contenidos(creado_en DESC);
    CREATE INDEX IF NOT EXISTS ix_contenidos_usuario ON contenidos(id_usuario, creado_en DESC);
    CREATE INDEX IF NOT EXISTS ix_contenidos_tema ON contenidos(id_tema, creado_en DESC);
"""

# Regla única de "pendiente de revisión": la evaluó el revisor como requiere_revision y ningún admin la aprobó.
PENDING_SQL = "(status = 'requiere_revision' AND aprobado_en IS NULL)"
USER_SELECT = "SELECT id_usuario, nombre, usuario, rol, activo, debe_cambiar_contrasena FROM usuarios"


def is_pending(record: dict) -> bool:
    """Equivalente en Python de PENDING_SQL; el material pendiente no es visible para el estudiante."""
    return record["status"] == "requiere_revision" and record["aprobado_en"] is None


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


def _columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn):
    """Lleva bases v0/v1/v2 (F06 o F08 por separado, o integradas) al esquema v3.

    Todo ocurre en una sola transacción: si algo falla, la base queda como estaba.
    """
    temas = _columns(conn, "temas")
    contenidos = _columns(conn, "contenidos")
    missing_topic_columns = [(name, ddl) for name, ddl in TOPIC_CONFIG_COLUMNS if temas and name not in temas]
    rebuild_contenidos = bool(contenidos) and "id_tema" not in contenidos
    add_approval = bool(contenidos) and not rebuild_contenidos and "aprobado_en" not in contenidos
    if not (missing_topic_columns or rebuild_contenidos or add_approval):
        return
    conn.execute("BEGIN")
    for name, ddl in missing_topic_columns:
        conn.execute(f"ALTER TABLE temas ADD COLUMN {name} {ddl}")  # Nombres de una lista fija.
    if add_approval:
        conn.execute("ALTER TABLE contenidos ADD COLUMN aprobado_en TEXT")
    if rebuild_contenidos:
        # SQLite no permite quitar NOT NULL de documento_id: se reconstruye la tabla.
        conn.execute("ALTER TABLE contenidos RENAME TO contenidos_v1")
        conn.execute("DROP INDEX IF EXISTS ix_contenidos_documento")
        conn.execute("DROP INDEX IF EXISTS ix_contenidos_fecha")
        conn.execute(CONTENIDOS_TABLE)
        conn.execute(
            """INSERT INTO contenidos
            (id, documento_id, titulo, tema, perfil_aplicado, formato_generado, status,
             anclaje_fuente_score, creado_en, solicitud_json, respuesta_json)
            SELECT id, documento_id, titulo, tema, perfil_aplicado, formato_generado, status,
             anclaje_fuente_score, creado_en, solicitud_json, respuesta_json FROM contenidos_v1"""
        )
        conn.execute("DROP TABLE contenidos_v1")


def init_db(path: Path | None = None):
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError("Versión de base de datos no compatible con esta API.")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.executescript(CONTENIDOS_SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def pages_from_document(document: dict) -> list[Document]:
    """Páginas del documento etiquetadas con su id y título, para trazar las fuentes."""
    pages = []
    for page in json.loads(document["paginas_json"]):
        metadata = {**page["metadata"], "documento_id": document["id"], "documento_titulo": document["documento_titulo"]}
        pages.append(Document(page_content=page["page_content"], metadata=metadata))
    return pages


class Store:
    """Acceso a datos. Sin ruta explícita usa ``DB_PATH`` en cada operación."""

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

    # --- Documentos ---

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

    # --- Temas: configuración, documentos y estudiantes ---

    def get_topic(self, id_tema: str):
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id_tema, nombre, descripcion, nicho_sector, nivel_detalle FROM temas WHERE id_tema = ?",
                (id_tema,),
            ).fetchone()
        return dict(row) if row is not None else None

    def update_topic(self, id_tema: str, changes: dict) -> dict | None:
        allowed = {"nombre", "descripcion", "nicho_sector", "nivel_detalle"}
        changes = {key: value for key, value in changes.items() if key in allowed}
        if changes:
            assignments = ", ".join(f"{column} = ?" for column in changes)  # Columnas de la lista fija.
            with self.connection() as conn:
                conn.execute(f"UPDATE temas SET {assignments} WHERE id_tema = ?", (*changes.values(), id_tema))
        return self.get_topic(id_tema)

    def delete_topic(self, id_tema: str) -> bool:
        """Borra el tema y sus asociaciones; el historial de contenidos se conserva sin tema (SET NULL)."""
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM temas WHERE id_tema = ?", (id_tema,))
        return cursor.rowcount == 1

    def is_assigned(self, id_usuario: int, id_tema: str) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM usuario_temas WHERE id_usuario = ? AND id_tema = ?", (id_usuario, id_tema),
            ).fetchone()
        return row is not None

    def link_document(self, id_tema: str, documento_id: str) -> bool:
        """Devuelve False si la asociación ya existía."""
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO tema_documentos (id_tema, documento_id, asociado_en) VALUES (?, ?, ?)",
                (id_tema, documento_id, utc_now()),
            )
        return cursor.rowcount == 1

    def unlink_document(self, id_tema: str, documento_id: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM tema_documentos WHERE id_tema = ? AND documento_id = ?", (id_tema, documento_id),
            )
        return cursor.rowcount == 1

    def list_topic_documents(self, id_tema: str) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT d.id, d.documento_titulo, d.nombre_archivo, d.tipo, d.tamano_bytes,
                d.fragmentos_extraidos, d.creado_en
                FROM tema_documentos td JOIN documentos d ON d.id = td.documento_id
                WHERE td.id_tema = ? ORDER BY td.asociado_en, d.id""", (id_tema,),
            ).fetchall()
        return [dict(row) for row in rows]

    def topic_pages(self, id_tema: str) -> list[Document]:
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT d.id, d.documento_titulo, d.paginas_json
                FROM tema_documentos td JOIN documentos d ON d.id = td.documento_id
                WHERE td.id_tema = ? ORDER BY td.asociado_en, d.id""", (id_tema,),
            ).fetchall()
        return [page for row in rows for page in pages_from_document(dict(row))]

    def get_user(self, id_usuario: int):
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id_usuario, nombre, usuario, rol, activo FROM usuarios WHERE id_usuario = ?", (id_usuario,),
            ).fetchone()
        return dict(row) if row is not None else None

    def assign_student(self, id_usuario: int, id_tema: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO usuario_temas (id_usuario, id_tema) VALUES (?, ?)", (id_usuario, id_tema),
            )
        return cursor.rowcount == 1

    def unassign_student(self, id_usuario: int, id_tema: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM usuario_temas WHERE id_usuario = ? AND id_tema = ?", (id_usuario, id_tema),
            )
        return cursor.rowcount == 1

    def list_topic_students(self, id_tema: str) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT u.id_usuario, u.nombre, u.usuario, u.activo
                FROM usuario_temas ut JOIN usuarios u ON u.id_usuario = ut.id_usuario
                WHERE ut.id_tema = ? ORDER BY u.nombre""", (id_tema,),
            ).fetchall()
        return [{**dict(row), "activo": bool(row["activo"])} for row in rows]

    def create_topic(self, topic: dict, documentos: list[str]) -> None:
        """Crea el tema y sus documentos en una transacción; IntegrityError si el id ya existe."""
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO temas (id_tema, nombre, descripcion, nicho_sector, nivel_detalle)
                VALUES (:id_tema, :nombre, :descripcion, :nicho_sector, :nivel_detalle)""",
                topic,
            )
            conn.executemany(
                "INSERT INTO tema_documentos (id_tema, documento_id, asociado_en) VALUES (?, ?, ?)",
                [(topic["id_tema"], documento_id, utc_now()) for documento_id in documentos],
            )

    def list_topics_for(self, user: dict) -> list[dict]:
        """Todos los temas para un admin; solo los asignados para un estudiante."""
        columns = "t.id_tema, t.nombre, t.descripcion, t.nicho_sector, t.nivel_detalle"
        sql = f"SELECT {columns} FROM temas t"
        params: tuple = ()
        if user["rol"] != "admin":
            sql += " JOIN usuario_temas ut ON ut.id_tema = t.id_tema WHERE ut.id_usuario = ?"
            params = (user["id_usuario"],)
        with self.connection() as conn:
            rows = conn.execute(f"{sql} ORDER BY t.nombre", params).fetchall()
        return [dict(row) for row in rows]

    def topic_ids_by_user(self) -> dict[int, list[str]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT id_usuario, id_tema FROM usuario_temas ORDER BY id_tema").fetchall()
        result: dict[int, list[str]] = {}
        for row in rows:
            result.setdefault(row["id_usuario"], []).append(row["id_tema"])
        return result

    # --- Usuarios ---

    def list_users(self) -> list[dict]:
        topics = self.topic_ids_by_user()
        with self.connection() as conn:
            rows = conn.execute(f"{USER_SELECT} ORDER BY nombre").fetchall()
        return [self._user_view(row, topics.get(row["id_usuario"], [])) for row in rows]

    def update_student(self, id_usuario: int, changes: dict) -> dict | None:
        """Aplica los cambios en un solo UPDATE; desactivar o resetear la clave revoca sus sesiones."""
        columns: dict = {}
        if "nombre" in changes:
            columns["nombre"] = changes["nombre"]
        if "activo" in changes:
            columns["activo"] = int(changes["activo"])
        if "contrasena_hash" in changes:
            columns.update(contrasena_hash=changes["contrasena_hash"], debe_cambiar_contrasena=1)
        assignments = ", ".join(f"{column} = ?" for column in columns)  # Columnas fijas, no del cliente.
        with self.connection() as conn:
            cursor = conn.execute(
                f"UPDATE usuarios SET {assignments} WHERE id_usuario = ? AND rol = 'estudiante'",
                (*columns.values(), id_usuario),
            )
            if cursor.rowcount != 1:
                return None
            if changes.get("activo") is False or "contrasena_hash" in changes:
                conn.execute("DELETE FROM sesiones WHERE id_usuario = ?", (id_usuario,))
            row = conn.execute(f"{USER_SELECT} WHERE id_usuario = ?", (id_usuario,)).fetchone()
        return self._user_view(row, self.topic_ids_by_user().get(id_usuario, []))

    @staticmethod
    def _user_view(row, temas: list[str]) -> dict:
        return {
            **dict(row), "activo": bool(row["activo"]),
            "debe_cambiar_contrasena": bool(row["debe_cambiar_contrasena"]), "temas": temas,
        }

    # --- Contenidos ---

    def save_content(
        self, request: ContentRequest, response: EducationalResponse, *,
        id_usuario: int | None = None, fuentes: list[Fuente] | None = None,
    ) -> tuple[str, str]:
        identifier, created = uuid4().hex, utc_now()
        fuentes_json = json.dumps([f.model_dump(mode="json") for f in fuentes or []], ensure_ascii=False)
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO contenidos
                (id, documento_id, id_tema, id_usuario, titulo, tema, perfil_aplicado, formato_generado, status,
                 anclaje_fuente_score, creado_en, solicitud_json, respuesta_json, fuentes_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    identifier, request.documento_id, request.id_tema, id_usuario,
                    response.contenido_adaptado.titulo, request.tema, response.metadatos.perfil_aplicado,
                    response.metadatos.formato_generado, response.status,
                    response.evaluacion_calidad.anclaje_fuente_score, created,
                    request.model_dump_json(), response.model_dump_json(), fuentes_json,
                ),
            )
        return identifier, created

    def list_contents(
        self, limit: int, offset: int, *, documento_id=None, perfil=None, status=None, id_tema=None, id_usuario=None,
        pendiente: bool | None = None,
    ) -> dict:
        filters, params = [], []
        for column, value in (
            ("documento_id", documento_id), ("perfil_aplicado", perfil), ("status", status),
            ("id_tema", id_tema), ("id_usuario", id_usuario),
        ):
            if value is not None:
                filters.append(f"{column} = ?")  # Los nombres vienen de esta lista fija.
                params.append(value)
        if pendiente is not None:
            filters.append(PENDING_SQL if pendiente else f"NOT {PENDING_SQL}")
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection() as conn:
            total = conn.execute("SELECT count(*) FROM contenidos" + where, params).fetchone()[0]
            rows = conn.execute(
                """SELECT id, documento_id, id_tema, id_usuario, titulo, tema, perfil_aplicado, formato_generado,
                status, anclaje_fuente_score, creado_en, aprobado_en FROM contenidos"""
                + where + " ORDER BY creado_en DESC, id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def approve_content(self, identifier: str) -> None:
        with self.connection() as conn:
            conn.execute("UPDATE contenidos SET aprobado_en = ? WHERE id = ?", (utc_now(), identifier))

    def delete_content(self, identifier: str) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM contenidos WHERE id = ?", (identifier,))

    def get_content(self, identifier: str) -> dict | None:
        """Registro con la respuesta educativa y sus metadatos de trazabilidad."""
        with self.connection() as conn:
            row = conn.execute(
                """SELECT id, id_tema, id_usuario, tema, status, creado_en, aprobado_en, respuesta_json, fuentes_json
                FROM contenidos WHERE id = ?""", (identifier,),
            ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["respuesta"] = EducationalResponse.model_validate_json(record.pop("respuesta_json"))
        record["fuentes"] = [Fuente.model_validate(item) for item in json.loads(record.pop("fuentes_json"))]
        return record
