
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import require_password_updated
from api.database import get_connection


router = APIRouter(prefix="/temas", tags=["Temas"])


class CrearTemaRequest(BaseModel):
    id_tema: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: str = Field(default="", max_length=1000)


@router.get("")
def listar_temas(user: dict = Depends(require_password_updated)):
    with get_connection() as connection:
        if user["rol"] == "admin":
            rows = connection.execute(
                """
                SELECT id_tema, nombre, descripcion
                FROM temas
                ORDER BY nombre
                """
            ).fetchall()

        elif user["rol"] == "estudiante":
            rows = connection.execute(
                """
                SELECT t.id_tema, t.nombre, t.descripcion
                FROM temas t
                JOIN usuario_temas ut
                    ON ut.id_tema = t.id_tema
                WHERE ut.id_usuario = ?
                ORDER BY t.nombre
                """,
                (user["id_usuario"],),
            ).fetchall()

        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rol no autorizado",
            )

    return [dict(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_tema(
    data: CrearTemaRequest,
user: dict = Depends(require_password_updated)
):
    if user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden crear temas",
        )

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO temas (
                    id_tema, nombre, descripcion
                )
                VALUES (?, ?, ?)
                """,
                (
                    data.id_tema,
                    data.nombre.strip(),
                    data.descripcion.strip(),
                ),
            )

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un tema con ese identificador",
        )

    return {
        "id_tema": data.id_tema,
        "nombre": data.nombre.strip(),
        "descripcion": data.descripcion.strip(),
    }
