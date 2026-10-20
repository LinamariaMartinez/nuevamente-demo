"""Pruebas del admin: Documentos, Configuración y Material en revisión."""

import json
import unittest

from apoyo_interfaz import RAIZ, abrir_pagina, columnas_principales, textos

from cliente_api import ClienteMock, ErrorCliente
from contrato import Tema
from paginas.admin.documentos import temas_por_documento, validar_archivo

DOCUMENTOS = "paginas.admin.documentos:mostrar"
CONFIGURACION = "paginas.admin.configuracion:mostrar"
REVISION = "paginas.admin.revision:mostrar"
MB = 1024 * 1024
ABRIR_GUION = f"abrir_{json.loads((RAIZ / 'app' / 'mocks' / 'guion.json').read_text(encoding='utf-8'))['id']}"


class ClienteQueFalla(ClienteMock):
    def listar_documentos(self):
        raise ErrorCliente("no_disponible", "Connection refused")

    def obtener_configuracion(self):
        raise ErrorCliente("no_disponible", "Connection refused")


class ReglasDeArchivos(unittest.TestCase):
    def test_validar_archivo(self):
        self.assertIsNone(validar_archivo("guia.pdf", MB))
        self.assertEqual(validar_archivo("foto.png", MB), "Solo se aceptan archivos PDF, Markdown o TXT.")
        self.assertEqual(validar_archivo("vacio.md", 0), "El archivo está vacío.")
        self.assertEqual(validar_archivo("grande.txt", 11 * MB), "El archivo supera 10 MB.")

    def test_temas_por_documento(self):
        x, y = {"id": "d-x", "titulo": "X"}, {"id": "d-y", "titulo": "Y"}
        temas = [Tema(id_tema="a", nombre="Redes", documentos=[x]),
                 Tema(id_tema="b", nombre="Nube", documentos=[x, y])]
        self.assertEqual(temas_por_documento(temas), {"d-x": ["Redes", "Nube"], "d-y": ["Nube"]})


class PaginaDocumentos(unittest.TestCase):
    def test_lista_con_titulo_tipo_fragmentos_y_temas(self):
        at = abrir_pagina(DOCUMENTOS, usuario="admin")
        self.assertEqual(at.title[0].value, "Documentos")
        self.assertIn("**Redes VCN en OCI**", textos(at.markdown))
        self.assertIn("oci_redes_vcn.pdf", textos(at.caption))
        texto = [t.value for t in at.text]
        self.assertIn("PDF", texto)
        self.assertIn("24 fragmentos", texto)
        self.assertIn("Redes en OCI", texto)

    def test_error_de_la_api_muestra_detalle_al_admin(self):
        at = abrir_pagina(DOCUMENTOS, usuario="admin", cliente=ClienteQueFalla())
        self.assertIn(ErrorCliente.MENSAJES["no_disponible"], textos(at.error))
        self.assertEqual(at.expander[0].label, "Ver detalle")

    def test_solo_para_admin(self):
        at = abrir_pagina(DOCUMENTOS, usuario="laura")
        self.assertIn("No tienes permiso para ver esta página.", textos(at.error))


class PaginaConfiguracion(unittest.TestCase):
    def test_guardar_el_sector(self):
        cliente = ClienteMock()
        at = abrir_pagina(CONFIGURACION, usuario="admin", cliente=cliente)
        at = at.selectbox(key="sector").set_value("Salud").run()
        at = at.button(key="guardar_sector").click().run()
        self.assertIn("Sector guardado: Salud", textos(at.success))
        self.assertEqual(cliente.obtener_configuracion().sector, "Salud")

    def test_sin_api_muestra_el_error(self):
        at = abrir_pagina(CONFIGURACION, usuario="admin", cliente=ClienteQueFalla())
        self.assertIn(ErrorCliente.MENSAJES["no_disponible"], textos(at.error))


class ClienteSinConfiguracion(ClienteMock):
    def guardar_configuracion(self, sector):
        raise ErrorCliente("rechazado", "404", mensaje="Esta opción todavía no está disponible en el servidor.")


class ConfiguracionSinBackend(unittest.TestCase):
    def test_guardar_sin_la_ruta_avisa_y_no_se_rompe(self):
        at = abrir_pagina(CONFIGURACION, usuario="admin", cliente=ClienteSinConfiguracion())
        at = at.button(key="guardar_sector").click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("Esta opción todavía no está disponible en el servidor.", textos(at.error))


ID_GUION = ABRIR_GUION.removeprefix("abrir_")


def abrir_guion(cliente=None):
    return abrir_pagina(REVISION, usuario="admin", cliente=cliente).button(key=ABRIR_GUION).click().run()


class AprobarYRechazar(unittest.TestCase):
    def test_aprobar_lo_saca_de_la_lista(self):
        cliente = ClienteMock()
        at = abrir_guion(cliente).button(key=f"aprobar_{ID_GUION}").click().run()
        # Revisión final: todavía no hay una pantalla donde quien estudia vea el material aprobado
        self.assertIn("Material aprobado.", textos(at.success))
        self.assertIn("No hay material pendiente de revisión.", textos(at.info))
        self.assertEqual(cliente.listar_paquetes_revision(), [])

    def test_rechazar_pide_confirmacion(self):
        cliente = ClienteMock()
        at = abrir_guion(cliente).button(key=f"rechazar_{ID_GUION}").click().run()
        self.assertIn("¿Rechazar este material? Se eliminará y se podrá generar de nuevo.", textos(at.warning))
        self.assertEqual(len(cliente.listar_paquetes_revision()), 1)  # todavía no se rechazó
        at = at.button(key=f"cancelar_rechazar_{ID_GUION}").click().run()
        self.assertEqual(len(cliente.listar_paquetes_revision()), 1)
        at = at.button(key=f"rechazar_{ID_GUION}").click().run()
        at = at.button(key=f"confirmar_rechazar_{ID_GUION}").click().run()
        self.assertIn("Material rechazado: se eliminó y se puede generar de nuevo.", textos(at.success))
        self.assertEqual(cliente.listar_paquetes_revision(), [])

    def test_admin_ve_las_metricas_internas(self):
        at = abrir_guion()
        self.assertIn("Anclaje en fuentes", [m.label for m in at.metric])
        self.assertIn("Observaciones del revisor", [e.label for e in at.expander])

    def test_exportar_json_usa_el_id(self):
        boton = abrir_guion().get("download_button")[0].proto
        self.assertEqual(boton.label, "Exportar JSON")


class PaginaRevision(unittest.TestCase):
    def test_lista_a_la_izquierda_y_material_a_la_derecha(self):
        at = abrir_pagina(REVISION, usuario="admin")
        izquierda, derecha = columnas_principales(at)
        self.assertIn(ABRIR_GUION, [b.key for b in izquierda.button])
        self.assertIn("Abre un material de la lista para verlo aquí.", [i.value for i in derecha.info])
        at = at.button(key=ABRIR_GUION).click().run()
        izquierda, derecha = columnas_principales(at)
        self.assertEqual(len(derecha.header), 1)

    def test_lista_abrir_y_exportar(self):
        at = abrir_pagina(REVISION, usuario="admin")
        self.assertEqual(at.title[0].value, "Material en revisión")
        at = at.button(key=ABRIR_GUION).click().run()
        self.assertEqual(len(at.header), 1)
        self.assertEqual(at.get("download_button")[0].proto.label, "Exportar JSON")

    def test_revision_pide_contraer_el_menu_al_abrir_un_material(self):
        at = abrir_pagina(REVISION, usuario="admin")
        self.assertNotIn("menu_pedido", at.session_state)
        at = at.button(key=ABRIR_GUION).click().run()
        self.assertEqual(at.session_state["menu_pedido"], "collapsed")

    def test_documentos_no_pide_contraer_el_menu(self):
        self.assertNotIn("menu_pedido", abrir_pagina(DOCUMENTOS, usuario="admin").session_state)

    def test_solo_para_admin(self):
        at = abrir_pagina(REVISION, usuario="laura")
        self.assertIn("No tienes permiso para ver esta página.", textos(at.error))


if __name__ == "__main__":
    unittest.main()
