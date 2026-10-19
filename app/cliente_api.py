"""La costura de F07: el único archivo de la interfaz que sabe de dónde vienen los datos.

MODO_API=mock → responde con los JSON de app/mocks/ (no necesita la API).
MODO_API=http → llama a la API FastAPI del Backend.
Las páginas solo usan obtener_cliente() y los métodos de los clientes; nunca saben de HTTP.
"""

import os
from pathlib import Path
from uuid import uuid4

import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from contrato import Configuracion, Documento, Paquete, ResumenPaquete

CARPETA_MOCKS = Path(__file__).resolve().parent / "mocks"
TEMA_SIN_CONTEXTO_MOCK = "tema inexistente"  # en modo mock, este tema devuelve el error sin_contexto
TIEMPO_SALUD_SEGUNDOS = 5
TIEMPO_CORTO_SEGUNDOS = 10  # rutas que no generan ni indexan: no esperar el tiempo máximo
MOCK_POR_FORMATO = {
    "Flashcards": "flashcards.json",
    "Quiz": "quiz.json",
    "Tutorial": "tutorial.json",
    "Resumen": "resumen.json",
    "Guion": "guion.json",
}


class ErrorCliente(Exception):
    """Error ya traducido para el usuario. `tipo` dice qué pasó; `detalle` va en el desplegable."""

    MENSAJES = {
        "no_disponible": "El servicio no está disponible en este momento. Inténtalo de nuevo más tarde.",
        "tiempo_agotado": "La generación está tardando más de lo normal. Inténtalo de nuevo en unos minutos.",
        "sin_permiso": "No tienes permiso para esta acción. Revisa la clave del administrador en la configuración.",
        "respuesta_invalida": "Hubo un problema con el material generado. Inténtalo de nuevo.",
        "rechazado": "El servicio no pudo atender la petición. Inténtalo de nuevo.",
    }

    def __init__(self, tipo, detalle=""):
        super().__init__(self.MENSAJES[tipo])
        self.tipo = tipo
        self.mensaje = self.MENSAJES[tipo]
        self.detalle = detalle


class ClienteMock:
    """Responde con los ejemplos de app/mocks/. Los documentos subidos viven solo en memoria."""

    es_mock = True

    def __init__(self, carpeta=CARPETA_MOCKS):
        self._carpeta = Path(carpeta)
        self._documentos = [
            Documento(nombre="oci_redes_vcn.pdf", estado="indexado", chunks=24),
            Documento(nombre="manual_escaneado.pdf", estado="error", error="El PDF no tiene texto extraíble."),
        ]
        self._configuracion = Configuracion()
        self._guiones_generados = 0

    def _leer(self, nombre):
        return Paquete.model_validate_json((self._carpeta / nombre).read_text(encoding="utf-8"))

    def _todos(self):
        return [self._leer(ruta.name) for ruta in sorted(self._carpeta.glob("*.json"))]

    def salud(self):
        return True

    def generar_paquete(self, solicitud):
        if solicitud.tema.lower() == TEMA_SIN_CONTEXTO_MOCK:
            return self._leer("error_sin_contexto.json")
        paquete = self._leer(MOCK_POR_FORMATO[solicitud.formato])
        metadatos = paquete.metadatos.model_copy(update={
            "tema": solicitud.tema,
            "perfil_aplicado": solicitud.perfil,
            "nicho_sector": self._configuracion.sector,
        })
        # Id nuevo en cada generación, como hará la API: si se repite, las vistas
        # interactivas heredan el estado del paquete anterior (quiz ya calificado, etc.)
        id_nuevo = f"{paquete.id_paquete}-{uuid4().hex[:8]}"
        cambios = {"metadatos": metadatos, "id_paquete": id_nuevo}
        if solicitud.formato == "Guion":
            # Para la demo: un guion sí y otro no cae en revisión, así se ven los dos casos
            self._guiones_generados += 1
            if self._guiones_generados % 2 == 0:
                cambios["evaluacion_calidad"] = paquete.evaluacion_calidad.model_copy(
                    update={"requiere_revision_admin": False})
        return paquete.model_copy(update=cambios)

    def obtener_paquete(self, id_paquete):
        for paquete in self._todos():
            if paquete.id_paquete == id_paquete:
                return paquete
        raise ErrorCliente("rechazado", f"No existe el paquete {id_paquete}")

    def listar_paquetes_revision(self):
        return [
            ResumenPaquete(
                id_paquete=p.id_paquete,
                creado_en=p.creado_en,
                tema=p.metadatos.tema,
                formato=p.metadatos.formato_generado,
                anclaje_fuente_score=p.evaluacion_calidad.anclaje_fuente_score,
            )
            for p in self._todos()
            if p.status == "exito" and p.evaluacion_calidad.requiere_revision_admin
        ]

    def subir_documento(self, nombre, contenido):
        documento = Documento(nombre=nombre, estado="indexado", chunks=len(contenido) // 1000 + 1)
        self._documentos.append(documento)
        return documento

    def listar_documentos(self):
        return list(self._documentos)

    def obtener_configuracion(self):
        return self._configuracion

    def guardar_configuracion(self, sector):
        try:
            self._configuracion = Configuracion(sector=sector)
        except ValidationError as error:
            raise ErrorCliente("rechazado", str(error)) from error
        return self._configuracion


class ClienteHttp:
    """Llama a la API del Backend. Traduce cualquier falla a ErrorCliente."""

    es_mock = False

    def __init__(self, url, clave_admin="", tiempo_maximo=120, sesion=None):
        self._url = url.rstrip("/")
        self._clave_admin = clave_admin
        self._tiempo_maximo = tiempo_maximo
        self._sesion = sesion or requests.Session()

    def _pedir(self, metodo, ruta, admin=False, tiempo=None, **kwargs):
        cabeceras = {"X-Clave-Admin": self._clave_admin} if admin else {}
        try:
            respuesta = self._sesion.request(metodo, self._url + ruta, headers=cabeceras,
                                             timeout=tiempo or TIEMPO_CORTO_SEGUNDOS, **kwargs)
        except requests.Timeout as error:  # va antes: Timeout también es RequestException
            raise ErrorCliente("tiempo_agotado", str(error)) from error
        except requests.RequestException as error:
            raise ErrorCliente("no_disponible", str(error)) from error
        if respuesta.status_code == 401:
            raise ErrorCliente("sin_permiso", respuesta.text)
        if respuesta.status_code >= 400:
            raise ErrorCliente("rechazado", f"{respuesta.status_code}: {respuesta.text}")
        try:
            return respuesta.json()
        except ValueError as error:
            raise ErrorCliente("respuesta_invalida", f"La respuesta no es JSON: {respuesta.text[:200]}") from error

    def _validar(self, modelo, datos):
        try:
            return modelo.model_validate(datos)
        except ValidationError as error:
            raise ErrorCliente("respuesta_invalida", str(error)) from error

    def _lista(self, modelo, datos):
        if not isinstance(datos, list):
            raise ErrorCliente("respuesta_invalida", f"Se esperaba una lista y llegó: {type(datos).__name__}")
        return [self._validar(modelo, elemento) for elemento in datos]

    def salud(self):
        try:
            self._pedir("GET", "/salud", tiempo=TIEMPO_SALUD_SEGUNDOS)
            return True
        except ErrorCliente:
            return False

    def generar_paquete(self, solicitud):
        return self._validar(Paquete, self._pedir("POST", "/paquetes", tiempo=self._tiempo_maximo,
                                                   json=solicitud.model_dump()))

    def obtener_paquete(self, id_paquete):
        return self._validar(Paquete, self._pedir("GET", f"/paquetes/{id_paquete}"))

    def listar_paquetes_revision(self):
        datos = self._pedir("GET", "/paquetes", admin=True, params={"requiere_revision": "true"})
        return self._lista(ResumenPaquete, datos)

    def subir_documento(self, nombre, contenido):
        datos = self._pedir("POST", "/documentos", admin=True, tiempo=self._tiempo_maximo,
                            files={"archivo": (nombre, contenido)})
        return self._validar(Documento, datos)

    def listar_documentos(self):
        return self._lista(Documento, self._pedir("GET", "/documentos", admin=True))

    def obtener_configuracion(self):
        return self._validar(Configuracion, self._pedir("GET", "/configuracion"))

    def guardar_configuracion(self, sector):
        datos = self._pedir("PUT", "/configuracion", admin=True, json={"sector": sector})
        return self._validar(Configuracion, datos)


def obtener_cliente():
    """Elige el cliente según MODO_API (por defecto, mock)."""
    load_dotenv()
    if os.getenv("MODO_API", "mock").strip().lower() == "http":
        return ClienteHttp(
            url=os.getenv("URL_API", "http://localhost:8000"),
            clave_admin=os.getenv("CLAVE_ADMIN_API", ""),
            tiempo_maximo=float(os.getenv("TIEMPO_MAXIMO_SEGUNDOS", "120")),
        )
    return ClienteMock()
