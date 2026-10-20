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
from contrato import FORMATOS, PERFILES, DatosTema, MaterialEnRevision, SolicitudPaquete

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


def respuesta(status=200, cuerpo=None, texto=None):
    r = requests.Response()
    r.status_code = status
    r.encoding = "utf-8"
    r._content = (json.dumps(cuerpo) if texto is None else texto).encode("utf-8")
    return r


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
TEMA_JSON = {"id_tema": "t-1", "nombre": "Redes", "descripcion": "", "documentos": ["a.pdf"]}


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
        cliente.cerrar_sesion()
        sesion = cliente.iniciar_sesion("mateo", "nueva-clave-1")
        self.assertFalse(sesion.usuario.debe_cambiar_contrasena)

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

    # --- Generar material ---
    def test_genera_un_paquete_por_formato_con_lo_que_pidio_el_estudiante(self):
        cliente = con_sesion("admin")
        cliente.guardar_configuracion("Fintech")
        cliente.cerrar_sesion()
        cliente.iniciar_sesion("laura", "demo-estudiante")
        for formato in ("Tutorial", "Flashcards", "Quiz", "Resumen"):
            with self.subTest(formato=formato):
                paquete = cliente.generar_paquete(solicitud(formato_salida=formato))
                self.assertEqual(paquete.metadatos.formato_generado, formato)
                self.assertEqual(paquete.id_tema, "t-redes")
                self.assertEqual(paquete.status, "exito")
                self.assertEqual(paquete.metadatos.perfil_aplicado, PERFILES[1])
                self.assertEqual(paquete.metadatos.nicho_sector, "Fintech")

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
    def cliente(self, **kwargs):
        sesion = SesionFalsa(**kwargs)
        return ClienteHttp("http://api.local/", tiempo_maximo=30, sesion=sesion), sesion

    def con_token(self, *respuestas):
        """Cliente que ya inició sesión; `respuestas` son las de las llamadas siguientes."""
        cliente, sesion = self.cliente(respuestas=[respuesta(cuerpo=SESION_JSON), *respuestas])
        cliente.iniciar_sesion("ana", "clave")
        return cliente, sesion

    # --- Sesión y token ---
    def test_iniciar_sesion_guarda_el_token_y_lo_envia_despues(self):
        cliente, sesion = self.con_token(respuesta(cuerpo=[TEMA_JSON]))
        temas = cliente.listar_temas()
        (m1, u1, k1), (m2, u2, k2) = sesion.llamadas
        self.assertEqual((m1, u1, k1["json"]), ("POST", "http://api.local/sesion", {"usuario": "ana", "contrasena": "clave"}))
        self.assertNotIn("Authorization", k1["headers"])
        self.assertEqual((m2, u2), ("GET", "http://api.local/temas"))
        self.assertEqual(k2["headers"]["Authorization"], "Bearer tok-123")
        self.assertNotIn("tok-123", u2)  # el token nunca va en la URL
        self.assertEqual(temas[0].nombre, "Redes")

    def test_401_en_inicio_es_credenciales_y_en_otra_ruta_sesion_vencida(self):
        cliente, _ = self.cliente(respuesta=respuesta(status=401, texto="no"))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.iniciar_sesion("ana", "mala")
        self.assertEqual(ctx.exception.tipo, "credenciales")
        cliente, _ = self.con_token(respuesta(status=401, texto="vencido"))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.listar_temas()
        self.assertEqual(ctx.exception.tipo, "sesion_vencida")

    def test_cerrar_sesion_borra_el_token_aunque_la_api_falle(self):
        cliente, sesion = self.con_token(respuesta(status=500, texto="caída"), respuesta(cuerpo=[]))
        with self.assertRaises(ErrorCliente):
            cliente.cerrar_sesion()
        self.assertEqual(sesion.llamadas[1][0], "DELETE")
        cliente.listar_temas()
        self.assertNotIn("Authorization", sesion.llamadas[2][2]["headers"])

    def test_401_al_cambiar_la_contrasena_es_contrasena_actual_incorrecta(self):
        # Revisión final: no debe cerrar la sesión de quien se equivocó al escribir su contraseña actual
        cliente, _ = self.con_token(respuesta(status=401, texto="actual incorrecta"))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.cambiar_contrasena("mala", "nueva-1234")
        self.assertEqual((ctx.exception.tipo, ctx.exception.mensaje), ("rechazado", "La contraseña actual no es correcta."))

    def test_cambiar_contrasena_envia_actual_y_nueva(self):
        cliente, sesion = self.con_token(respuesta(status=204, texto=""))
        self.assertIsNone(cliente.cambiar_contrasena("vieja-123", "nueva-1234"))
        metodo, url, kwargs = sesion.llamadas[1]
        self.assertEqual((metodo, url, kwargs["json"]),
                         ("PUT", "http://api.local/sesion/contrasena", {"actual": "vieja-123", "nueva": "nueva-1234"}))

    # --- Temas ---
    def test_crear_editar_y_retirar_tema(self):
        datos = DatosTema(nombre="Redes", documentos=["a.pdf"])
        cliente, sesion = self.con_token(respuesta(cuerpo=TEMA_JSON), respuesta(cuerpo=TEMA_JSON),
                                         respuesta(status=204, texto=""))
        cliente.crear_tema(datos)
        cliente.editar_tema("t-1", datos)
        self.assertIsNone(cliente.retirar_tema("t-1"))
        self.assertEqual([(m, u) for m, u, _ in sesion.llamadas[1:]],
                         [("POST", "http://api.local/temas"), ("PUT", "http://api.local/temas/t-1"),
                          ("DELETE", "http://api.local/temas/t-1")])
        self.assertEqual(sesion.llamadas[1][2]["json"], {"nombre": "Redes", "descripcion": "", "documentos": ["a.pdf"]})

    def test_id_con_caracteres_especiales_va_codificado(self):
        cliente, sesion = self.con_token(respuesta(status=204, texto=""))
        cliente.retirar_tema("t/1 a")
        self.assertEqual(sesion.llamadas[1][1], "http://api.local/temas/t%2F1%20a")

    # --- Material, documentos y configuración ---
    def test_generar_envia_id_tema_y_espera_el_tiempo_maximo(self):
        cliente, sesion = self.con_token(respuesta(cuerpo=paquete_json()))
        paquete = cliente.generar_paquete(solicitud())
        metodo, url, kwargs = sesion.llamadas[1]
        self.assertEqual((metodo, url), ("POST", "http://api.local/paquetes"))
        self.assertEqual((kwargs["json"]["id_tema"], kwargs["json"]["tema"]), ("t-redes", "Redes VCN"))
        self.assertEqual(kwargs["timeout"], 30)
        self.assertEqual(paquete.metadatos.formato_generado, "Quiz")

    def test_solo_generar_y_subir_esperan_el_tiempo_maximo(self):
        documento = {"nombre": "a.pdf", "estado": "procesando", "chunks": 0, "error": None}
        cliente, sesion = self.con_token(respuesta(cuerpo={"sector": "General"}), respuesta(cuerpo={"sector": "General"}),
                                         respuesta(cuerpo=[]), respuesta(cuerpo=[]), respuesta(cuerpo=documento))
        cliente.obtener_configuracion()
        cliente.guardar_configuracion("General")
        cliente.listar_documentos()
        cliente.listar_paquetes_revision()
        cliente.subir_documento("a.pdf", b"%PDF")
        tiempos = [k["timeout"] for _, _, k in sesion.llamadas[1:]]
        self.assertEqual(tiempos, [TIEMPO_CORTO_SEGUNDOS] * 4 + [30])
        self.assertEqual(sesion.llamadas[4][2]["params"], {"requiere_revision": "true"})
        self.assertEqual(sesion.llamadas[5][2]["files"], {"archivo": ("a.pdf", b"%PDF")})

    # --- Errores ---
    def test_errores_de_red_y_de_estado_se_traducen(self):
        casos = [
            ({"excepcion": requests.ConnectionError("caída")}, "no_disponible"),
            ({"excepcion": requests.Timeout("lento")}, "tiempo_agotado"),
            ({"respuesta": respuesta(status=403, texto="rol")}, "sin_permiso"),
            ({"respuesta": respuesta(status=404, texto="no")}, "no_encontrado"),
            ({"respuesta": respuesta(status=500, texto="explotó")}, "rechazado"),
            ({"respuesta": respuesta(texto="<html>proxy</html>")}, "respuesta_invalida"),
            ({"respuesta": respuesta(cuerpo={"status": "exito"})}, "respuesta_invalida"),
        ]
        for kwargs, tipo in casos:
            with self.subTest(tipo=tipo):
                cliente, _ = self.cliente(**kwargs)
                with self.assertRaises(ErrorCliente) as ctx:
                    cliente.generar_paquete(solicitud())
                self.assertEqual(ctx.exception.tipo, tipo)
                self.assertTrue(ctx.exception.mensaje)

    def test_409_y_422_usan_el_mensaje_de_backend_si_viene(self):
        cliente, _ = self.cliente(respuesta=respuesta(status=409, cuerpo={"mensaje": "Ya existe un tema con ese nombre."}))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.crear_tema(DatosTema(nombre="Redes", documentos=["a.pdf"]))
        self.assertEqual((ctx.exception.tipo, ctx.exception.mensaje), ("rechazado", "Ya existe un tema con ese nombre."))
        cliente, _ = self.cliente(respuesta=respuesta(status=422, cuerpo={"detail": [{"loc": ["body"]}]}))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.crear_tema(DatosTema(nombre="Redes", documentos=["a.pdf"]))
        self.assertEqual(ctx.exception.mensaje, ErrorCliente.MENSAJES["rechazado"])

    def test_lista_que_no_es_lista_es_respuesta_invalida(self):
        cliente, _ = self.cliente(respuesta=respuesta(cuerpo={"documentos": []}))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.listar_documentos()
        self.assertEqual(ctx.exception.tipo, "respuesta_invalida")

    def test_salud_es_false_si_la_api_no_responde(self):
        cliente, sesion = self.cliente(excepcion=requests.ConnectionError("caída"))
        self.assertFalse(cliente.salud())
        self.assertEqual(sesion.llamadas[0][2]["timeout"], 5)


class ElegirCliente(unittest.TestCase):
    def test_mock_por_defecto_y_http_cuando_se_pide(self):
        with patch.dict(os.environ, {"MODO_API": "mock"}):
            self.assertIsInstance(obtener_cliente(), ClienteMock)
        with patch.dict(os.environ, {"MODO_API": "http", "URL_API": "http://x", "TIEMPO_MAXIMO_SEGUNDOS": "60"}):
            self.assertIsInstance(obtener_cliente(), ClienteHttp)


if __name__ == "__main__":
    unittest.main()
