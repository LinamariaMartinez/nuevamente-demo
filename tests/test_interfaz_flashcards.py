"""Pruebas de la vista de flashcards (v2.2): componente HTML con volteo, progreso y Lo sé / Repasar."""

import json
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "app"))

from streamlit.testing.v1 import AppTest

from contrato import ItemFlashcard
from vistas.flashcards import ALTO, COLORES, construir_html

APP_VISTA = str(RAIZ / "tests" / "apps_interfaz" / "vista_app.py")
DATOS = json.loads((RAIZ / "app" / "mocks" / "flashcards.json").read_text(encoding="utf-8"))
ITEMS = [ItemFlashcard(**item) for item in DATOS["contenido_adaptado"]["items"]]


def correr(datos=DATOS):
    at = AppTest.from_file(APP_VISTA, default_timeout=10)
    at.session_state["datos_paquete"] = datos
    return at.run()


class HtmlDelComponente(unittest.TestCase):
    def test_lleva_todas_las_tarjetas(self):
        html = construir_html(ITEMS)
        for item in ITEMS:
            with self.subTest(frente=item.frente):
                self.assertIn(json.dumps(item.frente, ensure_ascii=False)[1:-1], html)
                self.assertIn(json.dumps(item.dorso, ensure_ascii=False)[1:-1], html)

    def test_texto_peligroso_no_rompe_el_html(self):
        raro = ItemFlashcard(frente='</script><b>"hola"</b>', dorso="a & b < c", pista_didactica=None)
        html = construir_html([raro])
        self.assertEqual(html.count("</script>"), 1)  # solo el cierre del script propio
        self.assertIn("\\u003c/script>", html)

    def test_texto_con_marcadores_o_comentarios_no_se_altera_ni_rompe(self):
        # Revisión final: "__texto__" se cambiaba por un color, y "<!-- <script" dejaba el componente en blanco
        raro = ItemFlashcard(frente="usa __texto__ y __fondo__", dorso="<!-- <script> -->", pista_didactica=None)
        html = construir_html([raro])
        self.assertIn("usa __texto__ y __fondo__", html)
        datos = html[html.index("const TARJETAS"):html.index("let actual")]
        self.assertNotIn("<", datos)  # ningún "<" crudo dentro del script

    def test_colores_segun_el_modo(self):
        self.assertIn(COLORES["light"]["fondo"], construir_html(ITEMS))
        self.assertNotIn(COLORES["dark"]["fondo"], construir_html(ITEMS))
        self.assertIn(COLORES["dark"]["fondo"], construir_html(ITEMS, oscuro=True))

    def test_botones_con_texto_teclado_y_movimiento_reducido(self):
        html = construir_html(ITEMS)
        for texto in ("Anterior", "Siguiente", "Lo sé", "Repasar", "prefers-reduced-motion", "keydown", "aria-live"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)

    def test_contraste_del_texto_en_los_dos_modos(self):
        from test_interfaz_tema import contraste
        for modo, c in COLORES.items():
            with self.subTest(modo=modo):
                self.assertGreaterEqual(contraste(c["texto_frente"], c["frente"]), 4.5)
                self.assertGreaterEqual(contraste(c["texto"], c["dorso"]), 4.5)
                self.assertGreaterEqual(contraste(c["si_texto"], c["si_fondo"]), 4.5)
                self.assertGreaterEqual(contraste(c["rep_texto"], c["rep_fondo"]), 4.5)


class VistaFlashcards(unittest.TestCase):
    def test_la_vista_dibuja_el_componente(self):
        at = correr()
        marcos = at.get("iframe")
        self.assertEqual(len(marcos), 1)
        self.assertIn(json.dumps(ITEMS[0].frente, ensure_ascii=False)[1:-1], marcos[0].proto.srcdoc)

    def test_tarjeta_incompleta_usa_la_vista_generica(self):
        datos = json.loads(json.dumps(DATOS))
        del datos["contenido_adaptado"]["items"][0]["dorso"]
        at = correr(datos)
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.get("iframe")), 0)
        self.assertIn("*Frente:*", " ".join(m.value for m in at.markdown))


if __name__ == "__main__":
    unittest.main()
