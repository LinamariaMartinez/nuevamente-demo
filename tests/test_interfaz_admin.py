"""Pruebas de la página del admin: contraseña, documentos, revisión y validación de archivos."""

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "app"))

from streamlit.testing.v1 import AppTest

from cliente_api import ClienteMock, ErrorCliente
from paginas.admin import validar_archivo

APP = str(RAIZ / "tests" / "apps_interfaz" / "admin_app.py")
MB = 1024 * 1024


class ClienteSinPermiso(ClienteMock):
    es_mock = False

    def listar_documentos(self):
        raise ErrorCliente("sin_permiso", "401")


def abrir(contrasena="clave-de-prueba", cliente=None):
    at = AppTest.from_file(APP, default_timeout=10)
    if contrasena is not None:
        at.secrets["contrasena_admin"] = contrasena
    if cliente is not None:
        at.session_state["cliente"] = cliente
    return at.run()


def entrar(at, clave):
    at.text_input(key="clave_admin").input(clave).run()
    return at.button(key="entrar").click().run()


@patch.dict(os.environ, {"MODO_API": "mock"})
class PaginaAdmin(unittest.TestCase):
    def test_sin_contrasena_configurada_avisa_y_no_deja_entrar(self):
        at = abrir(contrasena=None)
        self.assertTrue(any("Falta configurar la contraseña" in e.value for e in at.error))
        self.assertEqual(len(at.text_input), 0)

    def test_contrasena_incorrecta(self):
        at = entrar(abrir(), "otra")
        self.assertIn("Contraseña incorrecta", [e.value for e in at.error])
        self.assertEqual(len(at.subheader), 0)

    def test_contrasena_correcta_muestra_las_tres_secciones(self):
        at = entrar(abrir(), "clave-de-prueba")
        self.assertEqual([s.value for s in at.subheader],
                         ["Subir documento", "Documentos", "Paquetes por revisar"])
        self.assertTrue(any("manual_escaneado.pdf" in e.value for e in at.error))

    def test_abrir_un_paquete_por_revisar_lo_muestra_con_aviso(self):
        at = entrar(abrir(), "clave-de-prueba")
        at = at.button(key="abrir_ejemplo-005").click().run()
        self.assertEqual(at.header[0].value, "Guion de clase: arquitectura de red en OCI")
        self.assertEqual(len(at.warning), 1)

    def test_api_sin_permiso_muestra_el_mensaje(self):
        at = entrar(abrir(cliente=ClienteSinPermiso()), "clave-de-prueba")
        self.assertIn("No tienes permiso. Revisa la configuración de la clave.", [e.value for e in at.error])


class ValidarArchivo(unittest.TestCase):
    def test_casos(self):
        casos = [
            ("manual.pdf", MB, None),
            ("MANUAL.PDF", MB, None),
            ("notas.md", 10 * MB, None),
            ("notas.txt", 10 * MB + 1, "El archivo supera 10 MB."),
            ("vacio.txt", 0, "El archivo está vacío."),
            ("informe.docx", MB, "Solo se aceptan archivos PDF, MD o TXT."),
            ("sin_extension", MB, "Solo se aceptan archivos PDF, MD o TXT."),
        ]
        for nombre, tamano, esperado in casos:
            with self.subTest(nombre=nombre, tamano=tamano):
                self.assertEqual(validar_archivo(nombre, tamano), esperado)


if __name__ == "__main__":
    unittest.main()
