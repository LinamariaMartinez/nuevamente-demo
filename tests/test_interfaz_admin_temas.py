"""Pruebas de Temas (admin): crear, editar y retirar, con confirmación y sin perder lo escrito."""

import unittest

from apoyo_interfaz import abrir_pagina, textos

from cliente_api import ClienteMock
from contrato import Documento

TEMAS = "paginas.admin.temas:mostrar"


class ClienteSinIndexados(ClienteMock):
    def listar_documentos(self):
        return [Documento(nombre="malo.pdf", estado="error", error="Sin texto")]


def crear(at, nombre, documentos):
    at.text_input(key="nuevo_nombre").input(nombre)
    at.multiselect(key="nuevo_documentos").set_value(documentos)
    return at.button(key="nuevo_enviar").click().run()


class PaginaTemas(unittest.TestCase):
    def test_lista_los_temas_con_sus_documentos(self):
        at = abrir_pagina(TEMAS, usuario="admin")
        self.assertEqual(at.title[0].value, "Temas")
        self.assertIn("**Redes en OCI**", textos(at.markdown))
        self.assertIn("Documentos: oci_redes_vcn.pdf", textos(at.caption))

    def test_solo_documentos_indexados_en_el_formulario(self):
        at = abrir_pagina(TEMAS, usuario="admin")
        self.assertNotIn("manual_escaneado.pdf", at.multiselect(key="nuevo_documentos").options)

    def test_crear_tema(self):
        cliente = ClienteMock()
        at = crear(abrir_pagina(TEMAS, usuario="admin", cliente=cliente), "Bases de datos", ["guia_datos.txt"])
        self.assertIn("Tema creado: Bases de datos", textos(at.success))
        self.assertIn("**Bases de datos**", textos(at.markdown))
        self.assertEqual(len(cliente.listar_temas()), 4)

    def test_nombre_repetido_avisa_y_conserva_lo_escrito(self):
        at = crear(abrir_pagina(TEMAS, usuario="admin"), "redes en oci", ["guia_datos.txt"])
        self.assertIn("Ya existe un tema con ese nombre.", textos(at.error))
        self.assertEqual(at.text_input(key="nuevo_nombre").value, "redes en oci")

    def test_sin_documentos_elegidos_avisa(self):
        at = crear(abrir_pagina(TEMAS, usuario="admin"), "Vacío", [])
        self.assertIn("Escribe un nombre y elige al menos un documento.", textos(at.warning))

    def test_editar_tema(self):
        cliente = ClienteMock()
        at = abrir_pagina(TEMAS, usuario="admin", cliente=cliente)
        at = at.button(key="editar_t-redes").click().run()
        at.text_input(key="editar_t-redes_nombre").input("Redes y subredes en OCI")
        at = at.button(key="editar_t-redes_enviar").click().run()
        self.assertIn("Cambios guardados: Redes y subredes en OCI", textos(at.success))
        self.assertIn("Redes y subredes en OCI", [t.nombre for t in cliente.listar_temas()])

    def test_retirar_pide_confirmacion(self):
        cliente = ClienteMock()
        at = abrir_pagina(TEMAS, usuario="admin", cliente=cliente)
        at = at.button(key="retirar_t-datos").click().run()
        self.assertIn("¿Retirar «Herramientas de datos»? Quienes lo tienen asignado dejarán de verlo.", textos(at.warning))
        self.assertEqual(len(cliente.listar_temas()), 3)  # todavía no se retiró
        at = at.button(key="cancelar_retirar_t-datos").click().run()
        self.assertEqual(len(cliente.listar_temas()), 3)
        at = at.button(key="retirar_t-datos").click().run()
        at = at.button(key="confirmar_retirar_t-datos").click().run()
        self.assertIn("Tema retirado: Herramientas de datos", textos(at.success))
        self.assertEqual(len(cliente.listar_temas()), 2)

    def test_sin_documentos_indexados_lleva_a_documentos(self):
        at = abrir_pagina(TEMAS, usuario="admin", cliente=ClienteSinIndexados())
        self.assertIn("Todavía no hay documentos indexados. Sube al menos uno para crear un tema.", textos(at.info))
        self.assertEqual(at.button(key="ir_documentos").label, "Ir a Documentos")

    def test_solo_para_admin(self):
        at = abrir_pagina(TEMAS, usuario="laura")
        self.assertIn("No tienes permiso para ver esta página.", textos(at.error))


if __name__ == "__main__":
    unittest.main()
