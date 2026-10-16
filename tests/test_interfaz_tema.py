"""Pruebas de la identidad visual "Bosque sereno": tema de Streamlit, contrastes y logo."""

from pathlib import Path
import re
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
        for seccion in ("client", "server", "theme", "theme.light", "theme.dark", "theme.light.sidebar", "theme.dark.sidebar"):
            tabla = CONFIG
            for parte in seccion.split("."):
                tabla = tabla[parte]
            for clave, valor in tabla.items():
                if isinstance(valor, dict):  # subtablas light/dark se revisan aparte
                    continue
                with self.subTest(clave=f"{seccion}.{clave}"):
                    self.assertIn(f"{seccion}.{clave}", validas)

    def test_no_se_muestran_errores_tecnicos_en_bruto(self):
        # Spec §7: un error inesperado no debe mostrar el traceback a quien estudia
        self.assertEqual(CONFIG["client"]["showErrorDetails"], "none")
        self.assertIn("client.showErrorDetails", config_streamlit._config_options_template)

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

    def _revisar_menu(self, tema):
        m = CONFIG["theme"][tema]["sidebar"]
        casos = [
            ("texto / fondo del menú", m["textColor"], m["backgroundColor"], 4.5),
            ("texto / opción activa", m["textColor"], m["secondaryBackgroundColor"], 4.5),
            ("borde / fondo del menú", m["borderColor"], m["backgroundColor"], 3),
        ]
        for nombre, primero, segundo, minimo in casos:
            with self.subTest(tema=tema, par=nombre):
                self.assertGreaterEqual(round(contraste(primero, segundo), 2), minimo)

    def test_menu_claro(self):
        self._revisar_menu("light")

    def test_menu_oscuro(self):
        self._revisar_menu("dark")

    def test_oscuro_usa_la_paleta_b(self):
        t = CONFIG["theme"]["dark"]
        self.assertEqual((t["backgroundColor"], t["secondaryBackgroundColor"], t["primaryColor"]),
                         ("#14201E", "#1E2B28", "#3A8277"))


SVG = "{http://www.w3.org/2000/svg}"


class Logo(unittest.TestCase):
    def test_los_svg_existen_y_tienen_titulo_accesible(self):
        for ruta in (marca.LOGO, marca.LOGO_MENU, marca.ICONO):
            with self.subTest(archivo=ruta.name):
                raiz = ET.parse(ruta).getroot()
                self.assertTrue(raiz.tag.endswith("svg"))
                self.assertIsNotNone(raiz.find(f"{SVG}title"))

    def test_hojas_sin_tallo(self):
        # La versión 2.1 quita el tallo blanco: ningún trazo con stroke
        for ruta in (marca.LOGO, marca.LOGO_MENU, marca.ICONO):
            with self.subTest(archivo=ruta.name):
                self.assertNotIn("stroke", ruta.read_text(encoding="utf-8"))

    def test_color_del_texto_segun_el_fondo(self):
        self.assertIn('fill="#205E58" d="M90.69', marca.LOGO.read_text(encoding="utf-8"))
        self.assertIn('fill="#EAF2EF" d="M90.69', marca.LOGO_MENU.read_text(encoding="utf-8"))

    def test_el_texto_ocupa_mas_de_la_mitad_del_alto(self):
        # Streamlit limita st.logo a 32 px de alto: el texto tiene que llenar esa altura para leerse
        alto_texto = 54.42 - 31.19  # alto de "NuevaMente" en las coordenadas del trazo
        for ruta in (marca.LOGO, marca.LOGO_MENU):
            with self.subTest(archivo=ruta.name):
                raiz = ET.parse(ruta).getroot()
                alto = float(raiz.get("viewBox").split()[3])
                escala = float(re.search(r"scale\(([\d.]+)\)", raiz.find(f"{SVG}g[@id='texto']").get("transform")).group(1))
                self.assertGreaterEqual(alto_texto * escala / alto, 0.5)

    def test_ya_no_hay_logo_por_tema(self):
        self.assertFalse((marca.ASSETS / "logo_nuevamente_oscuro.svg").exists())
        self.assertFalse(hasattr(marca, "logo_para"))

    def test_favicon_png_con_esquinas_transparentes(self):
        # PNG y no SVG: Safari y otros navegadores no muestran favicons SVG
        from PIL import Image
        imagen = Image.open(marca.FAVICON)
        self.assertEqual((imagen.format, imagen.mode), ("PNG", "RGBA"))
        self.assertEqual(imagen.getpixel((0, 0))[3], 0)  # esquina transparente
        self.assertEqual(imagen.getpixel((imagen.width // 2, imagen.height // 2))[3], 255)

    def test_inicio_usa_el_favicon_png(self):
        inicio = (RAIZ / "app" / "inicio.py").read_text(encoding="utf-8")
        self.assertNotIn("page_icon=str(marca.ICONO)", inicio)
        self.assertEqual(inicio.count("page_icon=str(marca.FAVICON)"), 2)

    def test_logo_principal_segun_el_modo(self):
        # Landing e Iniciar sesión: el texto verde #205E58 no se lee sobre el fondo oscuro
        self.assertEqual(marca.logo_principal("dark"), marca.LOGO_MENU)
        self.assertEqual(marca.logo_principal("light"), marca.LOGO)
        self.assertEqual(marca.logo_principal(None), marca.LOGO)
        for pagina in ("landing.py", "acceso.py"):
            with self.subTest(pagina=pagina):
                codigo = (RAIZ / "app" / "paginas" / pagina).read_text(encoding="utf-8")
                self.assertIn("marca.logo_principal(st.context.theme.type)", codigo)
                self.assertNotIn("str(marca.LOGO)", codigo)

    def test_el_menu_usa_siempre_el_logo_del_menu(self):
        inicio = (RAIZ / "app" / "inicio.py").read_text(encoding="utf-8")
        self.assertIn("st.logo(str(marca.LOGO_MENU)", inicio)


if __name__ == "__main__":
    unittest.main()
