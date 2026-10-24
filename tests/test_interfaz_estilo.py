"""Pruebas del único CSS de la app: solo toca el menú lateral y solo lo usa inicio.py."""

from pathlib import Path
import re
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import estilo


class UnicoCss(unittest.TestCase):
    def test_solo_toca_el_menu_lateral(self):
        selectores = [s.strip() for s in re.findall(r"([^{}]+)\{", estilo.CSS)]
        self.assertTrue(selectores)
        for selector in selectores:
            with self.subTest(selector=selector):
                self.assertTrue(selector.startswith('[data-testid="stSidebar'))

    def test_pega_el_contenido_propio_al_fondo(self):
        self.assertIn('[data-testid="stSidebarUserContent"]', estilo.CSS)
        self.assertIn("margin-top: auto", estilo.CSS)

    def test_ningun_otro_archivo_escribe_css(self):
        # flashcards.py lleva su <style> dentro del iframe del componente: no afecta a la app
        for ruta in (RAIZ / "app").rglob("*.py"):
            if ruta.name in ("estilo.py", "flashcards.py"):
                continue
            with self.subTest(archivo=ruta.name):
                self.assertNotIn("<style", ruta.read_text(encoding="utf-8"))

    def test_inicio_lo_aplica(self):
        self.assertIn("estilo.aplicar()", (RAIZ / "app" / "inicio.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
