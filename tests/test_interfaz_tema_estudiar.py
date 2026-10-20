"""Pruebas de la página del tema (Estudiar), con el cliente mock o con clientes falsos."""

import unittest

from apoyo_interfaz import RAIZ, abrir_pagina, columnas_principales, textos

from cliente_api import ClienteMock, ErrorCliente

TEMA = "paginas.estudiante.tema:mostrar"


def abrir(cliente=None, usuario="laura", tema="t-redes"):
    return abrir_pagina(TEMA, usuario=usuario, cliente=cliente, estado={"tema_elegido": tema})


def generar(at, formato="Quiz", pedido=""):
    at.selectbox(key="formato").set_value(formato).run()
    if pedido:
        at.text_input(key="pedido").input(pedido).run()
    return at.button(key="generar").click().run()


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


class ClienteVencido(ClienteMock):
    def generar_paquete(self, solicitud):
        raise ErrorCliente("sesion_vencida", "401")


class ClienteCaido(ClienteMock):
    es_mock = False

    def salud(self):
        return False


class PaginaDelTema(unittest.TestCase):
    def test_muestra_nombre_descripcion_y_documentos(self):
        at = abrir()
        self.assertEqual(at.title[0].value, "Redes en OCI")
        self.assertIn("Documentos de este tema: Redes VCN en OCI", textos(at.caption))
        self.assertIn("Modo demostración: datos de ejemplo", textos(at.info))

    def test_solo_para_estudiantes(self):
        at = abrir(usuario="admin")
        self.assertIn("No tienes permiso para ver esta página.", textos(at.error))

    def test_genera_y_muestra_el_material(self):
        at = generar(abrir(), formato="Flashcards")
        self.assertEqual(len(at.header), 1)
        self.assertEqual(at.session_state["paquete"].metadatos.tema, "Redes en OCI")  # pedido vacío = todo el tema

    def test_quiz_de_estudio_avisa_que_es_practica(self):
        at = generar(abrir(), formato="Quiz")
        self.assertIn("Práctica: no cuenta para tu nota.", textos(at.caption))

    def test_un_segundo_quiz_empieza_en_blanco(self):
        # Viene del PBI02: un quiz nuevo no hereda respuestas ni calificación del anterior
        at = generar(abrir(), formato="Quiz")
        primera = at.radio[0]
        primera.set_value(primera.options[0])
        calificar = next(b.key for b in at.button if b.key.endswith("_calificar"))
        at = at.button(key=calificar).click().run()
        self.assertIn("Tu puntaje", [m.label for m in at.metric])
        at = at.button(key="generar").click().run()
        self.assertNotIn("Tu puntaje", [m.label for m in at.metric])
        self.assertTrue(all(r.value is None for r in at.radio))

    def test_pedido_sin_contexto_muestra_el_mensaje_claro(self):
        at = generar(abrir(), pedido="tema inexistente")
        self.assertIn("No encontramos ese tema en los documentos cargados. Prueba con otras palabras.", textos(at.error))

    def test_material_en_revision_no_se_muestra_y_se_puede_pedir_otro(self):
        at = generar(abrir(), formato="Guion")
        self.assertIn("Este material necesita una revisión adicional antes de estar disponible.", textos(at.info))
        self.assertEqual(len(at.header), 0)
        at = at.button(key="reintentar").click().run()
        self.assertEqual(len(at.header), 1)

    def test_cambiar_el_formato_quita_el_material_anterior(self):
        at = generar(abrir(), formato="Flashcards")
        at = at.selectbox(key="formato").set_value("Resumen").run()
        self.assertEqual(len(at.header), 0)
        self.assertNotIn("paquete", at.session_state)

    def test_tiempo_agotado_conserva_lo_elegido_y_reintentar_funciona(self):
        cliente = ClienteQueFallaUnaVez()
        at = generar(abrir(cliente), formato="Flashcards", pedido="subredes")
        self.assertIn(ErrorCliente.MENSAJES["tiempo_agotado"], textos(at.error))
        self.assertEqual(len(at.expander), 0)  # el estudiante no ve el detalle técnico
        self.assertEqual(at.text_input(key="pedido").value, "subredes")
        at = at.button(key="reintentar").click().run()
        self.assertEqual(len(at.header), 1)
        self.assertEqual(cliente.llamadas, 2)

    def test_sesion_vencida_al_generar_vuelve_a_iniciar_sesion(self):
        at = generar(abrir(ClienteVencido()))
        self.assertNotIn("sesion", at.session_state)
        self.assertIn("Tu sesión terminó. Inicia sesión de nuevo.", textos(at.info))

    def test_tema_retirado_o_no_asignado_muestra_un_mensaje_amable(self):
        at = abrir(tema="t-datos")  # existe, pero no está asignado a Laura
        self.assertIn("Este tema ya no está disponible. Vuelve a Mis temas para ver los que tienes asignados.",
                      textos(at.info))
        self.assertEqual(len(at.error), 0)

    def test_formulario_a_la_izquierda_y_recuadro_reservado_a_la_derecha(self):
        izquierda, derecha = columnas_principales(abrir())
        self.assertIn("generar", [b.key for b in izquierda.button])
        self.assertIn("Elige tu nivel y formato y pulsa Generar material. Aquí aparecerá tu material.",
                      [i.value for i in derecha.info])

    def test_el_material_aparece_a_la_derecha(self):
        at = generar(abrir(), formato="Flashcards")
        izquierda, derecha = columnas_principales(at)
        self.assertEqual(len(derecha.header), 1)
        self.assertNotIn("Elige tu nivel y formato y pulsa Generar material. Aquí aparecerá tu material.",
                         [i.value for i in derecha.info])

    def test_pide_contraer_el_menu_solo_cuando_hay_material(self):
        at = abrir()
        self.assertNotIn("menu_pedido", at.session_state)
        at = generar(at, formato="Flashcards")
        self.assertEqual(at.session_state["menu_pedido"], "collapsed")

    def test_la_app_usa_pantalla_ancha(self):
        self.assertIn('layout="wide"', (RAIZ / "app" / "inicio.py").read_text(encoding="utf-8"))

    def test_api_caida_avisa_pero_deja_el_formulario(self):
        at = abrir(ClienteCaido())
        self.assertIn("El servicio no está disponible en este momento. Inténtalo de nuevo más tarde.", textos(at.warning))
        self.assertFalse(at.button(key="generar").disabled)


if __name__ == "__main__":
    unittest.main()
