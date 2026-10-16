"""Pruebas del punto de entrada: qué se ve sin sesión, con contraseña temporal y con el menú de cada rol."""

import unittest

from apoyo_interfaz import CUENTAS, RAIZ, abrir_pagina, textos

from streamlit.testing.v1 import AppTest

import menu
import paginas
from cliente_api import ClienteMock

INICIO = str(RAIZ / "app" / "inicio.py")


def abrir(usuario=None):
    at = AppTest.from_file(INICIO, default_timeout=10)
    cliente = ClienteMock()
    at.session_state["cliente"] = cliente
    if usuario is not None:
        at.session_state["sesion"] = cliente.iniciar_sesion(usuario, CUENTAS[usuario])
    return at.run()


class MenuPorRol(unittest.TestCase):
    def test_estudiante(self):
        self.assertEqual([e.titulo for e in menu.entradas("estudiante")], ["Mis temas"])

    def test_admin_agrupado_y_solo_lo_que_esta_listo(self):
        self.assertEqual([(e.seccion, e.titulo) for e in menu.entradas("admin")],
                         [("Contenido", "Documentos"), ("Contenido", "Temas"),
                          ("Contenido", "Material en revisión"), ("Ajustes", "Configuración")])

    def test_lo_que_falta_esta_declarado_pero_oculto(self):
        ocultas = {e.titulo for rol in menu.MENU for e in menu.MENU[rol] if not e.lista}
        self.assertEqual(ocultas, {"Evaluaciones", "Exámenes", "Usuarios", "Progreso"})


class PuntoDeEntrada(unittest.TestCase):
    def test_sin_sesion_solo_iniciar_sesion(self):
        at = abrir()
        self.assertEqual(at.text_input(key="acceso_usuario").label, "Usuario")
        self.assertEqual([b.key for b in at.sidebar.button], [])

    def test_contrasena_temporal_obliga_a_cambiarla(self):
        at = abrir("mateo")
        self.assertEqual(at.title[0].value, "Cambia tu contraseña")

    def test_estudiante_entra_a_mis_temas_y_ve_su_nombre(self):
        at = abrir("laura")
        self.assertEqual(at.title[0].value, "Mis temas")
        self.assertIn("**Laura Gómez**", textos(at.sidebar.markdown))
        self.assertIn("Estudiante", textos(at.sidebar.caption))
        self.assertEqual(set(paginas.DESTINOS), {"mis-temas", "tema"})  # ninguna página del admin

    def test_admin_entra_a_documentos(self):
        at = abrir("admin")
        self.assertEqual(at.title[0].value, "Documentos")
        self.assertIn("Administración", textos(at.sidebar.caption))
        self.assertEqual(set(paginas.DESTINOS), {"documentos", "temas", "revision", "configuracion"})

    def test_cerrar_sesion_vuelve_a_iniciar_sesion(self):
        at = abrir("laura").sidebar.button(key="cerrar_sesion").click().run()
        self.assertNotIn("sesion", at.session_state)
        self.assertIsNotNone(at.text_input(key="acceso_usuario"))

    def test_el_menu_se_contrae_con_el_material_y_vuelve_en_otra_pagina(self):
        # AppTest no recuerda st.switch_page entre ejecuciones con páginas-función: el cambio de página se
        # simula con la mini-app de pruebas, que aplica el estado del menú igual que inicio.py
        at = abrir_pagina("paginas.estudiante.tema:mostrar", estado={"tema_elegido": "t-redes", "aplicar_menu": True})
        self.assertEqual(at.session_state["menu_actual"], "auto")
        at = at.button(key="generar").click().run()
        self.assertEqual(at.session_state["menu_actual"], "collapsed")
        self.assertNotIn("menu_pedido", at.session_state)  # ya se aplicó
        at.session_state["pagina"] = "paginas.estudiante.mis_temas:mostrar"
        at = at.run()
        self.assertEqual(at.session_state["menu_actual"], "auto")

    def test_inicio_aplica_el_estado_del_menu_al_final(self):
        inicio = (RAIZ / "app" / "inicio.py").read_text(encoding="utf-8")
        self.assertLess(inicio.index("pagina.run()"), inicio.index("aplicar_estado_menu()"))
        self.assertEqual(abrir("laura").session_state["menu_actual"], "auto")

    def test_abrir_un_tema_lleva_a_su_pagina(self):
        at = abrir("laura").button(key="abrir_t-redes").click().run()
        self.assertEqual(at.title[0].value, "Redes en OCI")


if __name__ == "__main__":
    unittest.main()
