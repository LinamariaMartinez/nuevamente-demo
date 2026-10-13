"""Pruebas de la página del estudiante con AppTest, en modo mock o con un cliente falso."""

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "app"))

from streamlit.testing.v1 import AppTest

from cliente_api import ClienteMock, ErrorCliente

APP = str(RAIZ / "tests" / "apps_interfaz" / "estudiante_app.py")


class ClienteQueFallaUnaVez(ClienteMock):
    """La primera generación se pasa del tiempo; la segunda funciona."""

    es_mock = False

    def __init__(self):
        super().__init__()
        self.llamadas = 0

    def generar_paquete(self, solicitud):
        self.llamadas += 1
        if self.llamadas == 1:
            raise ErrorCliente("tiempo_agotado", "Read timed out")
        return super().generar_paquete(solicitud)


class ClienteCaido(ClienteMock):
    es_mock = False

    def __init__(self):
        super().__init__()
        self.pidio_configuracion = False

    def salud(self):
        return False

    def obtener_configuracion(self):
        self.pidio_configuracion = True
        raise ErrorCliente("no_disponible", "Connection refused")


def abrir(cliente=None):
    at = AppTest.from_file(APP, default_timeout=10)
    if cliente is not None:
        at.session_state["cliente"] = cliente
    return at.run()


def pedir(at, tema, formato="Quiz"):
    at.text_input(key="tema").input(tema).run()
    at.selectbox(key="formato").set_value(formato).run()
    return at.button(key="generar").click().run()


@patch.dict(os.environ, {"MODO_API": "mock"})
class PaginaEstudiante(unittest.TestCase):
    def test_modo_mock_muestra_la_etiqueta_y_el_boton_esta_activo(self):
        # Activo siempre: si se desactivara con el tema vacío, el primer clic sin Enter se perdería
        at = abrir()
        self.assertIn("Modo demostración: datos de ejemplo", [i.value for i in at.info])
        self.assertFalse(at.button(key="generar").disabled)

    def test_generar_sin_tema_pide_escribirlo(self):
        at = abrir().button(key="generar").click().run()
        self.assertIn("Escribe un tema para generar tu material.", [w.value for w in at.warning])
        self.assertEqual(len(at.header), 0)

    def test_no_pide_nicho_y_muestra_el_sector_de_la_institucion(self):
        cliente = ClienteMock()
        cliente.guardar_configuracion("Salud")
        at = abrir(cliente)
        self.assertEqual([s.label for s in at.selectbox], ["Tu nivel", "Formato"])
        self.assertIn("Contexto de tu institución: Salud", [c.value for c in at.caption])

    def test_genera_y_muestra_el_paquete(self):
        at = pedir(abrir(), "Redes VCN", "Quiz")
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.header[0].value, "Quiz: componentes de red de una VCN")

    def test_tema_sin_contexto_muestra_el_mensaje_claro(self):
        at = pedir(abrir(), "Tema inexistente")
        self.assertIn("No encontré ese tema en los documentos cargados. Prueba con otras palabras.",
                      [e.value for e in at.error])

    def test_guion_no_aprobado_muestra_el_material_con_aviso(self):
        at = pedir(abrir(), "Redes VCN", "Guion")
        self.assertEqual(len(at.header), 1)
        self.assertEqual(len(at.warning), 1)

    def test_api_caida_avisa_pero_deja_el_formulario(self):
        cliente = ClienteCaido()
        at = abrir(cliente)
        self.assertIn("El servicio no está disponible en este momento.", [w.value for w in at.warning])
        self.assertEqual(len(at.text_input), 1)
        self.assertFalse(cliente.pidio_configuracion)  # no esperar otra petición que va a fallar

    def test_tiempo_agotado_conserva_el_tema_y_reintentar_funciona(self):
        cliente = ClienteQueFallaUnaVez()
        at = pedir(abrir(cliente), "Redes VCN")
        self.assertIn("La generación está tardando más de lo normal.", [e.value for e in at.error])
        self.assertEqual(at.text_input(key="tema").value, "Redes VCN")
        at = at.button(key="reintentar").click().run()
        self.assertEqual(len(at.error), 0)
        self.assertEqual(at.header[0].value, "Quiz: componentes de red de una VCN")
        self.assertEqual(cliente.llamadas, 2)

    def test_reintentar_con_el_tema_borrado_no_genera_ni_se_rompe(self):
        cliente = ClienteQueFallaUnaVez()
        at = pedir(abrir(cliente), "Redes VCN")
        at.text_input(key="tema").input("").run()
        at = at.button(key="reintentar").click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(cliente.llamadas, 1)


if __name__ == "__main__":
    unittest.main()
