
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from api.auth import require_password_updated
from api.database import Store
from api.dependencies import get_store
from api.errors import ApiError
from schemas import DEFAULT_DETAIL, DEFAULT_NICHE


router = APIRouter(prefix="/api/v1/temas", tags=["Temas"])


class CrearTemaRequest(BaseModel):
    # Recorta antes de validar: "   " no pasa min_length=1.
    model_config = ConfigDict(str_strip_whitespace=True)

    id_tema: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: str = Field(default="", max_length=1000)
    nicho_sector: str = Field(default=DEFAULT_NICHE, min_length=1, max_length=200)
    nivel_detalle: str = Field(default=DEFAULT_DETAIL, min_length=1, max_length=200)
    documentos: list[str] = Field(default_factory=list, max_length=50)


@router.get("")
def listar_temas(user: dict = Depends(require_password_updated), db: Store = Depends(get_store)):
    return db.list_topics_for(user)


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_tema(
    data: CrearTemaRequest,
    user: dict = Depends(require_password_updated),
    db: Store = Depends(get_store),
):
    if user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden crear temas",
        )

    documentos = list(dict.fromkeys(data.documentos))
    for documento_id in documentos:
        if db.get_document(documento_id) is None:
            raise ApiError(404, "DOCUMENTO_NO_ENCONTRADO", f"No existe el documento: {documento_id}")

    try:
        db.create_topic(data.model_dump(exclude={"documentos"}), documentos)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un tema con ese identificador",
        )

    return {**data.model_dump(), "documentos": documentos}
