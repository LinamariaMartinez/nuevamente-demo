"""Pruebas de app/cliente_api.py: modo mock y modo http con una sesión falsa. No necesitan la API."""

import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "app"))

import requests

from cliente_api import TIEMPO_CORTO_SEGUNDOS, ClienteHttp, ClienteMock, ErrorCliente, obtener_cliente
from contrato import FORMATOS, PERFILES, DatosEstudiante, DatosTema, MaterialEnRevision, SolicitudPaquete, Usuario

MOCKS = RAIZ / "app" / "mocks"


def solicitud(**cambios):
    datos = {"id_tema": "t-redes", "tema": "Redes VCN", "perfil_destinatario": PERFILES[1], "formato_salida": "Quiz"}
    datos.update(cambios)
    return SolicitudPaquete(**datos)


CUENTAS = {"laura": "demo-estudiante", "mateo": "temporal-123", "admin": "demo-admin"}


def con_sesion(usuario, cliente=None):
    cliente = cliente or ClienteMock()
    cliente.iniciar_sesion(usuario, CUENTAS[usuario])
    return cliente


def respuesta(status=200, cuerpo=None, texto=None, cabeceras=None):
    r = requests.Response()
    r.status_code = status
    r.encoding = "utf-8"
    r._content = (json.dumps(cuerpo) if texto is None else texto).encode("utf-8")
    r.headers.update(cabeceras or {})
    return r


def error(status, codigo, mensaje="Mensaje del backend.", cabeceras=None):
    """Un error con el formato del backend integrado."""
    return respuesta(status=status, cuerpo={"status": "error", "error": {"codigo": codigo, "mensaje": mensaje}},
                     cabeceras=cabeceras)


class SesionFalsa:
    def __init__(self, respuesta=None, excepcion=None, respuestas=None):
        self.respuestas = list(respuestas) if respuestas is not None else None
        self.respuesta = respuesta
        self.excepcion = excepcion
        self.llamadas = []

    def request(self, metodo, url, **kwargs):
        self.llamadas.append((metodo, url, kwargs))
        if self.excepcion is not None:
            raise self.excepcion
        if self.respuestas is not None:
            return self.respuestas.pop(0)
        return self.respuesta


SESION_JSON = {"token": "tok-123", "usuario": {"id_usuario": 1, "nombre": "Ana", "usuario": "ana",
                                               "rol": "admin", "temas": []}}
TEMA_JSON = {"id_tema": "t-1", "nombre": "Redes", "descripcion": "", "nicho_sector": "General",
             "nivel_detalle": "Didáctico"}
ID_A, ID_B = "a" * 32, "b" * 32
DOCUMENTO_JSON = {"id": ID_A, "documento_titulo": "Redes VCN", "nombre_archivo": "redes.pdf", "tipo": "pdf",
                  "tamano_bytes": 10, "fragmentos_extraidos": 3, "creado_en": "2026-10-19T15:00:00Z"}
DOCUMENTO_B_JSON = {**DOCUMENTO_JSON, "id": ID_B, "documento_titulo": "Nube"}
CONTENIDO_JSON = {"id": "c" * 32, "documento_id": None, "id_tema": "t-redes", "id_usuario": 2, "titulo": "Guion",
                  "tema": "subredes", "perfil_aplicado": "Intermedio", "formato_generado": "Guion",
                  "status": "requiere_revision", "anclaje_fuente_score": 0.6, "creado_en": "2026-10-19T15:00:00Z",
                  "aprobado_en": None}


def listado(*items):
    return {"items": list(items), "total": len(items), "limit": 100, "offset": 0}


def paquete_json(nombre="quiz.json"):
    return json.loads((MOCKS / nombre).read_text(encoding="utf-8"))


class ModoMock(unittest.TestCase):
    def test_es_mock_y_esta_sano_sin_sesion(self):
        cliente = ClienteMock()
        self.assertTrue(cliente.es_mock)
        self.assertTrue(cliente.salud())

    # --- Sesión ---
    def test_inicio_correcto_devuelve_token_y_usuario(self):
        sesion = ClienteMock().iniciar_sesion("laura", "demo-estudiante")
        self.assertTrue(sesion.token)
        self.assertEqual((sesion.usuario.nombre, sesion.usuario.rol), ("Laura Gómez", "estudiante"))

    def test_contrasena_mala_y_usuario_inexistente_dan_el_mismo_error(self):
        for usuario, contrasena in (("laura", "otra"), ("nadie", "demo-estudiante")):
            with self.subTest(usuario=usuario), self.assertRaises(ErrorCliente) as ctx:
                ClienteMock().iniciar_sesion(usuario, contrasena)
            self.assertEqual(ctx.exception.tipo, "credenciales")

    def test_sin_sesion_pide_iniciarla(self):
        with self.assertRaises(ErrorCliente) as ctx:
            ClienteMock().listar_temas()
        self.assertEqual(ctx.exception.tipo, "sesion_vencida")

    def test_cerrar_sesion(self):
        cliente = con_sesion("laura")
        cliente.cerrar_sesion()
        with self.assertRaises(ErrorCliente):
            cliente.listar_temas()

    def test_cambiar_contrasena(self):
        cliente = con_sesion("mateo")
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.cambiar_contrasena("equivocada", "nueva-clave-1")
        self.assertEqual(ctx.exception.mensaje, "La contraseña actual no es correcta.")
        cliente.cambiar_contrasena("temporal-123", "nueva-clave-1")
        with self.assertRaises(ErrorCliente) as ctx:  # como el backend: se cierran las sesiones
            cliente.listar_temas()
        self.assertEqual(ctx.exception.tipo, "sesion_vencida")
        sesion = cliente.iniciar_sesion("mateo", "nueva-clave-1")
        self.assertFalse(sesion.usuario.debe_cambiar_contrasena)

    def test_cambiar_contrasena_pide_12_caracteres_y_una_distinta(self):
        cliente = con_sesion("mateo")
        for nueva, mensaje in (("corta-11ch.", "La nueva contraseña debe tener al menos 12 caracteres."),
                               ("temporal-123", "La nueva contraseña debe ser diferente.")):
            with self.subTest(nueva=nueva), self.assertRaises(ErrorCliente) as ctx:
                cliente.cambiar_contrasena("temporal-123", nueva)
            self.assertEqual(ctx.exception.mensaje, mensaje)

    # --- Temas y permisos ---
    def test_estudiante_ve_solo_sus_temas_y_admin_todos(self):
        self.assertEqual([t.id_tema for t in con_sesion("laura").listar_temas()], ["t-redes", "t-seguridad"])
        self.assertEqual(len(con_sesion("admin").listar_temas()), 3)

    def test_estudiante_no_usa_rutas_de_admin(self):
        cliente = con_sesion("laura")
        for llamada in (cliente.listar_documentos, cliente.listar_paquetes_revision,
                        lambda: cliente.guardar_configuracion("Salud"),
                        lambda: cliente.crear_tema(DatosTema(nombre="X", documentos=["d-datos"]))):
            with self.subTest(llamada=llamada), self.assertRaises(ErrorCliente) as ctx:
                llamada()
            self.assertEqual(ctx.exception.tipo, "sin_permiso")

    def test_crear_editar_y_retirar_tema(self):
        cliente = con_sesion("admin")
        tema = cliente.crear_tema(DatosTema(nombre="Bases de datos", documentos=["d-datos"]))
        self.assertEqual(tema.id_tema, "bases-de-datos")
        self.assertEqual([d.titulo for d in tema.documentos], ["Guía de herramientas de datos"])
        self.assertIn(tema.id_tema, [t.id_tema for t in cliente.listar_temas()])
        editado = cliente.editar_tema(tema.id_tema, DatosTema(nombre="Bases de datos SQL",
                                                              documentos=["d-datos", "d-nube"]))
        self.assertEqual((editado.id_tema, editado.nombre), ("bases-de-datos", "Bases de datos SQL"))
        self.assertEqual([d.id for d in editado.documentos], ["d-datos", "d-nube"])
        cliente.retirar_tema(tema.id_tema)
        self.assertNotIn(tema.id_tema, [t.id_tema for t in cliente.listar_temas()])

    def test_nombre_repetido_no_crea_duplicado(self):
        cliente = con_sesion("admin")
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.crear_tema(DatosTema(nombre="redes en oci", documentos=["d-datos"]))
        self.assertEqual((ctx.exception.tipo, ctx.exception.mensaje), ("rechazado", "Ya existe un tema con ese nombre."))
        self.assertEqual(len(cliente.listar_temas()), 3)

    def test_documento_inexistente_no_sirve_para_un_tema(self):
        with self.assertRaises(ErrorCliente) as ctx:
            con_sesion("admin").crear_tema(DatosTema(nombre="Escaneos", documentos=["d-no-existe"]))
        self.assertEqual(ctx.exception.mensaje, "Elige solo documentos ya subidos.")

    def test_retirar_un_tema_lo_quita_de_quien_lo_tenia(self):
        cliente = con_sesion("admin")
        cliente.retirar_tema("t-redes")
        cliente.cerrar_sesion()
        cliente.iniciar_sesion("laura", "demo-estudiante")
        self.assertEqual([t.id_tema for t in cliente.listar_temas()], ["t-seguridad"])

    def test_tema_inexistente_es_no_encontrado(self):
        with self.assertRaises(ErrorCliente) as ctx:
            con_sesion("admin").retirar_tema("t-no-existe")
        self.assertEqual(ctx.exception.tipo, "no_encontrado")

    # --- Usuarios ---
    def nuevo(self, cliente, usuario="ana", temas=("t-redes",)):
        return cliente.crear_estudiante(DatosEstudiante(nombre="Ana Pérez", usuario=usuario,
                                                        contrasena_temporal="Temporal-2026", temas=list(temas)))

    def test_crear_estudiante_y_entrar_con_la_temporal(self):
        cliente = con_sesion("admin")
        ana = self.nuevo(cliente)
        self.assertEqual((ana.rol, ana.debe_cambiar_contrasena, ana.temas), ("estudiante", True, ["t-redes"]))
        self.assertIn("ana", [u.usuario for u in cliente.listar_usuarios()])
        self.assertTrue(cliente.iniciar_sesion("ana", "Temporal-2026").usuario.debe_cambiar_contrasena)

    def test_usuario_repetido_no_se_crea(self):
        cliente = con_sesion("admin")
        with self.assertRaises(ErrorCliente) as ctx:
            self.nuevo(cliente, usuario="laura")
        self.assertEqual((ctx.exception.tipo, ctx.exception.mensaje),
                         ("rechazado", "Ya existe un usuario con ese nombre de usuario."))

    def test_restablecer_contrasena_pide_cambiarla(self):
        cliente = con_sesion("admin")
        laura = cliente.restablecer_contrasena(1, "Nueva-temporal-1")
        self.assertTrue(laura.debe_cambiar_contrasena)
        self.assertTrue(cliente.iniciar_sesion("laura", "Nueva-temporal-1").usuario.debe_cambiar_contrasena)

    def test_desactivar_impide_entrar_y_activar_lo_devuelve(self):
        cliente = con_sesion("admin")
        self.assertFalse(cliente.cambiar_activo(1, False).activo)
        with self.assertRaises(ErrorCliente):
            cliente.iniciar_sesion("laura", "demo-estudiante")
        cliente.iniciar_sesion("admin", "demo-admin")
        self.assertTrue(cliente.cambiar_activo(1, True).activo)

    def test_cambiar_temas_del_estudiante(self):
        cliente = con_sesion("admin")
        laura = next(u for u in cliente.listar_usuarios() if u.usuario == "laura")
        cliente.cambiar_temas(laura, ["t-datos"])
        self.assertEqual(next(u for u in cliente.listar_usuarios() if u.usuario == "laura").temas, ["t-datos"])

    def test_desbloquear_no_falla_en_el_mock(self):
        self.assertIsNone(con_sesion("admin").desbloquear(1))

    def test_acciones_sobre_un_admin_no_existen(self):
        cliente = con_sesion("admin")
        for accion in (lambda: cliente.restablecer_contrasena(3, "Nueva-temporal-1"),
                       lambda: cliente.cambiar_activo(3, False), lambda: cliente.desbloquear(3)):
            with self.subTest(accion=accion), self.assertRaises(ErrorCliente) as ctx:
                accion()
            self.assertEqual(ctx.exception.tipo, "no_encontrado")

    def test_estudiante_no_administra_usuarios(self):
        cliente = con_sesion("laura")
        for accion in (cliente.listar_usuarios, lambda: self.nuevo(cliente, usuario="otra"),
                       lambda: cliente.desbloquear(2)):
            with self.subTest(accion=accion), self.assertRaises(ErrorCliente) as ctx:
                accion()
            self.assertEqual(ctx.exception.tipo, "sin_permiso")

    # --- Generar material ---
    def test_genera_un_paquete_por_formato_con_lo_que_pidio_el_estudiante(self):
        cliente = con_sesion("laura")
        for formato in ("Tutorial", "Flashcards", "Quiz", "Resumen"):
            with self.subTest(formato=formato):
                paquete = cliente.generar_paquete(solicitud(formato_salida=formato))
                self.assertEqual(paquete.metadatos.formato_generado, formato)
                self.assertEqual(paquete.id_tema, "t-redes")
                self.assertEqual(paquete.status, "exito")
                self.assertEqual(paquete.metadatos.perfil_aplicado, PERFILES[1])
                self.assertEqual(paquete.metadatos.nicho_sector, "General")  # el sector de t-redes

    def test_genera_con_el_sector_del_tema(self):
        paquete = con_sesion("laura").generar_paquete(solicitud(id_tema="t-seguridad"))
        self.assertEqual(paquete.metadatos.nicho_sector, "Salud")

    def test_el_sector_se_guarda_en_el_tema(self):
        cliente = con_sesion("admin")
        tema = cliente.crear_tema(DatosTema(nombre="Pagos", documentos=["d-datos"], nicho_sector="Fintech"))
        self.assertEqual(tema.nicho_sector, "Fintech")
        editado = cliente.editar_tema(tema.id_tema, DatosTema(nombre="Pagos", documentos=["d-datos"],
                                                              nicho_sector="E-commerce"))
        self.assertEqual(editado.nicho_sector, "E-commerce")

    def test_tema_no_asignado_no_genera(self):
        with self.assertRaises(ErrorCliente) as ctx:
            con_sesion("laura").generar_paquete(solicitud(id_tema="t-datos"))
        self.assertEqual(ctx.exception.tipo, "sin_permiso")

    def test_cada_generacion_tiene_un_id_nuevo(self):
        # Si dos paquetes comparten id, sus vistas interactivas comparten estado (quiz ya calificado, etc.)
        cliente = con_sesion("laura")
        primero = cliente.generar_paquete(solicitud(formato_salida="Quiz"))
        segundo = cliente.generar_paquete(solicitud(formato_salida="Quiz"))
        self.assertNotEqual(primero.id, segundo.id)
        self.assertEqual(len(primero.id), 32)  # como los ids del backend

    def test_tema_inexistente_lanza_sin_contexto(self):
        with self.assertRaises(ErrorCliente) as ctx:
            con_sesion("laura").generar_paquete(solicitud(tema="Tema inexistente"))
        self.assertEqual(ctx.exception.tipo, "sin_contexto")
        self.assertEqual(ctx.exception.mensaje,
                         "No encontramos ese tema en los documentos cargados. Prueba con otras palabras.")

    def test_guion_en_revision_devuelve_material_en_revision(self):
        # Para la demo: el primer guion cae en revisión y "Generar otra versión" trae uno aprobado
        cliente = con_sesion("laura")
        en_revision = [isinstance(cliente.generar_paquete(solicitud(formato_salida="Guion")), MaterialEnRevision)
                       for _ in range(3)]
        self.assertEqual(en_revision, [True, False, True])

    def test_guion_aprobado_trae_status_exito(self):
        cliente = con_sesion("laura")
        cliente.generar_paquete(solicitud(formato_salida="Guion"))
        self.assertEqual(cliente.generar_paquete(solicitud(formato_salida="Guion")).status, "exito")

    # --- Mi material ---
    def test_mi_material_lista_lo_que_genero_en_el_tema(self):
        cliente = con_sesion("laura")
        primero = cliente.generar_paquete(solicitud(formato_salida="Quiz"))
        cliente.generar_paquete(solicitud(formato_salida="Resumen", id_tema="t-seguridad"))
        material = cliente.listar_mi_material("t-redes")
        self.assertEqual([(m.id, m.formato, m.titulo) for m in material],
                         [(primero.id, "Quiz", primero.contenido_adaptado.titulo)])
        self.assertEqual(cliente.obtener_paquete(primero.id).id, primero.id)  # puede abrir lo suyo

    def test_mi_material_sin_lo_pendiente_hasta_que_se_aprueba(self):
        cliente = con_sesion("laura")
        pendiente = cliente.generar_paquete(solicitud(formato_salida="Guion"))
        self.assertEqual(cliente.listar_mi_material("t-redes"), [])
        cliente.cerrar_sesion()
        cliente.iniciar_sesion("admin", "demo-admin")
        cliente.aprobar_paquete(pendiente.id)
        cliente.cerrar_sesion()
        cliente.iniciar_sesion("laura", "demo-estudiante")
        self.assertEqual([m.id for m in cliente.listar_mi_material("t-redes")], [pendiente.id])

    def test_mi_material_sin_lo_rechazado(self):
        cliente = con_sesion("laura")
        pendiente = cliente.generar_paquete(solicitud(formato_salida="Guion"))
        cliente.cerrar_sesion()
        cliente.iniciar_sesion("admin", "demo-admin")
        cliente.rechazar_paquete(pendiente.id)
        cliente.cerrar_sesion()
        cliente.iniciar_sesion("laura", "demo-estudiante")
        self.assertEqual(cliente.listar_mi_material("t-redes"), [])

    def test_mi_material_no_muestra_lo_ajeno(self):
        cliente = con_sesion("laura")
        de_laura = cliente.generar_paquete(solicitud(formato_salida="Quiz"))
        cliente.cerrar_sesion()
        cliente.iniciar_sesion("mateo", "temporal-123")
        self.assertEqual(cliente.listar_mi_material("t-redes"), [])
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.obtener_paquete(de_laura.id)
        self.assertEqual(ctx.exception.tipo, "no_encontrado")

    # --- Admin ---
    def test_lista_de_revision_trae_solo_el_guion(self):
        self.assertEqual([r.formato for r in con_sesion("admin").listar_paquetes_revision()], ["Guion"])

    def test_guion_en_revision_aparece_en_la_lista_del_admin(self):
        cliente = con_sesion("laura")
        material = cliente.generar_paquete(solicitud(formato_salida="Guion", tema="subredes"))
        cliente.cerrar_sesion()
        cliente.iniciar_sesion("admin", "demo-admin")
        resumenes = cliente.listar_paquetes_revision()
        self.assertEqual(len(resumenes), 2)
        self.assertIn((material.id, "subredes"), [(r.id, r.tema) for r in resumenes])
        self.assertEqual(cliente.obtener_paquete(material.id).status, "requiere_revision")

    def test_aprobar_saca_de_pendientes(self):
        cliente = con_sesion("admin")
        id_guion = paquete_json("guion.json")["id"]
        self.assertEqual(cliente.aprobar_paquete(id_guion).id, id_guion)
        self.assertEqual(cliente.listar_paquetes_revision(), [])

    def test_rechazar_saca_de_pendientes(self):
        cliente = con_sesion("admin")
        id_guion = paquete_json("guion.json")["id"]
        self.assertIsNone(cliente.rechazar_paquete(id_guion))
        self.assertEqual(cliente.listar_paquetes_revision(), [])
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.obtener_paquete(id_guion)  # rechazado = eliminado
        self.assertEqual(ctx.exception.tipo, "no_encontrado")

    def test_aprobar_no_pendiente_rechazado(self):
        cliente = con_sesion("admin")
        for accion in (cliente.aprobar_paquete, cliente.rechazar_paquete):
            with self.subTest(accion=accion.__name__), self.assertRaises(ErrorCliente) as ctx:
                accion(paquete_json("quiz.json")["id"])
            self.assertEqual((ctx.exception.tipo, ctx.exception.mensaje),
                             ("rechazado", "El material ya no está pendiente de revisión."))

    def test_estudiante_no_puede_aprobar(self):
        cliente = con_sesion("laura")
        id_guion = paquete_json("guion.json")["id"]
        for accion in (cliente.aprobar_paquete, cliente.rechazar_paquete):
            with self.subTest(accion=accion.__name__), self.assertRaises(ErrorCliente) as ctx:
                accion(id_guion)
            self.assertEqual(ctx.exception.tipo, "sin_permiso")

    def test_obtener_paquete_existente_y_no_existente(self):
        cliente = con_sesion("admin")
        self.assertEqual(cliente.obtener_paquete(paquete_json("quiz.json")["id"]).metadatos.formato_generado, "Quiz")
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.obtener_paquete("no-existe")
        self.assertEqual(ctx.exception.tipo, "no_encontrado")

    def test_documentos_de_demostracion_y_subir_uno(self):
        cliente = con_sesion("admin")
        antes = cliente.listar_documentos()
        self.assertEqual([d.id for d in antes], ["d-redes", "d-nube", "d-datos"])
        documento = cliente.subir_documento("nuevo_manual.md", b"# Hola")
        self.assertEqual((documento.titulo, documento.nombre_archivo, documento.tipo, documento.fragmentos),
                         ("nuevo_manual", "nuevo_manual.md", "md", 1))
        self.assertEqual(len(cliente.listar_documentos()), len(antes) + 1)

    def test_sector_empieza_en_general_se_cambia_y_rechaza_valores_raros(self):
        cliente = con_sesion("admin")
        self.assertEqual(cliente.obtener_configuracion().sector, "General")
        self.assertEqual(cliente.guardar_configuracion("Salud").sector, "Salud")
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.guardar_configuracion("Minería")
        self.assertEqual(ctx.exception.tipo, "rechazado")
        self.assertEqual(cliente.obtener_configuracion().sector, "Salud")


class ModoHttp(unittest.TestCase):
    URL = "http://api.local"

    def cliente(self, **kwargs):
        sesion = SesionFalsa(**kwargs)
        return ClienteHttp("http://api.local/", tiempo_maximo=30, sesion=sesion), sesion

    def con_token(self, *respuestas):
        """Cliente que ya inició sesión; `respuestas` son las de las llamadas siguientes."""
        cliente, sesion = self.cliente(respuestas=[respuesta(cuerpo=SESION_JSON), *respuestas])
        cliente.iniciar_sesion("ana", "clave")
        return cliente, sesion

    def rutas(self, sesion, desde=1):
        return [(m, u.removeprefix(self.URL)) for m, u, _ in sesion.llamadas[desde:]]

    def error_de(self, accion, *respuestas):
        cliente, _ = self.con_token(*respuestas)
        with self.assertRaises(ErrorCliente) as ctx:
            accion(cliente)
        return ctx.exception

    # --- Sesión y token ---
    def test_iniciar_sesion_guarda_el_token_y_lo_envia_despues(self):
        cliente, sesion = self.con_token(respuesta(cuerpo=[TEMA_JSON]), respuesta(cuerpo=[DOCUMENTO_JSON]))
        temas = cliente.listar_temas()
        (m1, u1, k1), (m2, u2, k2) = sesion.llamadas[:2]
        self.assertEqual((m1, u1, k1["json"]),
                         ("POST", f"{self.URL}/api/v1/sesion", {"usuario": "ana", "contrasena": "clave"}))
        self.assertNotIn("Authorization", k1["headers"])
        self.assertEqual((m2, u2), ("GET", f"{self.URL}/api/v1/temas"))
        self.assertEqual(k2["headers"]["Authorization"], "Bearer tok-123")
        self.assertNotIn("tok-123", u2)  # el token nunca va en la URL
        self.assertEqual(temas[0].nombre, "Redes")

    def test_salud_usa_health(self):
        cliente, sesion = self.cliente(respuesta=respuesta(cuerpo={"status": "ok", "base_datos": "sqlite"}))
        self.assertTrue(cliente.salud())
        self.assertEqual(self.rutas(sesion, 0), [("GET", "/health")])

    def test_salud_es_false_si_la_api_no_responde(self):
        cliente, sesion = self.cliente(excepcion=requests.ConnectionError("caída"))
        self.assertFalse(cliente.salud())
        self.assertEqual(sesion.llamadas[0][2]["timeout"], 5)

    def test_401_en_inicio_es_credenciales_y_en_otra_ruta_sesion_vencida(self):
        cliente, _ = self.cliente(respuesta=error(401, "AUTENTICACION_REQUERIDA"))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.iniciar_sesion("ana", "mala")
        self.assertEqual(ctx.exception.tipo, "credenciales")
        fallo = self.error_de(lambda c: c.listar_temas(), error(401, "AUTENTICACION_REQUERIDA"))
        self.assertEqual(fallo.tipo, "sesion_vencida")

    def test_cerrar_sesion_borra_el_token_aunque_la_api_falle(self):
        cliente, sesion = self.con_token(respuesta(status=500, texto="caída"), respuesta(cuerpo=[]))
        with self.assertRaises(ErrorCliente):
            cliente.cerrar_sesion()
        self.assertEqual(self.rutas(sesion)[0], ("DELETE", "/api/v1/sesion"))
        cliente.listar_temas()
        self.assertNotIn("Authorization", sesion.llamadas[2][2]["headers"])

    def test_cambiar_contrasena_envia_los_campos_del_backend_y_borra_el_token(self):
        # El backend cierra todas las sesiones de la persona al cambiar la contraseña
        cliente, sesion = self.con_token(
            respuesta(cuerpo={"mensaje": "Contraseña actualizada correctamente", "sesiones_revocadas": True}),
            respuesta(cuerpo=[]))
        self.assertIsNone(cliente.cambiar_contrasena("vieja-123", "nueva-clave-12"))
        metodo, url, kwargs = sesion.llamadas[1]
        self.assertEqual((metodo, url, kwargs["json"]),
                         ("PUT", f"{self.URL}/api/v1/sesion/contrasena",
                          {"contrasena_actual": "vieja-123", "contrasena_nueva": "nueva-clave-12"}))
        cliente.listar_temas()
        self.assertNotIn("Authorization", sesion.llamadas[2][2]["headers"])

    def test_400_al_cambiar_la_contrasena_usa_el_mensaje_del_backend(self):
        fallo = self.error_de(lambda c: c.cambiar_contrasena("mala", "nueva-clave-12"),
                              error(400, "SOLICITUD_INVALIDA", "La contraseña actual es incorrecta"))
        self.assertEqual((fallo.tipo, fallo.mensaje), ("rechazado", "La contraseña actual es incorrecta"))

    # --- Demasiados intentos (429) ---
    def intento_bloqueado(self, cabeceras):
        cliente, _ = self.cliente(respuesta=error(429, "DEMASIADOS_INTENTOS", cabeceras=cabeceras))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.iniciar_sesion("ana", "clave")
        self.assertEqual(ctx.exception.tipo, "demasiados_intentos")
        return ctx.exception.mensaje

    def test_429_con_retry_after_60_dice_1_minuto(self):
        self.assertEqual(self.intento_bloqueado({"Retry-After": "60"}),
                         "Demasiados intentos. Intenta de nuevo en 1 minuto.")

    def test_429_con_retry_after_301_dice_6_minutos(self):
        self.assertEqual(self.intento_bloqueado({"Retry-After": "301"}),
                         "Demasiados intentos. Intenta de nuevo en 6 minutos.")

    def test_429_sin_retry_after(self):
        self.assertEqual(self.intento_bloqueado(None), "Demasiados intentos. Intenta de nuevo en unos minutos.")

    def test_429_retry_after_no_numerico(self):
        for valor in ("abc", "", "-5"):
            with self.subTest(valor=valor):
                self.assertEqual(self.intento_bloqueado({"Retry-After": valor}),
                                 "Demasiados intentos. Intenta de nuevo en unos minutos.")

    # --- Temas ---
    def test_listar_temas_trae_los_documentos_de_cada_tema(self):
        otro = {**TEMA_JSON, "id_tema": "t-2", "nombre": "Nube"}
        cliente, sesion = self.con_token(respuesta(cuerpo=[TEMA_JSON, otro]), respuesta(cuerpo=[DOCUMENTO_JSON]),
                                         respuesta(cuerpo=[]))
        temas = cliente.listar_temas()
        self.assertEqual(self.rutas(sesion), [("GET", "/api/v1/temas"), ("GET", "/api/v1/temas/t-1/documentos"),
                                              ("GET", "/api/v1/temas/t-2/documentos")])
        self.assertEqual([(d.id, d.titulo) for d in temas[0].documentos], [(ID_A, "Redes VCN")])
        self.assertEqual(temas[1].documentos, [])

    def test_crear_tema_arma_el_id_y_trae_los_titulos(self):
        creado = {**TEMA_JSON, "id_tema": "redes-en-oci", "nombre": "Redes en OCI", "documentos": [ID_A]}
        cliente, sesion = self.con_token(respuesta(status=201, cuerpo=creado), respuesta(cuerpo=[DOCUMENTO_JSON]))
        tema = cliente.crear_tema(DatosTema(nombre="Redes en OCI", documentos=[ID_A]))
        self.assertEqual(sesion.llamadas[1][2]["json"],
                         {"id_tema": "redes-en-oci", "nombre": "Redes en OCI", "descripcion": "", "documentos": [ID_A],
                          "nicho_sector": "General"})
        self.assertEqual(self.rutas(sesion), [("POST", "/api/v1/temas"),
                                              ("GET", "/api/v1/temas/redes-en-oci/documentos")])
        self.assertEqual((tema.id_tema, [d.titulo for d in tema.documentos]), ("redes-en-oci", ["Redes VCN"]))

    def test_crear_tema_repetido_avisa_con_el_nombre(self):
        fallo = self.error_de(lambda c: c.crear_tema(DatosTema(nombre="Redes", documentos=[ID_A])),
                              error(409, "CONFLICTO", "Ya existe un tema con ese identificador"))
        self.assertEqual((fallo.tipo, fallo.mensaje), ("rechazado", "Ya existe un tema con ese nombre."))

    def test_editar_tema_solo_toca_documentos_que_cambian(self):
        # Tenía A; queda con B: se agrega B y se quita A
        cliente, sesion = self.con_token(
            respuesta(cuerpo=[DOCUMENTO_JSON]), respuesta(cuerpo={**TEMA_JSON, "nombre": "Redes 2"}),
            respuesta(status=204, texto=""), respuesta(status=204, texto=""), respuesta(cuerpo=[DOCUMENTO_B_JSON]))
        tema = cliente.editar_tema("t-1", DatosTema(nombre="Redes 2", documentos=[ID_B]))
        self.assertEqual(self.rutas(sesion), [
            ("GET", "/api/v1/temas/t-1/documentos"), ("PATCH", "/api/v1/temas/t-1"),
            ("PUT", f"/api/v1/temas/t-1/documentos/{ID_B}"), ("DELETE", f"/api/v1/temas/t-1/documentos/{ID_A}"),
            ("GET", "/api/v1/temas/t-1/documentos")])
        self.assertEqual(sesion.llamadas[2][2]["json"], {"nombre": "Redes 2", "descripcion": "", "nicho_sector": "General"})
        self.assertEqual((tema.nombre, [d.id for d in tema.documentos]), ("Redes 2", [ID_B]))

    def test_editar_tema_sin_cambiar_documentos_no_los_toca(self):
        cliente, sesion = self.con_token(respuesta(cuerpo=[DOCUMENTO_JSON]), respuesta(cuerpo=TEMA_JSON),
                                         respuesta(cuerpo=[DOCUMENTO_JSON]))
        cliente.editar_tema("t-1", DatosTema(nombre="Redes", documentos=[ID_A]))
        self.assertEqual([m for m, _ in self.rutas(sesion)], ["GET", "PATCH", "GET"])

    def test_retirar_tema_con_id_codificado(self):
        cliente, sesion = self.con_token(respuesta(status=204, texto=""))
        self.assertIsNone(cliente.retirar_tema("t/1 a"))
        self.assertEqual(self.rutas(sesion), [("DELETE", "/api/v1/temas/t%2F1%20a")])

    # --- Usuarios ---
    USUARIO_JSON = {"id_usuario": 7, "nombre": "Ana Pérez", "usuario": "ana", "rol": "estudiante", "activo": True,
                    "debe_cambiar_contrasena": True, "temas": ["t-1"]}

    def test_listar_y_crear_estudiante(self):
        cliente, sesion = self.con_token(respuesta(cuerpo=[self.USUARIO_JSON]),
                                         respuesta(status=201, cuerpo=self.USUARIO_JSON))
        self.assertEqual([u.usuario for u in cliente.listar_usuarios()], ["ana"])
        cliente.crear_estudiante(DatosEstudiante(nombre="Ana Pérez", usuario="ana",
                                                 contrasena_temporal="Temporal-2026", temas=["t-1"]))
        self.assertEqual(self.rutas(sesion), [("GET", "/api/v1/usuarios"), ("POST", "/api/v1/usuarios")])
        self.assertEqual(sesion.llamadas[2][2]["json"], {"nombre": "Ana Pérez", "usuario": "ana",
                                                         "contrasena_temporal": "Temporal-2026", "temas": ["t-1"]})

    def test_usuario_repetido_avisa_con_su_mensaje(self):
        fallo = self.error_de(lambda c: c.crear_estudiante(DatosEstudiante(
            nombre="Ana", usuario="ana", contrasena_temporal="Temporal-2026")),
            error(409, "CONFLICTO", "El usuario ya existe o hay datos duplicados"))
        self.assertEqual(fallo.mensaje, "Ya existe un usuario con ese nombre de usuario.")

    def test_restablecer_y_activar_mandan_solo_su_campo(self):
        cliente, sesion = self.con_token(respuesta(cuerpo=self.USUARIO_JSON), respuesta(cuerpo=self.USUARIO_JSON))
        cliente.restablecer_contrasena(7, "Nueva-temporal-1")
        cliente.cambiar_activo(7, False)
        self.assertEqual(self.rutas(sesion), [("PUT", "/api/v1/usuarios/7"), ("PUT", "/api/v1/usuarios/7")])
        self.assertEqual([k["json"] for _, _, k in sesion.llamadas[1:]],
                         [{"contrasena_temporal": "Nueva-temporal-1"}, {"activo": False}])

    def test_cambiar_temas_solo_toca_lo_que_cambia(self):
        cliente, sesion = self.con_token(respuesta(status=204, texto=""), respuesta(status=204, texto=""))
        ana = Usuario.model_validate({**self.USUARIO_JSON, "temas": ["t-1", "t-2"]})
        cliente.cambiar_temas(ana, ["t-2", "t-3"])
        self.assertEqual(self.rutas(sesion), [("PUT", "/api/v1/temas/t-3/estudiantes/7"),
                                              ("DELETE", "/api/v1/temas/t-1/estudiantes/7")])

    def test_desbloquear(self):
        cliente, sesion = self.con_token(respuesta(status=204, texto=""))
        self.assertIsNone(cliente.desbloquear(7))
        self.assertEqual(self.rutas(sesion), [("POST", "/api/v1/usuarios/7/desbloqueo")])

    # --- Material ---
    def test_generar_envia_los_campos_del_backend_y_espera_el_tiempo_maximo(self):
        cliente, sesion = self.con_token(respuesta(status=201, cuerpo=paquete_json()))
        paquete = cliente.generar_paquete(solicitud())
        metodo, url, kwargs = sesion.llamadas[1]
        self.assertEqual((metodo, url), ("POST", f"{self.URL}/api/v1/contenidos"))
        self.assertEqual(kwargs["json"], {"id_tema": "t-redes", "tema": "Redes VCN",
                                          "perfil_destinatario": PERFILES[1], "formato_salida": "Quiz"})
        self.assertEqual(kwargs["timeout"], 30)
        self.assertEqual(paquete.metadatos.formato_generado, "Quiz")

    def test_generar_sin_tema_no_manda_tema(self):
        cliente, sesion = self.con_token(respuesta(status=201, cuerpo=paquete_json()))
        cliente.generar_paquete(solicitud(tema=""))
        self.assertNotIn("tema", sesion.llamadas[1][2]["json"])

    def test_generar_202_es_material_en_revision(self):
        pendiente = {"id": "c" * 32, "creado_en": "2026-10-19T15:00:00Z", "status": "requiere_revision",
                     "mensaje": "El material quedó pendiente de revisión por un administrador."}
        cliente, _ = self.con_token(respuesta(status=202, cuerpo=pendiente))
        material = cliente.generar_paquete(solicitud(formato_salida="Guion"))
        self.assertIsInstance(material, MaterialEnRevision)
        self.assertEqual(material.id, "c" * 32)

    def test_generar_422_sin_contexto_y_sin_documentos(self):
        for codigo, tipo in (("SIN_CONTEXTO", "sin_contexto"), ("SIN_DOCUMENTOS_ASOCIADOS", "sin_documentos")):
            with self.subTest(codigo=codigo):
                fallo = self.error_de(lambda c: c.generar_paquete(solicitud()), error(422, codigo))
                self.assertEqual((fallo.tipo, fallo.mensaje), (tipo, ErrorCliente.MENSAJES[tipo]))

    def test_revision_del_admin(self):
        cliente, sesion = self.con_token(
            respuesta(cuerpo=listado(CONTENIDO_JSON)), respuesta(cuerpo=paquete_json("guion.json")),
            respuesta(cuerpo=paquete_json("guion.json")), respuesta(status=204, texto=""))
        resumenes = cliente.listar_paquetes_revision()
        self.assertEqual(sesion.llamadas[1][2]["params"], {"pendiente": "true", "limit": 100})
        self.assertEqual([(r.id, r.tema, r.formato) for r in resumenes], [("c" * 32, "subredes", "Guion")])
        self.assertEqual(cliente.obtener_paquete("c" * 32).status, "requiere_revision")
        self.assertEqual(cliente.aprobar_paquete("c" * 32).metadatos.formato_generado, "Guion")
        self.assertIsNone(cliente.rechazar_paquete("c" * 32))
        self.assertEqual(self.rutas(sesion), [
            ("GET", "/api/v1/contenidos"), ("GET", f"/api/v1/contenidos/{'c' * 32}"),
            ("POST", f"/api/v1/contenidos/{'c' * 32}/aprobar"), ("POST", f"/api/v1/contenidos/{'c' * 32}/rechazar")])

    def test_mi_material(self):
        cliente, sesion = self.con_token(respuesta(cuerpo=listado({**CONTENIDO_JSON, "status": "exito"})))
        material = cliente.listar_mi_material("t-redes")
        self.assertEqual(self.rutas(sesion), [("GET", "/api/v1/contenidos")])
        self.assertEqual(sesion.llamadas[1][2]["params"], {"id_tema": "t-redes", "limit": 100})
        self.assertEqual([(m.titulo, m.formato) for m in material], [("Guion", "Guion")])

    # --- Documentos y configuración ---
    def test_documentos_subir_y_listar(self):
        cliente, sesion = self.con_token(respuesta(status=201, cuerpo=DOCUMENTO_JSON),
                                         respuesta(cuerpo=listado(DOCUMENTO_JSON)))
        documento = cliente.subir_documento("redes.pdf", b"%PDF")
        documentos = cliente.listar_documentos()
        self.assertEqual(self.rutas(sesion), [("POST", "/api/v1/documentos"), ("GET", "/api/v1/documentos")])
        self.assertEqual(sesion.llamadas[1][2]["files"], {"archivo": ("redes.pdf", b"%PDF")})
        self.assertEqual(sesion.llamadas[2][2]["params"], {"limit": 100})
        self.assertEqual((documento.titulo, documento.fragmentos), ("Redes VCN", 3))
        self.assertEqual([d.id for d in documentos], [ID_A])

    def test_solo_generar_y_subir_esperan_el_tiempo_maximo(self):
        cliente, sesion = self.con_token(respuesta(cuerpo={"sector": "General"}), respuesta(cuerpo={"sector": "General"}),
                                         respuesta(cuerpo=listado()), respuesta(cuerpo=listado()),
                                         respuesta(status=201, cuerpo=DOCUMENTO_JSON))
        cliente.obtener_configuracion()
        cliente.guardar_configuracion("General")
        cliente.listar_documentos()
        cliente.listar_paquetes_revision()
        cliente.subir_documento("a.pdf", b"%PDF")
        tiempos = [k["timeout"] for _, _, k in sesion.llamadas[1:]]
        self.assertEqual(tiempos, [TIEMPO_CORTO_SEGUNDOS] * 4 + [30])

    def test_configuracion_usa_api_v1(self):
        cliente, sesion = self.con_token(respuesta(cuerpo={"sector": "Salud"}), respuesta(cuerpo={"sector": "Salud"}))
        self.assertEqual(cliente.obtener_configuracion().sector, "Salud")
        cliente.guardar_configuracion("Salud")
        self.assertEqual(self.rutas(sesion), [("GET", "/api/v1/configuracion"), ("PUT", "/api/v1/configuracion")])
        self.assertEqual(sesion.llamadas[2][2]["json"], {"sector": "Salud"})

    def test_configuracion_404_devuelve_general(self):
        # Mientras Backend no tenga la ruta, el estudiante puede generar igual
        cliente, _ = self.con_token(error(404, "RECURSO_NO_ENCONTRADO"))
        self.assertEqual(cliente.obtener_configuracion().sector, "General")

    def test_guardar_configuracion_404_avisa_que_no_esta_disponible(self):
        fallo = self.error_de(lambda c: c.guardar_configuracion("Salud"), error(404, "RECURSO_NO_ENCONTRADO"))
        self.assertEqual((fallo.tipo, fallo.mensaje),
                         ("rechazado", "Esta opción todavía no está disponible en el servidor."))

    # --- Errores ---
    def test_errores_de_red_y_de_estado_se_traducen(self):
        casos = [
            ({"excepcion": requests.ConnectionError("caída")}, "no_disponible"),
            ({"excepcion": requests.Timeout("lento")}, "tiempo_agotado"),
            ({"respuesta": error(403, "PERMISOS_INSUFICIENTES")}, "sin_permiso"),
            ({"respuesta": error(404, "TEMA_NO_ENCONTRADO")}, "no_encontrado"),
            ({"respuesta": error(500, "ERROR_INTERNO")}, "rechazado"),
            ({"respuesta": error(502, "SALIDA_INVALIDA")}, "respuesta_invalida"),
            ({"respuesta": error(503, "CONFIGURACION_INCOMPLETA")}, "no_disponible"),
            ({"respuesta": respuesta(texto="<html>proxy</html>")}, "respuesta_invalida"),
            ({"respuesta": respuesta(status=201, cuerpo={"status": "exito"})}, "respuesta_invalida"),
        ]
        for kwargs, tipo in casos:
            with self.subTest(tipo=tipo):
                cliente, _ = self.cliente(**kwargs)
                with self.assertRaises(ErrorCliente) as ctx:
                    cliente.generar_paquete(solicitud())
                self.assertEqual(ctx.exception.tipo, tipo)
                self.assertTrue(ctx.exception.mensaje)

    def test_error_con_cuerpo_html(self):
        # Un proxy delante de la API puede responder un 502 en HTML
        cliente, _ = self.cliente(respuesta=respuesta(status=502, texto="<html>Bad Gateway</html>"))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.generar_paquete(solicitud())
        self.assertEqual((ctx.exception.tipo, ctx.exception.mensaje),
                         ("respuesta_invalida", ErrorCliente.MENSAJES["respuesta_invalida"]))

    def test_409_y_422_usan_el_mensaje_del_backend_salvo_la_entrada_invalida(self):
        fallo = self.error_de(lambda c: c.retirar_tema("t-1"), error(409, "CONTENIDO_NO_PENDIENTE", "Ya no está."))
        self.assertEqual((fallo.tipo, fallo.mensaje), ("rechazado", "Ya no está."))
        # "Revisa los campos: body.x" es técnico: el detalle queda para el admin
        fallo = self.error_de(lambda c: c.retirar_tema("t-1"),
                              error(422, "ENTRADA_INVALIDA", "Revisa los campos: body.nombre"))
        self.assertEqual(fallo.mensaje, ErrorCliente.MENSAJES["rechazado"])
        self.assertIn("body.nombre", fallo.detalle)

    def test_413_y_415_usan_el_mensaje_del_backend(self):
        # Revisión final: "inténtalo de nuevo" no sirve si el PDF tiene demasiadas páginas
        for estado, codigo, mensaje in ((413, "DEMASIADAS_PAGINAS", "El PDF supera las 100 páginas."),
                                        (415, "TIPO_NO_SOPORTADO", "Solo se aceptan PDF, Markdown o TXT.")):
            with self.subTest(estado=estado):
                fallo = self.error_de(lambda c: c.subir_documento("a.pdf", b"%PDF"), error(estado, codigo, mensaje))
                self.assertEqual((fallo.tipo, fallo.mensaje), ("rechazado", mensaje))

    def test_listado_que_no_es_listado_es_respuesta_invalida(self):
        for cuerpo in ({"documentos": []}, [DOCUMENTO_JSON]):
            with self.subTest(cuerpo=cuerpo):
                fallo = self.error_de(lambda c: c.listar_documentos(), respuesta(cuerpo=cuerpo))
                self.assertEqual(fallo.tipo, "respuesta_invalida")


class ElegirCliente(unittest.TestCase):
    def test_mock_por_defecto_y_http_cuando_se_pide(self):
        with patch.dict(os.environ, {"MODO_API": "mock"}):
            self.assertIsInstance(obtener_cliente(), ClienteMock)
        with patch.dict(os.environ, {"MODO_API": "http", "URL_API": "http://x", "TIEMPO_MAXIMO_SEGUNDOS": "60"}):
            self.assertIsInstance(obtener_cliente(), ClienteHttp)

    def test_tiempo_maximo_por_defecto_es_300(self):
        with patch.dict(os.environ, {"MODO_API": "http", "URL_API": "http://x"}), \
                patch("cliente_api.load_dotenv"):
            os.environ.pop("TIEMPO_MAXIMO_SEGUNDOS", None)
            self.assertEqual(obtener_cliente()._tiempo_maximo, 300)


if __name__ == "__main__":
    unittest.main()
