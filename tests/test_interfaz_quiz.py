"""Pruebas de la vista interactiva de quiz."""

import json
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "app"))

from streamlit.testing.v1 import AppTest

APP_VISTA = str(RAIZ / "tests" / "apps_interfaz" / "vista_app.py")
DATOS = json.loads((RAIZ / "app" / "mocks" / "quiz.json").read_text(encoding="utf-8"))
ITEMS = DATOS["contenido_adaptado"]["items"]
CLAVE = "quiz_ejemplo-002"


def correr(datos=DATOS):
    at = AppTest.from_file(APP_VISTA, default_timeout=10)
    at.session_state["datos_paquete"] = datos
    return at.run()


class VistaQuiz(unittest.TestCase):
    def test_todas_correctas_da_puntaje_completo(self):
        at = correr()
        for numero, item in enumerate(ITEMS, start=1):
            at.radio(key=f"{CLAVE}_{numero}").set_value(item["opciones"][item["respuesta_correcta"]])
        at = at.button(key=f"{CLAVE}_calificar").click().run()
        self.assertEqual(at.metric[-1].value, "3 de 3")
        self.assertEqual(len(at.success), 3)

    def test_una_incorrecta_muestra_la_respuesta_y_la_justificacion(self):
        at = correr()
        primera = ITEMS[0]
        incorrecta = next(o for i, o in enumerate(primera["opciones"]) if i != primera["respuesta_correcta"])
        at.radio(key=f"{CLAVE}_1").set_value(incorrecta)
        at = at.button(key=f"{CLAVE}_calificar").click().run()
        self.assertIn(primera["justificacion"], at.error[0].value)
        self.assertEqual(len(at.warning), 2)  # las otras dos quedaron sin responder
        self.assertEqual(at.metric[-1].value, "0 de 3")

    def test_respuesta_fuera_de_rango_usa_la_vista_generica(self):
        datos = json.loads(json.dumps(DATOS))
        datos["contenido_adaptado"]["items"][0]["respuesta_correcta"] = 9
        at = correr(datos)
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.radio), 0)


if __name__ == "__main__":
    unittest.main()
