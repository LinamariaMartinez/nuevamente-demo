"""Pruebas de las vistas: cada paquete se dibuja sin errores y los casos raros caen en la vista genérica."""

import json
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "app"))

from streamlit.testing.v1 import AppTest

from vistas.generica import AVISO_REVISION

MOCKS = RAIZ / "app" / "mocks"
APP_VISTA = str(RAIZ / "tests" / "apps_interfaz" / "vista_app.py")
MOCKS_EXITO = ("flashcards.json", "quiz.json", "tutorial.json", "resumen.json", "guion.json")


def cargar(nombre):
    return json.loads((MOCKS / nombre).read_text(encoding="utf-8"))


def correr(datos):
    at = AppTest.from_file(APP_VISTA, default_timeout=10)
    at.session_state["datos_paquete"] = datos
    return at.run()


def textos(at):
    return " ".join(m.value for m in at.markdown)


class VistaGenerica(unittest.TestCase):
    def test_cada_mock_de_exito_se_dibuja_con_titulo_y_fuentes(self):
        for nombre in MOCKS_EXITO:
            with self.subTest(mock=nombre):
                datos = cargar(nombre)
                at = correr(datos)
                self.assertEqual(len(at.exception), 0)
                self.assertEqual(at.header[0].value, datos["contenido_adaptado"]["titulo"])
                self.assertTrue(any(e.label.startswith("Fuentes") for e in at.expander))

    def test_paquete_que_requiere_revision_muestra_el_aviso(self):
        at = correr(cargar("guion.json"))
        self.assertEqual(at.warning[0].value, AVISO_REVISION)

    def test_paquete_aprobado_no_muestra_el_aviso(self):
        self.assertEqual(len(correr(cargar("resumen.json")).warning), 0)

    def test_formato_desconocido_usa_la_vista_generica(self):
        datos = cargar("resumen.json")
        datos["metadatos"]["formato_generado"] = "Podcast"
        at = correr(datos)
        self.assertEqual(len(at.exception), 0)
        self.assertIn("Qué es", textos(at))

    def test_paquete_con_error_muestra_el_mensaje_sin_romperse(self):
        datos = cargar("error_sin_contexto.json")
        at = correr(datos)
        self.assertEqual(len(at.exception), 0)
        self.assertIn(datos["mensaje_error"], [e.value for e in at.error])

    def test_paquete_sin_items_avisa_que_no_hay_contenido(self):
        datos = cargar("resumen.json")
        datos["contenido_adaptado"]["items"] = []
        at = correr(datos)
        self.assertIn("Este paquete no trae contenido.", [i.value for i in at.info])


if __name__ == "__main__":
    unittest.main()
