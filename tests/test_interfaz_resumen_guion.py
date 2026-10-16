"""Pruebas del Resumen en tarjetas y del Guion en escenas (v2.2)."""

import json
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "app"))

from streamlit.testing.v1 import AppTest

MOCKS = RAIZ / "app" / "mocks"
APP_VISTA = str(RAIZ / "tests" / "apps_interfaz" / "vista_app.py")


def cargar(nombre):
    return json.loads((MOCKS / nombre).read_text(encoding="utf-8"))


def correr(datos):
    at = AppTest.from_file(APP_VISTA, default_timeout=10)
    at.session_state["datos_paquete"] = datos
    return at.run()


def markdown(at):
    return [m.value for m in at.markdown]


class Resumen(unittest.TestCase):
    def setUp(self):
        self.datos = cargar("resumen.json")
        self.at = correr(self.datos)

    def test_idea_central_destacada_una_sola_vez(self):
        textos = markdown(self.at)
        self.assertIn(":material/lightbulb: **En pocas palabras**", textos)
        intro = self.datos["contenido_adaptado"]["introduccion_contextualizada"]
        self.assertEqual(sum(t.count(intro) for t in textos), 1)

    def test_cada_seccion_es_una_tarjeta_con_su_titulo(self):
        textos = markdown(self.at)
        for item in self.datos["contenido_adaptado"]["items"]:
            with self.subTest(seccion=item["titulo"]):
                self.assertIn(f"**{item['titulo']}**", textos)
        self.assertFalse(any("*Titulo:*" in t for t in textos))  # ya no es la vista genérica

    def test_conceptos_clave_al_final_como_etiquetas(self):
        conceptos = [t for t in markdown(self.at) if t.startswith("**Conceptos clave:**")]
        self.assertEqual(len(conceptos), 1)
        for concepto in self.datos["metadatos"]["conceptos_clave"]:
            self.assertIn(f":gray-badge[{concepto}]", conceptos[0])

    def test_mas_de_tres_secciones_pasan_a_otra_fila(self):
        datos = json.loads(json.dumps(self.datos))
        datos["contenido_adaptado"]["items"].append({"titulo": "Cuarta", "contenido": "Otra idea."})
        at = correr(datos)
        self.assertEqual(len(at.exception), 0)
        self.assertIn("**Cuarta**", markdown(at))

    def test_sin_secciones_avisa_que_no_hay_contenido(self):
        datos = json.loads(json.dumps(self.datos))
        datos["contenido_adaptado"]["items"] = []
        at = correr(datos)
        self.assertIn("Este material no trae contenido.", [i.value for i in at.info])


class Guion(unittest.TestCase):
    def test_escenas_numeradas(self):
        datos = cargar("guion.json")
        textos = markdown(correr(datos))
        for numero, item in enumerate(datos["contenido_adaptado"]["items"], start=1):
            with self.subTest(escena=numero):
                self.assertIn(f"**Escena {numero} · {item['titulo']}**", textos)
        self.assertFalse(any("*Titulo:*" in t for t in textos))


if __name__ == "__main__":
    unittest.main()
