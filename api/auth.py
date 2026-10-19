
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from pwdlib import PasswordHash

from api.database import get_connection


password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)

SESSION_HOURS = 8


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


@lru_cache(maxsize=1)
def dummy_hash() -> str:
    return password_hash.hash(secrets.token_urlsafe(16))


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    ).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sesiones (
                token_hash, id_usuario, expires_at
            )
            VALUES (?, ?, ?)
            """,
            (token_hash, user_id, expires_at),
        )

    return token


def get_session_user(token: str):
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT u.*
            FROM sesiones s
            JOIN usuarios u ON u.id_usuario = s.id_usuario
            WHERE s.token_hash = ?
              AND s.expires_at > ?
              AND u.activo = 1
            """,
            (token_hash, datetime.now(timezone.utc).isoformat()),
        ).fetchone()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
        )

    return dict(user)


from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere iniciar sesión",
        )

    return get_session_user(credentials.credentials)


def require_password_updated(
    user: dict = Depends(require_user),
):
    if user["debe_cambiar_contrasena"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes cambiar tu contraseña temporal antes de continuar",
        )

    return user



def revoke_session(token: str):
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    with get_connection() as connection:
        connection.execute(
            "DELETE FROM sesiones WHERE token_hash = ?",
            (token_hash,),
        )
