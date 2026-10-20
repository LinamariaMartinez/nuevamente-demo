"""Contrato de F07: la forma de los datos que viajan entre la interfaz (app/) y la API (api/).

Lo usan los dos lados. Se cambia solo de común acuerdo; si cambia, los ejemplos de
app/mocks/ se actualizan en el mismo PR.
"""

import re
import secrets
import unicodedata
from datetime import datetime
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

# --- Listas fijas: las mismas para el formulario y para la validación de la API ---
# Perfiles: los tres niveles que reconoce el Redactor (src/agents/writer_examples.py)
PERFILES = ("Principiante", "Intermedio", "Avanzado")
FORMATOS = ("Tutorial", "Flashcards", "Quiz", "Resumen", "Guion")
NICHOS = ("Fintech", "Salud", "E-commerce", "General")
LARGO_MAXIMO_TEMA = 300


# --- Items: su forma cambia según el formato (la de F06, que produce el Redactor) ---
class ItemFlashcard(BaseModel):
    frente: str
    dorso: str
    pista_didactica: str


class ItemQuiz(BaseModel):
    pregunta: str
    opciones: list[str] = Field(min_length=2)
    respuesta_correcta: str  # el texto exacto de una de las opciones
    justificacion: str

    @model_validator(mode="after")
    def opciones_coherentes(self):
        if len(set(self.opciones)) != len(self.opciones):
            raise ValueError("las opciones no pueden repetirse")
        if self.respuesta_correcta not in self.opciones:
            raise ValueError("respuesta_correcta no es ninguna de las opciones")
        return self


class ItemPaso(BaseModel):
    # El número del paso es su orden en la lista, desde 1
    titulo: str
    instrucciones: str


class ItemResumen(BaseModel):
    subtitulo: str
    texto: str


class ItemEscena(BaseModel):
    titulo: str
    narracion: str


MODELO_ITEM = {
    "Flashcards": ItemFlashcard,
    "Quiz": ItemQuiz,
    "Tutorial": ItemPaso,
    "Resumen": ItemResumen,
    "Guion": ItemEscena,
}


# --- Partes del paquete ---
# Los modelos de respuesta ignoran los campos que la interfaz no usa (aprobado_en, almacenamiento_oci…)
class Metadatos(BaseModel):
    tiempo_estimado_estudio_minutos: int = Field(ge=0)
    conceptos_clave: list[str] = []
    prerrequisitos: list[str] = []
    perfil_aplicado: str
    formato_generado: str
    nicho_sector: str
    nivel_detalle: str


class ContenidoAdaptado(BaseModel):
    titulo: str
    introduccion_contextualizada: str = ""
    # Los items se validan aparte con items_validos(): si alguno viene mal,
    # la interfaz usa la vista genérica en vez de romperse.
    items: list[dict] = []


class Fuente(BaseModel):
    documento_id: str
    documento: str  # título del documento de origen
    fragmento: int = Field(ge=1)
    pagina: Optional[int] = None
    extracto: str


class EvaluacionCalidad(BaseModel):
    anclaje_fuente_score: float = Field(ge=0, le=1)
    calidad_pedagogica_score: float = Field(ge=0, le=1)
    cumplimiento_formato_score: float = Field(ge=0, le=1)
    claridad_pedagogica: str
    observaciones: str = ""
    intentos_revision: int = Field(ge=0)


class Paquete(BaseModel):
    """El material generado. Si falla la generación, la API responde un error HTTP, no un paquete."""

    id: str
    creado_en: datetime
    id_tema: Optional[str] = None
    # requiere_revision: no pasó la revisión de calidad; el estudiante no lo ve hasta que el admin lo apruebe
    status: Literal["exito", "requiere_revision"]
    metadatos: Metadatos
    contenido_adaptado: ContenidoAdaptado
    evaluacion_calidad: EvaluacionCalidad
    fuentes: list[Fuente] = []


class MaterialEnRevision(BaseModel):
    """Lo que recibe el estudiante (202) cuando su material queda pendiente de revisión."""

    id: str
    creado_en: datetime


def items_validos(paquete):
    """Valida los items del paquete según su formato.

    Lanza ValidationError si algún item no cumple, y KeyError si el formato no está en MODELO_ITEM.
    """
    modelo = MODELO_ITEM[paquete.metadatos.formato_generado]
    return [modelo.model_validate(item) for item in paquete.contenido_adaptado.items]


# --- Peticiones y listados ---
class SolicitudPaquete(BaseModel):
    id_tema: str = Field(min_length=1)  # Backend busca solo en los documentos de este tema
    tema: str = ""  # "¿Algo en particular?": vacío = todo el tema
    perfil_destinatario: str
    formato_salida: str
    # Sin nicho: el sector lo define el admin para toda la institución (ver Configuracion)

    @field_validator("tema")
    @classmethod
    def tema_valido(cls, valor):
        valor = valor.strip()
        if len(valor) > LARGO_MAXIMO_TEMA:
            raise ValueError(f"el tema no puede pasar de {LARGO_MAXIMO_TEMA} caracteres")
        return valor

    @model_validator(mode="after")
    def valores_permitidos(self):
        for campo, permitidos in (("perfil_destinatario", PERFILES), ("formato_salida", FORMATOS)):
            if getattr(self, campo) not in permitidos:
                raise ValueError(f"{campo} no permitido: {getattr(self, campo)!r}")
        return self


class Configuracion(BaseModel):
    """Ajustes que define el admin para toda la institución."""

    sector: str = "General"

    @field_validator("sector")
    @classmethod
    def sector_permitido(cls, valor):
        if valor not in NICHOS:
            raise ValueError(f"sector no permitido: {valor!r}")
        return valor


class ResumenPaquete(BaseModel):
    id: str
    titulo: str = ""
    creado_en: datetime
    tema: str
    formato: str
    anclaje_fuente_score: float


class Documento(BaseModel):
    """Un documento ya indexado: la subida es síncrona, así que si falla no queda en la lista."""

    id: str
    titulo: str
    nombre_archivo: str
    tipo: Literal["pdf", "md", "txt"]
    fragmentos: int = Field(ge=0)
    creado_en: datetime


# --- Cuentas y temas (v2): el admin crea las cuentas y arma los temas ---
ROLES = ("estudiante", "admin")
LARGO_MAXIMO_NOMBRE_TEMA = 100
LARGO_MAXIMO_DESCRIPCION = 500
LARGO_MAXIMO_ID_TEMA = 100
LARGO_MINIMO_CONTRASENA = 12  # el mismo mínimo que pide Backend
LARGO_MAXIMO_NOMBRE = 150
LARGO_MAXIMO_USUARIO = 100
# Sin 0/O/o ni 1/l/I: la contraseña temporal se dicta o se copia a mano
CARACTERES_CONTRASENA = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class Usuario(BaseModel):
    id_usuario: int
    nombre: str
    usuario: str
    rol: Literal["estudiante", "admin"]
    activo: bool = True
    debe_cambiar_contrasena: bool = False
    temas: list[str] = []  # id_tema asignados (solo estudiantes)


class Sesion(BaseModel):
    token: str
    usuario: Usuario


class Tema(BaseModel):
    id_tema: str
    nombre: str
    descripcion: str = ""
    # El sector con el que se genera el material de este tema (texto libre: lo que guarde Backend)
    nicho_sector: str = "General"
    documentos: list["DocumentoTema"] = []


class DocumentoTema(BaseModel):
    """Un documento dentro de un tema: el id para guardar y el título para mostrar."""

    id: str
    titulo: str


class DatosTema(BaseModel):
    """Lo que el admin escribe para crear o editar un tema."""

    nombre: str
    descripcion: str = ""
    nicho_sector: str = "General"
    documentos: list[str] = Field(min_length=1)  # id de cada documento

    @field_validator("nicho_sector")
    @classmethod
    def sector_permitido(cls, valor):
        if valor not in NICHOS:
            raise ValueError(f"sector no permitido: {valor!r}")
        return valor

    @field_validator("nombre")
    @classmethod
    def nombre_valido(cls, valor):
        valor = valor.strip()
        if not valor:
            raise ValueError("el nombre no puede estar vacío")
        if len(valor) > LARGO_MAXIMO_NOMBRE_TEMA:
            raise ValueError(f"el nombre no puede pasar de {LARGO_MAXIMO_NOMBRE_TEMA} caracteres")
        return valor

    @field_validator("descripcion")
    @classmethod
    def descripcion_valida(cls, valor):
        valor = valor.strip()
        if len(valor) > LARGO_MAXIMO_DESCRIPCION:
            raise ValueError(f"la descripción no puede pasar de {LARGO_MAXIMO_DESCRIPCION} caracteres")
        return valor

    @field_validator("documentos")
    @classmethod
    def sin_repetidos(cls, valor):
        return list(dict.fromkeys(valor))


def id_tema_desde_nombre(nombre):
    """Arma el id que pide Backend a partir del nombre: "Análisis de año" → "analisis-de-ano"."""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    identificador = re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower())[:LARGO_MAXIMO_ID_TEMA].strip("-")
    return identificador or f"tema-{uuid4().hex[:8]}"  # un nombre de solo símbolos


class DatosEstudiante(BaseModel):
    """Lo que el admin escribe para crear un estudiante (Backend solo deja crear estudiantes)."""

    nombre: str = Field(max_length=LARGO_MAXIMO_NOMBRE)
    usuario: str = Field(max_length=LARGO_MAXIMO_USUARIO)
    contrasena_temporal: str = Field(min_length=LARGO_MINIMO_CONTRASENA)
    temas: list[str] = []  # id_tema asignados

    @field_validator("nombre", "usuario", mode="before")
    @classmethod
    def sin_espacios_ni_vacio(cls, valor):
        valor = str(valor).strip()
        if not valor:
            raise ValueError("no puede quedar vacío")
        return valor

    @field_validator("temas")
    @classmethod
    def temas_sin_repetidos(cls, valor):
        return list(dict.fromkeys(valor))


def generar_contrasena_temporal():
    """Contraseña aleatoria de 14 caracteres para dictar: "Ab3k-9Qm2-Zt7p"."""
    return "-".join("".join(secrets.choice(CARACTERES_CONTRASENA) for _ in range(4)) for _ in range(3))
