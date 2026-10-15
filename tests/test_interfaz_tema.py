"""Pruebas de la identidad visual "Bosque sereno": tema de Streamlit, contrastes y logo."""

from pathlib import Path
import sys
import tomllib
import unittest
import xml.etree.ElementTree as ET

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

from streamlit import config as config_streamlit

import marca

CONFIG = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8"))


def _luminancia(hexa):
    canales = [int(hexa.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    canales = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * canales[0] + 0.7152 * canales[1] + 0.0722 * canales[2]


def contraste(color_a, color_b):
    """Razón de contraste WCAG entre dos colores HEX (de 1 a 21)."""
    claro, oscuro = sorted((_luminancia(color_a), _luminancia(color_b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


class ConfigDelTema(unittest.TestCase):
    def test_todas_las_claves_existen_en_streamlit(self):
        """Streamlit ignora en silencio una clave mal escrita; esta prueba la detecta."""
        validas = config_streamlit._config_options_template
        for seccion in ("server", "theme", "theme.light", "theme.dark"):
            tabla = CONFIG
            for parte in seccion.split("."):
                tabla = tabla[parte]
            for clave, valor in tabla.items():
                if isinstance(valor, dict):  # subtablas light/dark se revisan aparte
                    continue
                with self.subTest(clave=f"{seccion}.{clave}"):
                    self.assertIn(f"{seccion}.{clave}", validas)

    def test_el_limite_de_subida_se_conserva(self):
        self.assertEqual(CONFIG["server"]["maxUploadSize"], 10)


class Contrastes(unittest.TestCase):
    """Objetivos WCAG 2.2 AA: 4.5:1 texto normal, 3:1 bordes de controles y botones contra el fondo."""

    def _revisar(self, tema):
        t = CONFIG["theme"][tema]
        casos = [
            ("texto / fondo", t["textColor"], t["backgroundColor"], 4.5),
            ("texto / superficie", t["textColor"], t["secondaryBackgroundColor"], 4.5),
            ("texto blanco del botón / primario", "#FFFFFF", t["primaryColor"], 4.5),
            ("primario / fondo", t["primaryColor"], t["backgroundColor"], 3),
            ("enlace / fondo", t["linkColor"], t["backgroundColor"], 4.5),
            ("borde / fondo", t["borderColor"], t["backgroundColor"], 3),
        ]
        for nombre, primero, segundo, minimo in casos:
            with self.subTest(tema=tema, par=nombre):
                self.assertGreaterEqual(round(contraste(primero, segundo), 2), minimo)

    def test_tema_claro(self):
        self._revisar("light")

    def test_tema_oscuro(self):
        self._revisar("dark")


class Logo(unittest.TestCase):
    def test_los_svg_existen_y_tienen_titulo_accesible(self):
        for ruta in (marca.LOGO_CLARO, marca.LOGO_OSCURO, marca.ICONO):
            with self.subTest(archivo=ruta.name):
                raiz = ET.parse(ruta).getroot()
                self.assertTrue(raiz.tag.endswith("svg"))
                self.assertIsNotNone(raiz.find("{http://www.w3.org/2000/svg}title"))

    def test_el_logo_cambia_segun_el_tema(self):
        self.assertEqual(marca.logo_para("dark"), marca.LOGO_OSCURO)
        self.assertEqual(marca.logo_para("light"), marca.LOGO_CLARO)
        self.assertEqual(marca.logo_para(None), marca.LOGO_CLARO)  # sin dato del navegador: claro


if __name__ == "__main__":
    unittest.main()
