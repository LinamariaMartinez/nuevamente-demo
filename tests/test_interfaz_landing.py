"""Pruebas de la landing (v2.4): HTML y CSS con st.html, sin JavaScript, y el botón real de Iniciar sesión."""

import json
import re
import unittest

from apoyo_interfaz import RAIZ, abrir_pagina

from cliente_api import ClienteMock
from paginas import landing

LANDING = "paginas.landing:mostrar"


class ClienteReal(ClienteMock):
    """Se comporta como la API real: no hay cuentas de demostración."""

    es_mock = False


def _html(at):
    return " ".join(elemento.proto.body for elemento in at.get("html"))


def _texto(html):
    """Texto visible aproximado: sin etiquetas y con espacios normales (sin espacio antes de coma o punto)."""
    return re.sub(r"\s+([,.;])", r"\1", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))


class HtmlLanding(unittest.TestCase):
    def setUp(self):
        self.html = landing.html_principal()

    def test_plantilla_completa_y_sin_lo_que_st_html_quitaria(self):
        self.assertNotIn("${", self.html)
        # st.html limpia el HTML: quita <script> y <svg>. Los íconos van como <img> con el SVG en data:
        for etiqueta in ("<script", "<svg", "<iframe"):
            with self.subTest(etiqueta=etiqueta):
                self.assertNotIn(etiqueta, self.html + landing.html_pie())
        self.assertIn('src="data:image/svg+xml;base64,', self.html)

    def test_titular_y_explicacion(self):
        texto = _texto(self.html)
        self.assertIn(landing.TITULAR, texto)
        self.assertIn(landing.EXPLICACION, texto)

    def test_secciones_pasos_pilares_y_oci(self):
        texto = _texto(self.html)
        for nombre, _ in landing.PASOS:
            self.assertIn(nombre, texto)
        for nombre, _, explicacion, _, _ in landing.POR_DENTRO:
            self.assertIn(nombre, texto)
            self.assertIn(explicacion, texto)
        for frase in ("Streamlit Community Cloud", "OCI Object Storage", "Always Free", "API de Gemini"):
            with self.subTest(frase=frase):
                self.assertIn(frase, texto)

    def test_cada_enlace_interno_tiene_su_destino(self):
        for ancla in set(re.findall(r'href="#([\w-]+)"', self.html)):
            with self.subTest(ancla=ancla):
                self.assertIn(f'id="{ancla}"', self.html)

    def test_iniciar_sesion_del_menu_abre_la_pagina_de_acceso(self):
        # st.html no puede usar st.switch_page: el enlace va a la dirección de la página (url_path="acceso")
        self.assertRegex(self.html, r'<a href="acceso"[^>]*>Iniciar sesión</a>')
        self.assertIn('url_path="acceso"', (RAIZ / "app" / "inicio.py").read_text(encoding="utf-8"))

    def test_cada_etiqueta_tiene_su_control(self):
        """Lo interactivo es CSS: cada <label for> necesita su radio o casilla."""
        controles = set(re.findall(r'<input[^>]*id="([\w-]+)"', self.html))
        etiquetas = set(re.findall(r'<label[^>]*for="([\w-]+)"', self.html))
        self.assertEqual(etiquetas, controles)
        self.assertEqual(len(controles), 3 + len(landing.FORMATOS) + 1 + 3 + len(landing.POR_DENTRO))

    def test_flechas_entre_agentes_se_ocultan_en_el_celular(self):
        # .nm-conector se oculta en pantallas angostas; sin la clase, la flecha queda apuntando al vacío
        agentes = landing._agentes()
        self.assertEqual(agentes.count("nm-flujo-punto"), len(landing.AGENTES) - 1)
        self.assertEqual(agentes.count('class="nm-conector"'), len(landing.AGENTES) - 1)

    def test_el_json_de_por_dentro_usa_los_campos_del_contrato(self):
        # "Rigor que se puede verificar": quien abra /docs debe ver los mismos nombres (contrato común, F06)
        bloques = {}
        for _, _, _, _, codigo in landing.POR_DENTRO:
            bloques.update(json.loads("{" + codigo + "}"))
        self.assertEqual(set(bloques["fuentes"][0]), {"documento_id", "documento", "fragmento", "pagina", "extracto"})
        self.assertIn(bloques["status"], ("exito", "requiere_revision"))
        self.assertEqual(set(bloques["evaluacion_calidad"]),
                         {"anclaje_fuente_score", "calidad_pedagogica_score", "cumplimiento_formato_score",
                          "claridad_pedagogica", "observaciones", "intentos_revision"})
        self.assertEqual(set(bloques["metadatos"]),
                         {"tiempo_estimado_estudio_minutos", "conceptos_clave", "prerrequisitos", "perfil_aplicado",
                          "formato_generado", "nicho_sector", "nivel_detalle"})

    def test_no_promete_revisar_todo_el_material(self):
        # Solo lo que no pasa el control de calidad queda en revisión; lo demás llega directo a quien estudia
        texto = _texto(self.html)
        self.assertNotIn("antes de que llegue a nadie", texto)
        self.assertNotIn("aprueba antes de publicar", texto)

    def test_tema_oscuro(self):
        self.assertIn('class="nm"', self.html)
        oscuro = landing.html_principal(tema_oscuro=True)
        self.assertIn('class="nm nm-oscuro"', oscuro)


class PaginaLanding(unittest.TestCase):
    def test_boton_de_entrada(self):
        at = abrir_pagina(LANDING, usuario=None)
        self.assertEqual(at.button(key="ir_acceso").label, "Iniciar sesión")
        self.assertIn(landing.CIERRE_TITULO, _html(at))

    def test_cuentas_de_demostracion_solo_en_modo_mock(self):
        html = _html(abrir_pagina(LANDING, usuario=None))
        self.assertIn("laura / demo-estudiante", html)
        html = _html(abrir_pagina(LANDING, usuario=None, cliente=ClienteReal()))
        self.assertNotIn("laura", html)
        self.assertIn(landing.SIN_CUENTAS_DEMO, html)


if __name__ == "__main__":
    unittest.main()
