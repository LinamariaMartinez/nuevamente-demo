"""Contrato de F07: la forma de los datos que viajan entre la interfaz (app/) y la API (api/).

Lo usan los dos lados. Se cambia solo de común acuerdo; si cambia, los ejemplos de
app/mocks/ se actualizan en el mismo PR.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# --- Listas fijas: las mismas para el formulario y para la validación de la API ---
# Perfiles: los tres niveles que reconoce el Redactor (src/agents/writer_examples.py)
PERFILES = ("Principiante", "Intermedio", "Avanzado")
FORMATOS = ("Tutorial", "Flashcards", "Quiz", "Resumen", "Guion")
NICHOS = ("Fintech", "Salud", "E-commerce", "General")
LARGO_MAXIMO_TEMA = 300


# --- Items: su forma cambia según el formato ---
class ItemFlashcard(BaseModel):
    frente: str
    dorso: str
    pista_didactica: Optional[str] = None


class ItemQuiz(BaseModel):
    pregunta: str
    opciones: list[str] = Field(min_length=2)
    respuesta_correcta: int = Field(ge=0)  # posición dentro de opciones, empezando en 0
    justificacion: str

    @model_validator(mode="after")
    def opciones_coherentes(self):
        if len(set(self.opciones)) != len(self.opciones):
            raise ValueError("las opciones no pueden repetirse")
        if self.respuesta_correcta >= len(self.opciones):
            raise ValueError("respuesta_correcta apunta a una opción que no existe")
        return self


class ItemPaso(BaseModel):
    paso: int = Field(ge=1)
    titulo: str
    explicacion: str
    ejemplo: Optional[str] = None


class ItemSeccion(BaseModel):
    titulo: str
    contenido: str


MODELO_ITEM = {
    "Flashcards": ItemFlashcard,
    "Quiz": ItemQuiz,
    "Tutorial": ItemPaso,
    "Resumen": ItemSeccion,
    "Guion": ItemSeccion,
}


# --- Partes del paquete ---
class Metadatos(BaseModel):
    tema: str
    tiempo_estimado_estudio_minutos: int = Field(ge=0)
    conceptos_clave: list[str] = []
    prerrequisitos: list[str] = []
    perfil_aplicado: str
    formato_generado: str
    nicho_sector: str
    nivel_detalle: Optional[str] = None


class ContenidoAdaptado(BaseModel):
    titulo: str
    introduccion_contextualizada: str = ""
    # Los items se validan aparte con items_validos(): si alguno viene mal,
    # la interfaz usa la vista genérica en vez de romperse.
    items: list[dict] = []


class Fuente(BaseModel):
    documento: str
    fragmento: int
    extracto: str


class EvaluacionCalidad(BaseModel):
    anclaje_fuente_score: float = Field(ge=0, le=1)
    claridad_pedagogica: str
    observaciones: str = ""
    intentos_revision: int = Field(ge=0)
    requiere_revision_admin: bool = False


class Paquete(BaseModel):
    id_paquete: str
    creado_en: datetime
    status: Literal["exito", "error"]
    codigo_error: Optional[Literal["sin_contexto", "contenido_vacio", "error_interno"]] = None
    mensaje_error: Optional[str] = None
    metadatos: Optional[Metadatos] = None
    contenido_adaptado: Optional[ContenidoAdaptado] = None
    fuentes: list[Fuente] = []
    evaluacion_calidad: Optional[EvaluacionCalidad] = None

    @model_validator(mode="after")
    def partes_segun_status(self):
        if self.status == "exito":
            faltan = [nombre for nombre in ("metadatos", "contenido_adaptado", "evaluacion_calidad")
                      if getattr(self, nombre) is None]
            if faltan:
                raise ValueError(f"un paquete con status 'exito' necesita: {', '.join(faltan)}")
        elif self.codigo_error is None:
            raise ValueError("un paquete con status 'error' necesita codigo_error")
        return self


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
    perfil: str
    formato: str
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
        for campo, permitidos in (("perfil", PERFILES), ("formato", FORMATOS)):
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
    id_paquete: str
    creado_en: datetime
    tema: str
    formato: str
    anclaje_fuente_score: float


class Documento(BaseModel):
    nombre: str
    estado: Literal["procesando", "indexado", "error"]
    chunks: int = 0
    error: Optional[str] = None


# --- Cuentas y temas (v2): el admin crea las cuentas y arma los temas ---
ROLES = ("estudiante", "admin")
LARGO_MAXIMO_NOMBRE_TEMA = 100
LARGO_MAXIMO_DESCRIPCION = 500


class Usuario(BaseModel):
    id_usuario: str
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
    # Nombres de archivo, iguales al metadata["source"] de los chunks: el Investigador filtra por ellos
    documentos: list[str] = []


class DatosTema(BaseModel):
    """Lo que el admin escribe para crear o editar un tema."""

    nombre: str
    descripcion: str = ""
    documentos: list[str] = Field(min_length=1)

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
