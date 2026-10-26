
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from api.auth import bearer_scheme, create_session, dummy_hash, hash_password, require_user, revoke_session, verify_password
from api.database import Store, get_connection
from api.dependencies import get_store
from api.login_throttle import LoginThrottle, client_ip, get_throttle


router = APIRouter(prefix="/api/v1/sesion", tags=["Sesión"])


class LoginRequest(BaseModel):
    usuario: str = Field(min_length=1)
    contrasena: str = Field(min_length=1)


@router.post("")
def iniciar_sesion(
    data: LoginRequest,
    request: Request,
    db: Store = Depends(get_store),
    throttle: LoginThrottle = Depends(get_throttle),
):
    ip = client_ip(request)
    throttle.check(data.usuario, ip)

    with db.connection() as connection:
        user = connection.execute(
            """
            SELECT *
            FROM usuarios
            WHERE usuario = ? AND activo = 1
            """,
            (data.usuario,),
        ).fetchone()

    # Con usuario inexistente se verifica igual un hash falso, para no revelar por tiempo qué usuarios existen.
    if not verify_password(data.contrasena, user["contrasena_hash"] if user else dummy_hash()) or user is None:
        throttle.fail(data.usuario, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    throttle.succeed(data.usuario, ip)
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


@router.get("")
def sesion_actual(user: dict = Depends(require_user), db: Store = Depends(get_store)):
    """Quién soy: permite al frontend restaurar la sesión al recargar la página."""
    temas = [topic["id_tema"] for topic in db.list_topics_for(user)]

    return {
        "id_usuario": user["id_usuario"],
        "nombre": user["nombre"],
        "usuario": user["usuario"],
        "rol": user["rol"],
        "debe_cambiar_contrasena": bool(user["debe_cambiar_contrasena"]),
        "temas": sorted(temas),
    }


@router.delete("")
def cerrar_sesion(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user: dict = Depends(require_user),
):
    revoke_session(credentials.credentials)

    return {"mensaje": "Sesión cerrada correctamente"}


class CambiarContrasenaRequest(BaseModel):
    contrasena_actual: str = Field(min_length=1)
    contrasena_nueva: str = Field(min_length=12)


@router.put("/contrasena")
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
