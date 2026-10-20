"""La costura de F07: el único archivo de la interfaz que sabe de dónde vienen los datos.

MODO_API=mock → responde con los JSON de app/mocks/ (no necesita la API).
MODO_API=http → llama a la API FastAPI del Backend.
Las páginas solo usan obtener_cliente() y los métodos de los clientes; nunca saben de HTTP.
"""

import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from contrato import (Configuracion, Documento, DocumentoTema, Paquete, ResumenPaquete, Sesion, Tema, Usuario,
                      id_tema_desde_nombre)

CARPETA_MOCKS = Path(__file__).resolve().parent / "mocks"
CARPETA_INSTITUCION = CARPETA_MOCKS / "institucion"  # cuentas y temas de demostración
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
    """Error ya traducido para el usuario. `tipo` dice qué pasó; `detalle` es técnico y solo lo ve el admin."""

    MENSAJES = {
        "credenciales": "No pudimos validar tus datos. Revisa tu usuario y contraseña e inténtalo de nuevo.",
        "sesion_vencida": "Tu sesión terminó. Inicia sesión de nuevo.",
        "sin_permiso": "No tienes permiso para esta acción.",
        "no_encontrado": "No encontramos lo que buscabas. Es posible que se haya retirado.",
        "no_disponible": "El servicio no está disponible en este momento. Inténtalo de nuevo más tarde.",
        "tiempo_agotado": "La generación está tardando más de lo normal. Inténtalo de nuevo en unos minutos.",
        "respuesta_invalida": "Hubo un problema con el material generado. Inténtalo de nuevo.",
        "rechazado": "El servicio no pudo atender la petición. Inténtalo de nuevo.",
    }

    def __init__(self, tipo, detalle="", mensaje=None):
        # `mensaje` reemplaza el texto por defecto: lo usa el {"mensaje": ...} de Backend en 409 y 422
        self.tipo = tipo
        self.mensaje = mensaje or self.MENSAJES[tipo]
        self.detalle = detalle
        super().__init__(self.mensaje)


class ClienteMock:
    """Responde con los ejemplos de app/mocks/. Cuentas, temas y documentos viven solo en memoria.

    Aplica los mismos permisos que Backend: sin sesión no hay datos, el estudiante solo ve y genera
    sus temas, y las rutas de admin piden el rol admin.
    """

    es_mock = True

    def __init__(self, carpeta=CARPETA_MOCKS):
        self._carpeta = Path(carpeta)
        institucion = self._carpeta / "institucion"
        cuentas = json.loads((institucion / "usuarios.json").read_text(encoding="utf-8"))
        # usuario → {"contrasena": ..., "usuario": Usuario}
        self._cuentas = {c["usuario"]["usuario"]: {"contrasena": c["contrasena"],
                                                   "usuario": Usuario.model_validate(c["usuario"])}
                         for c in cuentas}
        self._temas = [Tema.model_validate(t)
                       for t in json.loads((institucion / "temas.json").read_text(encoding="utf-8"))]
        creado = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)
        self._documentos = [
            Documento(id="d-redes", titulo="Redes VCN en OCI", nombre_archivo="oci_redes_vcn.pdf", tipo="pdf",
                      fragmentos=24, creado_en=creado),
            Documento(id="d-nube", titulo="Políticas de seguridad en la nube", nombre_archivo="politicas_nube.md",
                      tipo="md", fragmentos=12, creado_en=creado),
            Documento(id="d-datos", titulo="Guía de herramientas de datos", nombre_archivo="guia_datos.txt",
                      tipo="txt", fragmentos=8, creado_en=creado),
        ]
        self._configuracion = Configuracion()
        self._guiones_generados = 0
        self._usuario = None  # quien inició sesión en este cliente

    # --- Ayudas internas ---
    def _leer(self, nombre):
        return Paquete.model_validate_json((self._carpeta / nombre).read_text(encoding="utf-8"))

    def _todos(self):
        return [self._leer(ruta.name) for ruta in sorted(self._carpeta.glob("*.json"))]

    def _exigir(self, rol=None):
        if self._usuario is None:
            raise ErrorCliente("sesion_vencida", "No hay una sesión iniciada.")
        if rol is not None and self._usuario.rol != rol:
            raise ErrorCliente("sin_permiso", f"Esta acción necesita el rol {rol}.")
        return self._usuario

    def _indice_tema(self, id_tema):
        for indice, tema in enumerate(self._temas):
            if tema.id_tema == id_tema:
                return indice
        raise ErrorCliente("no_encontrado", f"No existe el tema {id_tema}")

    def _revisar_datos_tema(self, datos, id_tema=None):
        repetido = any(t.nombre.lower() == datos.nombre.lower() and t.id_tema != id_tema for t in self._temas)
        if repetido:
            raise ErrorCliente("rechazado", mensaje="Ya existe un tema con ese nombre.")
        subidos = {d.id for d in self._documentos}
        faltan = [id_documento for id_documento in datos.documentos if id_documento not in subidos]
        if faltan:
            raise ErrorCliente("rechazado", ", ".join(faltan), mensaje="Elige solo documentos ya subidos.")

    def _tema(self, id_tema, datos):
        titulos = {d.id: d.titulo for d in self._documentos}
        return Tema(id_tema=id_tema, nombre=datos.nombre, descripcion=datos.descripcion,
                    documentos=[DocumentoTema(id=d, titulo=titulos[d]) for d in datos.documentos])

    # --- Sesión ---
    def salud(self):
        return True

    def iniciar_sesion(self, usuario, contrasena):
        cuenta = self._cuentas.get(usuario)
        valida = (cuenta is not None and cuenta["usuario"].activo
                  and hmac.compare_digest(contrasena.encode(), cuenta["contrasena"].encode()))
        if not valida:  # mismo error si no existe, está desactivada o la contraseña no coincide
            raise ErrorCliente("credenciales")
        self._usuario = cuenta["usuario"]
        return Sesion(token=f"mock-{uuid4().hex}", usuario=self._usuario)

    def cerrar_sesion(self):
        self._usuario = None

    def cambiar_contrasena(self, actual, nueva):
        usuario = self._exigir()
        cuenta = self._cuentas[usuario.usuario]
        if not hmac.compare_digest(actual.encode(), cuenta["contrasena"].encode()):
            raise ErrorCliente("rechazado", mensaje="La contraseña actual no es correcta.")
        cuenta["contrasena"] = nueva
        cuenta["usuario"] = usuario.model_copy(update={"debe_cambiar_contrasena": False})
        self._usuario = cuenta["usuario"]

    # --- Temas ---
    def listar_temas(self):
        usuario = self._exigir()
        if usuario.rol == "admin":
            return list(self._temas)
        return [tema for tema in self._temas if tema.id_tema in usuario.temas]

    def crear_tema(self, datos):
        self._exigir("admin")
        self._revisar_datos_tema(datos)
        id_tema = id_tema_desde_nombre(datos.nombre)
        if any(t.id_tema == id_tema for t in self._temas):  # como Backend: el id no se puede repetir
            raise ErrorCliente("rechazado", mensaje="Ya existe un tema con ese nombre.")
        tema = self._tema(id_tema, datos)
        self._temas.append(tema)
        return tema

    def editar_tema(self, id_tema, datos):
        self._exigir("admin")
        indice = self._indice_tema(id_tema)
        self._revisar_datos_tema(datos, id_tema)
        self._temas[indice] = self._tema(id_tema, datos)
        return self._temas[indice]

    def retirar_tema(self, id_tema):
        self._exigir("admin")
        del self._temas[self._indice_tema(id_tema)]
        # Quienes lo tenían asignado dejan de verlo
        for cuenta in self._cuentas.values():
            temas = [t for t in cuenta["usuario"].temas if t != id_tema]
            cuenta["usuario"] = cuenta["usuario"].model_copy(update={"temas": temas})

    # --- Material ---
    def generar_paquete(self, solicitud):
        usuario = self._exigir("estudiante")
        if solicitud.id_tema not in usuario.temas:
            raise ErrorCliente("sin_permiso", f"El tema {solicitud.id_tema} no está asignado a {usuario.usuario}.")
        tema = self._temas[self._indice_tema(solicitud.id_tema)]
        if solicitud.tema.lower() == TEMA_SIN_CONTEXTO_MOCK:
            return self._leer("error_sin_contexto.json")
        paquete = self._leer(MOCK_POR_FORMATO[solicitud.formato])
        metadatos = paquete.metadatos.model_copy(update={
            "tema": solicitud.tema or tema.nombre,
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
        self._exigir("admin")
        for paquete in self._todos():
            if paquete.id_paquete == id_paquete:
                return paquete
        raise ErrorCliente("no_encontrado", f"No existe el paquete {id_paquete}")

    def listar_paquetes_revision(self):
        self._exigir("admin")
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

    # --- Documentos y configuración ---
    def subir_documento(self, nombre, contenido):
        self._exigir("admin")
        documento = Documento(id=f"d-{uuid4().hex[:8]}", titulo=Path(nombre).stem, nombre_archivo=nombre,
                              tipo=nombre.rsplit(".", 1)[-1].lower(), fragmentos=len(contenido) // 1000 + 1,
                              creado_en=datetime.now(timezone.utc))
        self._documentos.append(documento)
        return documento

    def listar_documentos(self):
        self._exigir("admin")
        return list(self._documentos)

    def obtener_configuracion(self):
        self._exigir()
        return self._configuracion

    def guardar_configuracion(self, sector):
        self._exigir("admin")
        try:
            self._configuracion = Configuracion(sector=sector)
        except ValidationError as error:
            raise ErrorCliente("rechazado", str(error)) from error
        return self._configuracion


def _en_ruta(valor):
    """Codifica un id para ponerlo en la URL: 't/1 a' → 't%2F1%20a'."""
    return quote(str(valor), safe="")


def _mensaje_de_backend(respuesta):
    """Backend manda {"mensaje": "..."} en español en los 409 y 422 (spec §5.7)."""
    try:
        mensaje = respuesta.json().get("mensaje")
    except (ValueError, AttributeError):
        return None
    return mensaje if isinstance(mensaje, str) and mensaje.strip() else None


class ClienteHttp:
    """Llama a la API del Backend. Traduce cualquier falla a ErrorCliente.

    El token vive en este objeto, que a su vez vive en st.session_state: nunca va en la URL ni en logs.
    """

    es_mock = False

    def __init__(self, url, tiempo_maximo=120, sesion=None):
        self._url = url.rstrip("/")
        self._tiempo_maximo = tiempo_maximo
        self._sesion = sesion or requests.Session()
        self._token = None

    def _pedir(self, metodo, ruta, tiempo=None, **kwargs):
        cabeceras = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            respuesta = self._sesion.request(metodo, self._url + ruta, headers=cabeceras,
                                             timeout=tiempo or TIEMPO_CORTO_SEGUNDOS, **kwargs)
        except requests.Timeout as error:  # va antes: Timeout también es RequestException
            raise ErrorCliente("tiempo_agotado", str(error)) from error
        except requests.RequestException as error:
            raise ErrorCliente("no_disponible", str(error)) from error
        estado = respuesta.status_code
        if estado == 401:
            if (metodo, ruta) == ("PUT", "/sesion/contrasena"):
                # La contraseña actual no coincide: la sesión sigue viva y no hay que mandar a la persona al login
                raise ErrorCliente("rechazado", respuesta.text, mensaje="La contraseña actual no es correcta.")
            tipo = "credenciales" if (metodo, ruta) == ("POST", "/sesion") else "sesion_vencida"
            raise ErrorCliente(tipo, respuesta.text)
        if estado == 403:
            raise ErrorCliente("sin_permiso", respuesta.text)
        if estado == 404:
            raise ErrorCliente("no_encontrado", respuesta.text)
        if estado in (409, 422):
            raise ErrorCliente("rechazado", respuesta.text, mensaje=_mensaje_de_backend(respuesta))
        if estado >= 400:
            raise ErrorCliente("rechazado", f"{estado}: {respuesta.text}")
        if estado == 204 or not respuesta.content:
            return None
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

    # --- Sesión ---
    def salud(self):
        try:
            self._pedir("GET", "/salud", tiempo=TIEMPO_SALUD_SEGUNDOS)
            return True
        except ErrorCliente:
            return False

    def iniciar_sesion(self, usuario, contrasena):
        datos = self._pedir("POST", "/sesion", json={"usuario": usuario, "contrasena": contrasena})
        sesion = self._validar(Sesion, datos)
        self._token = sesion.token
        return sesion

    def cerrar_sesion(self):
        try:
            if self._token:
                self._pedir("DELETE", "/sesion")
        finally:
            self._token = None  # aunque la API falle, aquí la sesión se cierra

    def cambiar_contrasena(self, actual, nueva):
        self._pedir("PUT", "/sesion/contrasena", json={"actual": actual, "nueva": nueva})

    # --- Temas ---
    def listar_temas(self):
        return self._lista(Tema, self._pedir("GET", "/temas"))

    def crear_tema(self, datos):
        return self._validar(Tema, self._pedir("POST", "/temas", json=datos.model_dump()))

    def editar_tema(self, id_tema, datos):
        return self._validar(Tema, self._pedir("PUT", f"/temas/{_en_ruta(id_tema)}", json=datos.model_dump()))

    def retirar_tema(self, id_tema):
        self._pedir("DELETE", f"/temas/{_en_ruta(id_tema)}")

    # --- Material ---
    def generar_paquete(self, solicitud):
        return self._validar(Paquete, self._pedir("POST", "/paquetes", tiempo=self._tiempo_maximo,
                                                   json=solicitud.model_dump()))

    def obtener_paquete(self, id_paquete):
        return self._validar(Paquete, self._pedir("GET", f"/paquetes/{_en_ruta(id_paquete)}"))

    def listar_paquetes_revision(self):
        return self._lista(ResumenPaquete, self._pedir("GET", "/paquetes", params={"requiere_revision": "true"}))

    # --- Documentos y configuración ---
    def subir_documento(self, nombre, contenido):
        datos = self._pedir("POST", "/documentos", tiempo=self._tiempo_maximo, files={"archivo": (nombre, contenido)})
        return self._validar(Documento, datos)

    def listar_documentos(self):
        return self._lista(Documento, self._pedir("GET", "/documentos"))

    def obtener_configuracion(self):
        return self._validar(Configuracion, self._pedir("GET", "/configuracion"))

    def guardar_configuracion(self, sector):
        return self._validar(Configuracion, self._pedir("PUT", "/configuracion", json={"sector": sector}))


def obtener_cliente():
    """Elige el cliente según MODO_API (por defecto, mock)."""
    load_dotenv()
    if os.getenv("MODO_API", "mock").strip().lower() == "http":
        return ClienteHttp(
            url=os.getenv("URL_API", "http://localhost:8000"),
            tiempo_maximo=float(os.getenv("TIEMPO_MAXIMO_SEGUNDOS", "120")),
        )
    return ClienteMock()
