"""Dependencias compartidas por la app y los routers."""

from fastapi import Depends, Request

from api.auth import require_password_updated
from api.database import Store
from api.errors import ApiError


def get_store(request: Request) -> Store:
    return request.app.state.store


def is_admin(user: dict) -> bool:
    return user["rol"] == "admin"


def require_admin(user: dict = Depends(require_password_updated)) -> dict:
    if not is_admin(user):
        raise ApiError(403, "PERMISOS_INSUFICIENTES", "Solo un administrador puede realizar esta acción.")
    return user


def require_document(store: Store, documento_id: str) -> dict:
    document = store.get_document(documento_id)
    if document is None:
        raise ApiError(404, "DOCUMENTO_NO_ENCONTRADO", "No existe el documento solicitado.")
    return document


def require_topic(store: Store, id_tema: str) -> dict:
    topic = store.get_topic(id_tema)
    if topic is None:
        raise ApiError(404, "TEMA_NO_ENCONTRADO", "No existe el tema solicitado.")
    return topic


def require_topic_access(store: Store, user: dict, id_tema: str) -> dict:
    """Admin accede a cualquier tema; un estudiante solo a los asignados."""
    topic = require_topic(store, id_tema)
    if not is_admin(user) and not store.is_assigned(user["id_usuario"], id_tema):
        raise ApiError(403, "TEMA_NO_ASIGNADO", "No tienes asignado este tema.")
    return topic
