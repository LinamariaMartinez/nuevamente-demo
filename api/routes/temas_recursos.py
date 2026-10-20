"""Configuración de temas, documentos asociados y estudiantes asignados."""

from fastapi import APIRouter, Depends, Response

from api.auth import require_password_updated
from api.contracts import DocumentSummary, Identifier, TopicDetail, TopicId, TopicStudent, TopicUpdate
from api.database import Store
from api.dependencies import get_store, require_admin, require_document, require_topic, require_topic_access
from api.errors import ApiError

router = APIRouter(prefix="/api/v1/temas", tags=["Temas"])


@router.get("/{id_tema}", response_model=TopicDetail)
def get_topic(id_tema: TopicId, user: dict = Depends(require_password_updated), db: Store = Depends(get_store)):
    return require_topic_access(db, user, id_tema)


@router.patch("/{id_tema}", response_model=TopicDetail)
def update_topic(id_tema: TopicId, body: TopicUpdate, _: dict = Depends(require_admin), db: Store = Depends(get_store)):
    require_topic(db, id_tema)
    return db.update_topic(id_tema, body.model_dump(exclude_none=True))


@router.delete("/{id_tema}", status_code=204, response_class=Response)
def delete_topic(id_tema: TopicId, _: dict = Depends(require_admin), db: Store = Depends(get_store)):
    require_topic(db, id_tema)
    db.delete_topic(id_tema)
    return Response(status_code=204)


@router.get("/{id_tema}/documentos", response_model=list[DocumentSummary])
def list_topic_documents(id_tema: TopicId, user: dict = Depends(require_password_updated), db: Store = Depends(get_store)):
    require_topic_access(db, user, id_tema)
    return db.list_topic_documents(id_tema)


@router.put("/{id_tema}/documentos/{documento_id}", status_code=204, response_class=Response)
def link_document(id_tema: TopicId, documento_id: Identifier, _: dict = Depends(require_admin), db: Store = Depends(get_store)):
    require_topic(db, id_tema)
    require_document(db, documento_id)
    db.link_document(id_tema, documento_id)
    return Response(status_code=204)


@router.delete("/{id_tema}/documentos/{documento_id}", status_code=204, response_class=Response)
def unlink_document(id_tema: TopicId, documento_id: Identifier, _: dict = Depends(require_admin), db: Store = Depends(get_store)):
    require_topic(db, id_tema)
    if not db.unlink_document(id_tema, documento_id):
        raise ApiError(404, "ASOCIACION_NO_ENCONTRADA", "El documento no está asociado a este tema.")
    return Response(status_code=204)


@router.get("/{id_tema}/estudiantes", response_model=list[TopicStudent])
def list_topic_students(id_tema: TopicId, _: dict = Depends(require_admin), db: Store = Depends(get_store)):
    require_topic(db, id_tema)
    return db.list_topic_students(id_tema)


@router.put("/{id_tema}/estudiantes/{id_usuario}", status_code=204, response_class=Response)
def assign_student(id_tema: TopicId, id_usuario: int, _: dict = Depends(require_admin), db: Store = Depends(get_store)):
    require_topic(db, id_tema)
    student = db.get_user(id_usuario)
    if student is None or student["rol"] != "estudiante":
        raise ApiError(404, "ESTUDIANTE_NO_ENCONTRADO", "No existe un estudiante con ese identificador.")
    db.assign_student(id_usuario, id_tema)
    return Response(status_code=204)


@router.delete("/{id_tema}/estudiantes/{id_usuario}", status_code=204, response_class=Response)
def unassign_student(id_tema: TopicId, id_usuario: int, _: dict = Depends(require_admin), db: Store = Depends(get_store)):
    require_topic(db, id_tema)
    if not db.unassign_student(id_usuario, id_tema):
        raise ApiError(404, "ASIGNACION_NO_ENCONTRADA", "El estudiante no tiene asignado este tema.")
    return Response(status_code=204)
