"""Pruebas de la vista interactiva de flashcards."""

import json
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "app"))

from streamlit.testing.v1 import AppTest

APP_VISTA = str(RAIZ / "tests" / "apps_interfaz" / "vista_app.py")
DATOS = json.loads((RAIZ / "app" / "mocks" / "flashcards.json").read_text(encoding="utf-8"))
CLAVE = "flashcard_ejemplo-001"


def correr(datos=DATOS):
    at = AppTest.from_file(APP_VISTA, default_timeout=10)
    at.session_state["datos_paquete"] = datos
    return at.run()


def textos(at):
    return " ".join(m.value for m in at.markdown)


class VistaFlashcards(unittest.TestCase):
    def test_empieza_en_la_primera_tarjeta_por_el_frente(self):
        at = correr()
        primera = DATOS["contenido_adaptado"]["items"][0]
        self.assertIn(primera["frente"], textos(at))
        self.assertNotIn(primera["dorso"], textos(at))
        self.assertIn("Tarjeta 1 de 5", [c.value for c in at.caption])
        self.assertTrue(at.button(key=f"{CLAVE}_anterior").disabled)

    def test_voltear_muestra_la_respuesta(self):
        at = correr().button(key=f"{CLAVE}_voltear").click().run()
        self.assertIn(DATOS["contenido_adaptado"]["items"][0]["dorso"], textos(at))

    def test_siguiente_pasa_a_la_segunda_tarjeta_por_el_frente(self):
        at = correr().button(key=f"{CLAVE}_voltear").click().run()
        at = at.button(key=f"{CLAVE}_siguiente").click().run()
        self.assertIn("Tarjeta 2 de 5", [c.value for c in at.caption])
        self.assertIn(DATOS["contenido_adaptado"]["items"][1]["frente"], textos(at))

    def test_tarjeta_incompleta_usa_la_vista_generica(self):
        datos = json.loads(json.dumps(DATOS))
        del datos["contenido_adaptado"]["items"][0]["dorso"]
        at = correr(datos)
        self.assertEqual(len(at.exception), 0)
        self.assertIn("*Frente:*", textos(at))


if __name__ == "__main__":
    unittest.main()
