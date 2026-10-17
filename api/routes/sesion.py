
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import create_session, verify_password
from api.database import get_connection


router = APIRouter(tags=["Sesión"])


class LoginRequest(BaseModel):
    usuario: str = Field(min_length=1)
    contrasena: str = Field(min_length=1)


@router.post("/sesion")
def iniciar_sesion(data: LoginRequest):
    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT *
            FROM usuarios
            WHERE usuario = ? AND activo = 1
            """,
            (data.usuario,),
        ).fetchone()

    if user is None or not verify_password(
        data.contrasena, user["contrasena_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    token = create_session(user["id_usuario"])

    return {
        "token": token,
        "usuario": {
            "id_usuario": user["id_usuario"],
            "nombre": user["nombre"],
            "usuario": user["usuario"],
            "rol": user["rol"],
            "debe_cambiar_contrasena": bool(
                user["debe_cambiar_contrasena"]
            ),
        },
    }

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import bearer_scheme, require_user, revoke_session


@router.delete("/sesion")
def cerrar_sesion(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user: dict = Depends(require_user),
):
    revoke_session(credentials.credentials)

    return {"mensaje": "Sesión cerrada correctamente"}

from fastapi import Depends

from api.auth import hash_password, require_user


class CambiarContrasenaRequest(BaseModel):
    contrasena_actual: str = Field(min_length=1)
    contrasena_nueva: str = Field(min_length=12)


@router.put("/sesion/contrasena")
def cambiar_contrasena(
    data: CambiarContrasenaRequest,
    user: dict = Depends(require_user),
):
    if not verify_password(
        data.contrasena_actual,
        user["contrasena_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta",
        )

    if data.contrasena_actual == data.contrasena_nueva:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser diferente",
        )

    nuevo_hash = hash_password(data.contrasena_nueva)

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE usuarios
            SET contrasena_hash = ?,
                debe_cambiar_contrasena = 0
            WHERE id_usuario = ?
            """,
            (nuevo_hash, user["id_usuario"]),
        )

        connection.execute(
            """
            DELETE FROM sesiones
            WHERE id_usuario = ?
            """,
            (user["id_usuario"],),
        )

    return {
        "mensaje": "Contraseña actualizada correctamente",
        "sesiones_revocadas": True,
    }
