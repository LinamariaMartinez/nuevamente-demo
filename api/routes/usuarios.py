
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import hash_password, require_password_updated
from api.database import get_connection


router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


class CrearEstudianteRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    usuario: str = Field(min_length=1, max_length=100)
    contrasena_temporal: str = Field(min_length=12)
    temas: list[str] = Field(default_factory=list)


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_estudiante(
    data: CrearEstudianteRequest,
  user: dict = Depends(require_password_updated)
):
    if user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede crear usuarios",
        )

    temas = list(dict.fromkeys(data.temas))

    try:
        with get_connection() as connection:
            for id_tema in temas:
                existe = connection.execute(
                    "SELECT 1 FROM temas WHERE id_tema = ?",
                    (id_tema,),
                ).fetchone()

                if existe is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No existe el tema: {id_tema}",
                    )

            cursor = connection.execute(
                """
                INSERT INTO usuarios (
                    nombre,
                    usuario,
                    contrasena_hash,
                    rol,
                    activo,
                    debe_cambiar_contrasena
                )
                VALUES (?, ?, ?, 'estudiante', 1, 1)
                """,
                (
                    data.nombre.strip(),
                    data.usuario.strip(),
                    hash_password(data.contrasena_temporal),
                ),
            )

            id_usuario = cursor.lastrowid

            for id_tema in temas:
                connection.execute(
                    """
                    INSERT INTO usuario_temas (id_usuario, id_tema)
                    VALUES (?, ?)
                    """,
                    (id_usuario, id_tema),
                )

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya existe o hay datos duplicados",
        )

    return {
        "id_usuario": id_usuario,
        "nombre": data.nombre.strip(),
        "usuario": data.usuario.strip(),
        "rol": "estudiante",
        "activo": True,
        "debe_cambiar_contrasena": True,
        "temas": temas,
    }
