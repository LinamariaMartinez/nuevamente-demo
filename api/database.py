
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "nuevamente.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_connection() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                usuario TEXT NOT NULL UNIQUE,
                contrasena_hash TEXT NOT NULL,
                rol TEXT NOT NULL CHECK (
                    rol IN ('admin', 'estudiante')
                ),
                activo INTEGER NOT NULL DEFAULT 1,
                debe_cambiar_contrasena INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS temas (
                id_tema TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS usuario_temas (
                id_usuario INTEGER NOT NULL,
                id_tema TEXT NOT NULL,
                PRIMARY KEY (id_usuario, id_tema),
                FOREIGN KEY (id_usuario)
                    REFERENCES usuarios(id_usuario)
                    ON DELETE CASCADE,
                FOREIGN KEY (id_tema)
                    REFERENCES temas(id_tema)
                    ON DELETE CASCADE
            );

           CREATE TABLE IF NOT EXISTS sesiones (
               token_hash TEXT PRIMARY KEY,
               id_usuario INTEGER NOT NULL,
               expires_at TEXT NOT NULL,
               FOREIGN KEY (id_usuario)
                   REFERENCES usuarios(id_usuario)
                   ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sesiones_usuario
            ON sesiones(id_usuario);


        """)
