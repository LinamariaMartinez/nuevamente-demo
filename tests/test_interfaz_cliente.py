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
from contrato import FORMATOS, PERFILES, SolicitudPaquete

MOCKS = RAIZ / "app" / "mocks"


def solicitud(**cambios):
    datos = {"tema": "Redes VCN", "perfil": PERFILES[1], "formato": "Quiz"}
    datos.update(cambios)
    return SolicitudPaquete(**datos)


def respuesta(status=200, cuerpo=None, texto=None):
    r = requests.Response()
    r.status_code = status
    r.encoding = "utf-8"
    r._content = (json.dumps(cuerpo) if texto is None else texto).encode("utf-8")
    return r


class SesionFalsa:
    def __init__(self, respuesta=None, excepcion=None):
        self.respuesta = respuesta
        self.excepcion = excepcion
        self.llamadas = []

    def request(self, metodo, url, **kwargs):
        self.llamadas.append((metodo, url, kwargs))
        if self.excepcion is not None:
            raise self.excepcion
        return self.respuesta


def paquete_json(nombre="quiz.json"):
    return json.loads((MOCKS / nombre).read_text(encoding="utf-8"))


class ModoMock(unittest.TestCase):
    def setUp(self):
        self.cliente = ClienteMock()

    def test_es_mock_y_esta_sano(self):
        self.assertTrue(self.cliente.es_mock)
        self.assertTrue(self.cliente.salud())

    def test_genera_un_paquete_por_formato_con_lo_que_pidio_el_estudiante(self):
        self.cliente.guardar_configuracion("Fintech")
        for formato in FORMATOS:
            with self.subTest(formato=formato):
                paquete = self.cliente.generar_paquete(solicitud(formato=formato))
                self.assertEqual(paquete.metadatos.formato_generado, formato)
                self.assertEqual(paquete.metadatos.tema, "Redes VCN")
                self.assertEqual(paquete.metadatos.perfil_aplicado, PERFILES[1])
                self.assertEqual(paquete.metadatos.nicho_sector, "Fintech")

    def test_sector_empieza_en_general_y_se_puede_cambiar(self):
        self.assertEqual(self.cliente.obtener_configuracion().sector, "General")
        self.assertEqual(self.cliente.guardar_configuracion("Salud").sector, "Salud")
        self.assertEqual(self.cliente.obtener_configuracion().sector, "Salud")

    def test_sector_no_permitido_no_se_guarda(self):
        with self.assertRaises(ErrorCliente) as ctx:
            self.cliente.guardar_configuracion("Minería")
        self.assertEqual(ctx.exception.tipo, "rechazado")
        self.assertEqual(self.cliente.obtener_configuracion().sector, "General")

    def test_cada_generacion_tiene_un_id_nuevo(self):
        # Si dos paquetes comparten id, sus vistas interactivas comparten estado (quiz ya calificado, etc.)
        primero = self.cliente.generar_paquete(solicitud(formato="Quiz"))
        segundo = self.cliente.generar_paquete(solicitud(formato="Quiz"))
        self.assertNotEqual(primero.id_paquete, segundo.id_paquete)
        self.assertTrue(primero.id_paquete.startswith("ejemplo-002"))

    def test_tema_inexistente_devuelve_error_sin_contexto(self):
        paquete = self.cliente.generar_paquete(solicitud(tema="Tema inexistente"))
        self.assertEqual(paquete.status, "error")
        self.assertEqual(paquete.codigo_error, "sin_contexto")

    def test_el_guion_alterna_entre_en_revision_y_aprobado(self):
        # Para la demo: el primer guion cae en revisión y "Generar otra versión" trae uno aprobado
        revisiones = [self.cliente.generar_paquete(solicitud(formato="Guion")).evaluacion_calidad.requiere_revision_admin
                      for _ in range(3)]
        self.assertEqual(revisiones, [True, False, True])

    def test_lista_de_revision_trae_solo_el_guion(self):
        resumenes = self.cliente.listar_paquetes_revision()
        self.assertEqual([r.formato for r in resumenes], ["Guion"])

    def test_obtener_paquete_existente_y_no_existente(self):
        self.assertEqual(self.cliente.obtener_paquete("ejemplo-002").metadatos.formato_generado, "Quiz")
        with self.assertRaises(ErrorCliente) as ctx:
            self.cliente.obtener_paquete("no-existe")
        self.assertEqual(ctx.exception.tipo, "rechazado")

    def test_subir_documento_lo_agrega_a_la_lista(self):
        antes = len(self.cliente.listar_documentos())
        documento = self.cliente.subir_documento("nuevo.md", b"# Hola")
        self.assertEqual(documento.estado, "indexado")
        self.assertEqual(len(self.cliente.listar_documentos()), antes + 1)

    def test_la_lista_de_documentos_trae_uno_con_error(self):
        self.assertIn("error", [d.estado for d in self.cliente.listar_documentos()])


class ModoHttp(unittest.TestCase):
    def cliente(self, **kwargs):
        sesion = SesionFalsa(**kwargs)
        return ClienteHttp("http://api.local/", clave_admin="secreta", tiempo_maximo=30, sesion=sesion), sesion

    def test_generar_envia_post_con_la_solicitud_y_el_tiempo_maximo(self):
        cliente, sesion = self.cliente(respuesta=respuesta(cuerpo=paquete_json()))
        paquete = cliente.generar_paquete(solicitud())
        metodo, url, kwargs = sesion.llamadas[0]
        self.assertEqual((metodo, url), ("POST", "http://api.local/paquetes"))
        self.assertEqual(kwargs["json"]["tema"], "Redes VCN")
        self.assertEqual(kwargs["timeout"], 30)
        self.assertNotIn("X-Clave-Admin", kwargs["headers"])
        self.assertEqual(paquete.metadatos.formato_generado, "Quiz")

    def test_rutas_de_admin_envian_la_clave(self):
        cliente, sesion = self.cliente(respuesta=respuesta(cuerpo=[]))
        cliente.listar_documentos()
        cliente.listar_paquetes_revision()
        for _, _, kwargs in sesion.llamadas:
            self.assertEqual(kwargs["headers"]["X-Clave-Admin"], "secreta")
        self.assertEqual(sesion.llamadas[1][2]["params"], {"requiere_revision": "true"})

    def test_configuracion_se_lee_sin_clave_y_se_guarda_con_clave(self):
        cliente, sesion = self.cliente(respuesta=respuesta(cuerpo={"sector": "Salud"}))
        self.assertEqual(cliente.obtener_configuracion().sector, "Salud")
        cliente.guardar_configuracion("Salud")
        (m1, u1, k1), (m2, u2, k2) = sesion.llamadas
        self.assertEqual((m1, u1), ("GET", "http://api.local/configuracion"))
        self.assertNotIn("X-Clave-Admin", k1["headers"])
        self.assertEqual((m2, u2), ("PUT", "http://api.local/configuracion"))
        self.assertEqual(k2["headers"]["X-Clave-Admin"], "secreta")
        self.assertEqual(k2["json"], {"sector": "Salud"})

    def test_solo_generar_y_subir_esperan_el_tiempo_maximo(self):
        cliente, sesion = self.cliente(respuesta=respuesta(cuerpo={"sector": "General"}))
        cliente.obtener_configuracion()
        cliente.guardar_configuracion("General")
        self.assertEqual([k["timeout"] for _, _, k in sesion.llamadas], [TIEMPO_CORTO_SEGUNDOS] * 2)
        cliente, sesion = self.cliente(respuesta=respuesta(cuerpo=[]))
        cliente.listar_documentos()
        cliente.listar_paquetes_revision()
        self.assertEqual([k["timeout"] for _, _, k in sesion.llamadas], [TIEMPO_CORTO_SEGUNDOS] * 2)
        cuerpo = {"nombre": "a.pdf", "estado": "procesando", "chunks": 0, "error": None}
        cliente, sesion = self.cliente(respuesta=respuesta(cuerpo=cuerpo))
        cliente.subir_documento("a.pdf", b"%PDF")
        self.assertEqual(sesion.llamadas[0][2]["timeout"], 30)

    def test_errores_de_red_y_de_estado_se_traducen(self):
        casos = [
            ({"excepcion": requests.ConnectionError("caída")}, "no_disponible"),
            ({"excepcion": requests.Timeout("lento")}, "tiempo_agotado"),
            ({"respuesta": respuesta(status=401, texto="clave mala")}, "sin_permiso"),
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

    def test_lista_que_no_es_lista_es_respuesta_invalida(self):
        cliente, _ = self.cliente(respuesta=respuesta(cuerpo={"documentos": []}))
        with self.assertRaises(ErrorCliente) as ctx:
            cliente.listar_documentos()
        self.assertEqual(ctx.exception.tipo, "respuesta_invalida")

    def test_salud_es_false_si_la_api_no_responde(self):
        cliente, sesion = self.cliente(excepcion=requests.ConnectionError("caída"))
        self.assertFalse(cliente.salud())
        self.assertEqual(sesion.llamadas[0][2]["timeout"], 5)

    def test_subir_documento_envia_el_archivo(self):
        cuerpo = {"nombre": "a.pdf", "estado": "procesando", "chunks": 0, "error": None}
        cliente, sesion = self.cliente(respuesta=respuesta(cuerpo=cuerpo))
        documento = cliente.subir_documento("a.pdf", b"%PDF")
        self.assertEqual(documento.estado, "procesando")
        self.assertEqual(sesion.llamadas[0][2]["files"], {"archivo": ("a.pdf", b"%PDF")})


class ElegirCliente(unittest.TestCase):
    def test_mock_por_defecto_y_http_cuando_se_pide(self):
        with patch.dict(os.environ, {"MODO_API": "mock"}):
            self.assertIsInstance(obtener_cliente(), ClienteMock)
        with patch.dict(os.environ, {"MODO_API": "http", "URL_API": "http://x", "TIEMPO_MAXIMO_SEGUNDOS": "60"}):
            self.assertIsInstance(obtener_cliente(), ClienteHttp)


if __name__ == "__main__":
    unittest.main()
