"""Pruebas de la vista interactiva de la guía paso a paso."""

import json
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "app"))

from streamlit.testing.v1 import AppTest

APP_VISTA = str(RAIZ / "tests" / "apps_interfaz" / "vista_app.py")
DATOS = json.loads((RAIZ / "app" / "mocks" / "tutorial.json").read_text(encoding="utf-8"))
CLAVE = "guia_ejemplo-003"


def correr(datos=DATOS):
    at = AppTest.from_file(APP_VISTA, default_timeout=10)
    at.session_state["datos_paquete"] = datos
    return at.run()


class VistaGuia(unittest.TestCase):
    def test_muestra_los_pasos_y_el_avance_en_cero(self):
        at = correr()
        self.assertEqual(len(at.checkbox), 5)
        self.assertIn("0 de 5 pasos completados", [c.value for c in at.caption])

    def test_marcar_un_paso_sube_el_avance(self):
        at = correr()
        at = at.checkbox(key=f"{CLAVE}_0").check().run()
        self.assertIn("1 de 5 pasos completados", [c.value for c in at.caption])

    def test_pasos_desordenados_se_muestran_en_orden_y_numeros_repetidos_no_rompen(self):
        datos = json.loads(json.dumps(DATOS))
        items = datos["contenido_adaptado"]["items"]
        items.reverse()
        items[0]["paso"] = items[1]["paso"]  # dos pasos con el mismo número
        at = correr(datos)
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.checkbox), 5)


if __name__ == "__main__":
    unittest.main()
