"""La costura de F07: el único archivo de la interfaz que sabe de dónde vienen los datos.

MODO_API=mock → responde con los JSON de app/mocks/ (no necesita la API).
MODO_API=http → llama a la API FastAPI del Backend.
Las páginas solo usan obtener_cliente() y los métodos de los clientes; nunca saben de HTTP.
"""

import hmac
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from contrato import (LARGO_MINIMO_CONTRASENA, Configuracion, Documento, DocumentoTema, MaterialEnRevision, Paquete,
                      ResumenPaquete, Sesion, Tema, Usuario, id_tema_desde_nombre)

CARPETA_MOCKS = Path(__file__).resolve().parent / "mocks"
CARPETA_INSTITUCION = CARPETA_MOCKS / "institucion"  # cuentas y temas de demostración
TEMA_SIN_CONTEXTO_MOCK = "tema inexistente"  # en modo mock, este pedido lanza el error sin_contexto
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
        "tiempo_agotado": ("La generación está tardando más de lo normal. Puede que termine en unos minutos: "
                           "revisa Mi material antes de generarlo de nuevo."),
        "respuesta_invalida": "Hubo un problema con el material generado. Inténtalo de nuevo.",
        "rechazado": "El servicio no pudo atender la petición. Inténtalo de nuevo.",
        "sin_contexto": "No encontramos ese tema en los documentos cargados. Prueba con otras palabras.",
        "sin_documentos": "Este tema todavía no tiene documentos. Avísale a quien administra la plataforma.",
        "demasiados_intentos": "Demasiados intentos. Intenta de nuevo en unos minutos.",
    }

    def __init__(self, tipo, detalle="", mensaje=None):
        # `mensaje` reemplaza el texto por defecto: lo usa el mensaje de Backend en 400, 409, 413, 415 y 422
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
        # Material en revisión: id → (paquete, lo que se pidió). Arranca con el guion de ejemplo.
        guion = self._leer(MOCK_POR_FORMATO["Guion"])
        self._pendientes = {guion.id: (guion, "Redes en OCI")}
        self._aprobados = {}
        self._eliminados = set()  # rechazados: ya no existen
        self._generados = {}  # id → (paquete, usuario que lo pidió, lo que pidió): para "Mi material"
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
        return Tema(id_tema=id_tema, nombre=datos.nombre, descripcion=datos.descripcion, nicho_sector=datos.nicho_sector,
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
        if len(nueva) < LARGO_MINIMO_CONTRASENA:  # las mismas reglas que Backend
            raise ErrorCliente("rechazado", mensaje=f"La nueva contraseña debe tener al menos "
                                                    f"{LARGO_MINIMO_CONTRASENA} caracteres.")
        if nueva == actual:
            raise ErrorCliente("rechazado", mensaje="La nueva contraseña debe ser diferente.")
        cuenta["contrasena"] = nueva
        cuenta["usuario"] = usuario.model_copy(update={"debe_cambiar_contrasena": False})
        self._usuario = None  # como Backend: cambiar la contraseña cierra las sesiones de la persona

    # --- Usuarios (solo admin; como Backend, solo se crean y modifican estudiantes) ---
    def _cuenta_de_estudiante(self, id_usuario):
        self._exigir("admin")
        for cuenta in self._cuentas.values():
            if cuenta["usuario"].id_usuario == id_usuario and cuenta["usuario"].rol == "estudiante":
                return cuenta
        raise ErrorCliente("no_encontrado", f"No existe un estudiante con el id {id_usuario}")

    def _actualizar(self, cuenta, **cambios):
        cuenta["usuario"] = cuenta["usuario"].model_copy(update=cambios)
        return cuenta["usuario"]

    def listar_usuarios(self):
        self._exigir("admin")
        return [cuenta["usuario"] for cuenta in self._cuentas.values()]

    def crear_estudiante(self, datos):
        self._exigir("admin")
        if datos.usuario in self._cuentas:
            raise ErrorCliente("rechazado", mensaje="Ya existe un usuario con ese nombre de usuario.")
        id_usuario = max(c["usuario"].id_usuario for c in self._cuentas.values()) + 1
        usuario = Usuario(id_usuario=id_usuario, nombre=datos.nombre, usuario=datos.usuario, rol="estudiante",
                          debe_cambiar_contrasena=True, temas=datos.temas)
        self._cuentas[datos.usuario] = {"contrasena": datos.contrasena_temporal, "usuario": usuario}
        return usuario

    def restablecer_contrasena(self, id_usuario, contrasena_temporal):
        cuenta = self._cuenta_de_estudiante(id_usuario)
        cuenta["contrasena"] = contrasena_temporal
        return self._actualizar(cuenta, debe_cambiar_contrasena=True)

    def cambiar_activo(self, id_usuario, activo):
        return self._actualizar(self._cuenta_de_estudiante(id_usuario), activo=activo)

    def cambiar_temas(self, usuario, temas):
        self._actualizar(self._cuenta_de_estudiante(usuario.id_usuario), temas=list(temas))

    def desbloquear(self, id_usuario):
        self._cuenta_de_estudiante(id_usuario)  # el mock no bloquea por intentos: solo revisa permisos

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
            raise ErrorCliente("sin_contexto", "422 SIN_CONTEXTO (simulado)")
        paquete = self._leer(MOCK_POR_FORMATO[solicitud.formato_salida])
        metadatos = paquete.metadatos.model_copy(update={
            "perfil_aplicado": solicitud.perfil_destinatario,
            "nicho_sector": tema.nicho_sector,  # como Backend: el sector sale del tema
        })
        # Id nuevo en cada generación, como la API: si se repite, las vistas
        # interactivas heredan el estado del paquete anterior (quiz ya calificado, etc.)
        paquete = paquete.model_copy(update={"metadatos": metadatos, "id": uuid4().hex, "id_tema": tema.id_tema,
                                             "creado_en": datetime.now(timezone.utc)})
        pedido = solicitud.tema or tema.nombre
        if solicitud.formato_salida != "Guion":
            self._generados[paquete.id] = (paquete, usuario.usuario, pedido)
            return paquete
        # Para la demo: un guion sí y otro no cae en revisión, así se ven los dos casos
        self._guiones_generados += 1
        if self._guiones_generados % 2 == 1:
            self._pendientes[paquete.id] = (paquete, pedido)
            self._generados[paquete.id] = (paquete, usuario.usuario, pedido)
            return MaterialEnRevision(id=paquete.id, creado_en=paquete.creado_en)  # como el 202 de la API
        calidad = paquete.evaluacion_calidad.model_copy(update={"anclaje_fuente_score": 0.9})
        paquete = paquete.model_copy(update={"status": "exito", "evaluacion_calidad": calidad})
        self._generados[paquete.id] = (paquete, usuario.usuario, pedido)
        return paquete

    def _visible_para(self, id_paquete, usuario):
        """Como Backend: quien estudia ve solo lo suyo, sin lo pendiente ni lo rechazado."""
        paquete, dueno, _ = self._generados[id_paquete]
        return (dueno == usuario.usuario and id_paquete not in self._pendientes
                and id_paquete not in self._eliminados)

    def listar_mi_material(self, id_tema):
        usuario = self._exigir("estudiante")
        return [
            ResumenPaquete(id=p.id, titulo=p.contenido_adaptado.titulo, creado_en=p.creado_en, tema=pedido,
                           formato=p.metadatos.formato_generado,
                           anclaje_fuente_score=p.evaluacion_calidad.anclaje_fuente_score)
            for id_paquete, (p, _, pedido) in self._generados.items()
            if p.id_tema == id_tema and self._visible_para(id_paquete, usuario)
        ]

    def obtener_paquete(self, id_paquete):
        usuario = self._exigir()
        if usuario.rol == "estudiante":
            if id_paquete in self._generados and self._visible_para(id_paquete, usuario):
                return self._generados[id_paquete][0]
            raise ErrorCliente("no_encontrado", f"No existe el paquete {id_paquete}")
        if id_paquete in self._generados and id_paquete not in self._eliminados:
            return self._generados[id_paquete][0]
        if id_paquete in self._pendientes:
            return self._pendientes[id_paquete][0]
        if id_paquete in self._aprobados:
            return self._aprobados[id_paquete]
        for paquete in self._todos():
            if paquete.id == id_paquete and id_paquete not in self._eliminados:
                return paquete
        raise ErrorCliente("no_encontrado", f"No existe el paquete {id_paquete}")

    def listar_paquetes_revision(self):
        self._exigir("admin")
        return [
            ResumenPaquete(
                id=p.id,
                creado_en=p.creado_en,
                tema=pedido,
                formato=p.metadatos.formato_generado,
                anclaje_fuente_score=p.evaluacion_calidad.anclaje_fuente_score,
            )
            for p, pedido in self._pendientes.values()
        ]

    def _sacar_de_pendientes(self, id_paquete):
        self._exigir("admin")
        if id_paquete not in self._pendientes:
            raise ErrorCliente("rechazado", f"{id_paquete} no está pendiente",
                               mensaje="El material ya no está pendiente de revisión.")
        return self._pendientes.pop(id_paquete)[0]

    def aprobar_paquete(self, id_paquete):
        """El material queda visible para quien lo pidió."""
        paquete = self._sacar_de_pendientes(id_paquete)
        self._aprobados[id_paquete] = paquete
        return paquete

    def rechazar_paquete(self, id_paquete):
        """El material se elimina; quien lo pidió puede generar otro."""
        self._sacar_de_pendientes(id_paquete)
        self._eliminados.add(id_paquete)

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


def _codigo_y_mensaje(respuesta):
    """Lee {"status": "error", "error": {"codigo", "mensaje"}} del backend; (None, None) si el cuerpo no sirve."""
    try:
        error = respuesta.json().get("error")
    except (ValueError, AttributeError):
        return None, None
    if not isinstance(error, dict):
        return None, None
    codigo, mensaje = error.get("codigo"), error.get("mensaje")
    return (codigo if isinstance(codigo, str) else None,
            mensaje if isinstance(mensaje, str) and mensaje.strip() else None)


def _minutos_de_espera(respuesta):
    """Minutos del Retry-After de un 429 (redondeando hacia arriba), o None si no viene un número válido."""
    try:
        segundos = int(respuesta.headers.get("Retry-After", ""))
    except ValueError:
        return None
    return max(1, math.ceil(segundos / 60)) if segundos >= 0 else None


def _mensaje_de_espera(minutos):
    if minutos is None:
        return None  # el mensaje por defecto: "en unos minutos"
    return f"Demasiados intentos. Intenta de nuevo en {minutos} {'minuto' if minutos == 1 else 'minutos'}."


class ClienteHttp:
    """Llama a la API del Backend (rutas /api/v1). Traduce cualquier falla a ErrorCliente.

    El token vive en este objeto, que a su vez vive en st.session_state: nunca va en la URL ni en logs.
    """

    es_mock = False

    def __init__(self, url, tiempo_maximo=300, sesion=None):
        self._url = url.rstrip("/")
        self._tiempo_maximo = tiempo_maximo
        self._sesion = sesion or requests.Session()
        self._token = None

    def _pedir_con_estado(self, metodo, ruta, tiempo=None, mensajes=None, **kwargs):
        """Devuelve (código HTTP, JSON). `mensajes`: código HTTP → texto para la persona, si la ruta lo necesita."""
        cabeceras = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            respuesta = self._sesion.request(metodo, self._url + ruta, headers=cabeceras,
                                             timeout=tiempo or TIEMPO_CORTO_SEGUNDOS, **kwargs)
        except requests.Timeout as error:  # va antes: Timeout también es RequestException
            raise ErrorCliente("tiempo_agotado", str(error)) from error
        except requests.RequestException as error:
            raise ErrorCliente("no_disponible", str(error)) from error
        estado = respuesta.status_code
        if estado >= 400:
            codigo, mensaje = _codigo_y_mensaje(respuesta)
            detalle = f"{estado} {codigo or ''}: {mensaje or respuesta.text[:200]}"
            propio = (mensajes or {}).get(estado)
            raise self._error(metodo, ruta, estado, codigo, mensaje, detalle, propio, respuesta)
        if estado == 204 or not respuesta.content:
            return estado, None
        try:
            return estado, respuesta.json()
        except ValueError as error:
            raise ErrorCliente("respuesta_invalida", f"La respuesta no es JSON: {respuesta.text[:200]}") from error

    def _pedir(self, metodo, ruta, **kwargs):
        return self._pedir_con_estado(metodo, ruta, **kwargs)[1]

    @staticmethod
    def _error(metodo, ruta, estado, codigo, mensaje, detalle, propio, respuesta):
        if propio:
            return ErrorCliente("rechazado", detalle, mensaje=propio)
        if estado == 401:
            return ErrorCliente("credenciales" if (metodo, ruta) == ("POST", "/api/v1/sesion") else "sesion_vencida",
                                detalle)
        if estado == 403:
            return ErrorCliente("sin_permiso", detalle)
        if estado == 404:
            return ErrorCliente("no_encontrado", detalle)
        if estado == 429:
            return ErrorCliente("demasiados_intentos", detalle, mensaje=_mensaje_de_espera(_minutos_de_espera(respuesta)))
        if codigo == "SIN_CONTEXTO":
            return ErrorCliente("sin_contexto", detalle)
        if codigo == "SIN_DOCUMENTOS_ASOCIADOS":
            return ErrorCliente("sin_documentos", detalle)
        if estado in (400, 409, 413, 415, 422):  # 413/415: archivo muy grande o de un tipo que no se acepta
            # "Revisa los campos: body.x" es técnico: se muestra el mensaje general y el detalle queda para el admin
            return ErrorCliente("rechazado", detalle, mensaje=None if codigo == "ENTRADA_INVALIDA" else mensaje)
        if estado == 502:
            return ErrorCliente("respuesta_invalida", detalle)
        if estado == 503:
            return ErrorCliente("no_disponible", detalle)
        return ErrorCliente("rechazado", detalle)

    def _validar(self, modelo, datos):
        try:
            return modelo.model_validate(datos)
        except ValidationError as error:
            raise ErrorCliente("respuesta_invalida", str(error)) from error

    def _lista(self, modelo, datos):
        if not isinstance(datos, list):
            raise ErrorCliente("respuesta_invalida", f"Se esperaba una lista y llegó: {type(datos).__name__}")
        return [self._validar(modelo, elemento) for elemento in datos]

    def _items(self, datos):
        """Los listados del backend vienen como {"items", "total", "limit", "offset"}."""
        if not isinstance(datos, dict) or not isinstance(datos.get("items"), list):
            raise ErrorCliente("respuesta_invalida", f"Se esperaba un listado y llegó: {type(datos).__name__}")
        return datos["items"]

    def _documento(self, datos):
        if not isinstance(datos, dict):
            raise ErrorCliente("respuesta_invalida", f"Se esperaba un documento y llegó: {type(datos).__name__}")
        return self._validar(Documento, {**datos, "titulo": datos.get("documento_titulo"),
                                         "fragmentos": datos.get("fragmentos_extraidos")})

    # --- Sesión ---
    def salud(self):
        try:
            self._pedir("GET", "/health", tiempo=TIEMPO_SALUD_SEGUNDOS)
            return True
        except ErrorCliente:
            return False

    def iniciar_sesion(self, usuario, contrasena):
        datos = self._pedir("POST", "/api/v1/sesion", json={"usuario": usuario, "contrasena": contrasena})
        sesion = self._validar(Sesion, datos)
        self._token = sesion.token
        return sesion

    def cerrar_sesion(self):
        try:
            if self._token:
                self._pedir("DELETE", "/api/v1/sesion")
        finally:
            self._token = None  # aunque la API falle, aquí la sesión se cierra

    def cambiar_contrasena(self, actual, nueva):
        self._pedir("PUT", "/api/v1/sesion/contrasena",
                    json={"contrasena_actual": actual, "contrasena_nueva": nueva})
        self._token = None  # el backend cierra todas las sesiones de la persona

    # --- Usuarios ---
    def listar_usuarios(self):
        return self._lista(Usuario, self._pedir("GET", "/api/v1/usuarios"))

    def crear_estudiante(self, datos):
        creado = self._pedir("POST", "/api/v1/usuarios", json=datos.model_dump(),
                             mensajes={409: "Ya existe un usuario con ese nombre de usuario."})
        return self._validar(Usuario, creado)

    def _actualizar_estudiante(self, id_usuario, cambios):
        return self._validar(Usuario, self._pedir("PUT", f"/api/v1/usuarios/{_en_ruta(id_usuario)}", json=cambios))

    def restablecer_contrasena(self, id_usuario, contrasena_temporal):
        return self._actualizar_estudiante(id_usuario, {"contrasena_temporal": contrasena_temporal})

    def cambiar_activo(self, id_usuario, activo):
        return self._actualizar_estudiante(id_usuario, {"activo": activo})

    def cambiar_temas(self, usuario, temas):
        for id_tema in (t for t in temas if t not in usuario.temas):
            self._pedir("PUT", f"/api/v1/temas/{_en_ruta(id_tema)}/estudiantes/{_en_ruta(usuario.id_usuario)}")
        for id_tema in (t for t in usuario.temas if t not in temas):
            self._pedir("DELETE", f"/api/v1/temas/{_en_ruta(id_tema)}/estudiantes/{_en_ruta(usuario.id_usuario)}")

    def desbloquear(self, id_usuario):
        self._pedir("POST", f"/api/v1/usuarios/{_en_ruta(id_usuario)}/desbloqueo")

    # --- Temas ---
    def _documentos_del_tema(self, id_tema):
        datos = self._pedir("GET", f"/api/v1/temas/{_en_ruta(id_tema)}/documentos")
        if not isinstance(datos, list):
            raise ErrorCliente("respuesta_invalida", f"Se esperaba una lista y llegó: {type(datos).__name__}")
        return [DocumentoTema(id=d.id, titulo=d.titulo) for d in map(self._documento, datos)]

    def _tema(self, datos):
        if not isinstance(datos, dict):
            raise ErrorCliente("respuesta_invalida", f"Se esperaba un tema y llegó: {type(datos).__name__}")
        # GET /temas no trae los documentos: se piden aparte
        return self._validar(Tema, {**datos, "documentos": self._documentos_del_tema(datos.get("id_tema"))})

    def listar_temas(self):
        datos = self._pedir("GET", "/api/v1/temas")
        if not isinstance(datos, list):
            raise ErrorCliente("respuesta_invalida", f"Se esperaba una lista y llegó: {type(datos).__name__}")
        return [self._tema(tema) for tema in datos]

    def crear_tema(self, datos):
        cuerpo = {"id_tema": id_tema_desde_nombre(datos.nombre), **datos.model_dump()}
        # El id sale del nombre: un 409 quiere decir que ya hay un tema que se llama igual
        creado = self._pedir("POST", "/api/v1/temas", json=cuerpo, mensajes={409: "Ya existe un tema con ese nombre."})
        return self._tema(creado)

    def editar_tema(self, id_tema, datos):
        ruta = f"/api/v1/temas/{_en_ruta(id_tema)}"
        antes = [d.id for d in self._documentos_del_tema(id_tema)]
        editado = self._pedir("PATCH", ruta, json={"nombre": datos.nombre, "descripcion": datos.descripcion,
                                                   "nicho_sector": datos.nicho_sector})
        for id_documento in (d for d in datos.documentos if d not in antes):
            self._pedir("PUT", f"{ruta}/documentos/{_en_ruta(id_documento)}")
        for id_documento in (d for d in antes if d not in datos.documentos):
            self._pedir("DELETE", f"{ruta}/documentos/{_en_ruta(id_documento)}")
        return self._tema(editado)

    def retirar_tema(self, id_tema):
        self._pedir("DELETE", f"/api/v1/temas/{_en_ruta(id_tema)}")

    # --- Material ---
    def generar_paquete(self, solicitud):
        cuerpo = solicitud.model_dump(exclude={"tema"} if not solicitud.tema else None)
        estado, datos = self._pedir_con_estado("POST", "/api/v1/contenidos", tiempo=self._tiempo_maximo, json=cuerpo)
        if estado == 202:  # no pasó la revisión de calidad: queda para el admin
            return self._validar(MaterialEnRevision, datos)
        return self._validar(Paquete, datos)

    def obtener_paquete(self, id_paquete):
        return self._validar(Paquete, self._pedir("GET", f"/api/v1/contenidos/{_en_ruta(id_paquete)}"))

    def _resumenes(self, datos):
        return [self._validar(ResumenPaquete, {**item, "formato": item.get("formato_generado")}
                              if isinstance(item, dict) else item) for item in self._items(datos)]

    def listar_paquetes_revision(self):
        return self._resumenes(self._pedir("GET", "/api/v1/contenidos", params={"pendiente": "true", "limit": 100}))

    def listar_mi_material(self, id_tema):
        # Para quien estudia, Backend devuelve solo lo suyo y visible
        return self._resumenes(self._pedir("GET", "/api/v1/contenidos", params={"id_tema": id_tema, "limit": 100}))

    def aprobar_paquete(self, id_paquete):
        return self._validar(Paquete, self._pedir("POST", f"/api/v1/contenidos/{_en_ruta(id_paquete)}/aprobar"))

    def rechazar_paquete(self, id_paquete):
        self._pedir("POST", f"/api/v1/contenidos/{_en_ruta(id_paquete)}/rechazar")

    # --- Documentos y configuración ---
    def subir_documento(self, nombre, contenido):
        datos = self._pedir("POST", "/api/v1/documentos", tiempo=self._tiempo_maximo,
                            files={"archivo": (nombre, contenido)})
        return self._documento(datos)

    def listar_documentos(self):
        return [self._documento(d) for d in self._items(self._pedir("GET", "/api/v1/documentos",
                                                                    params={"limit": 100}))]

    def obtener_configuracion(self):
        try:
            return self._validar(Configuracion, self._pedir("GET", "/api/v1/configuracion"))
        except ErrorCliente as error:
            if error.tipo == "no_encontrado":  # Backend todavía no tiene la ruta: se usa el sector por defecto
                return Configuracion()
            raise

    def guardar_configuracion(self, sector):
        datos = self._pedir("PUT", "/api/v1/configuracion", json={"sector": sector},
                            mensajes={404: "Esta opción todavía no está disponible en el servidor."})
        return self._validar(Configuracion, datos)


def obtener_cliente():
    """Elige el cliente según MODO_API (por defecto, mock)."""
    load_dotenv()
    if os.getenv("MODO_API", "mock").strip().lower() == "http":
        return ClienteHttp(
            url=os.getenv("URL_API", "http://localhost:8000"),
            tiempo_maximo=float(os.getenv("TIEMPO_MAXIMO_SEGUNDOS", "300")),
        )
    return ClienteMock()
