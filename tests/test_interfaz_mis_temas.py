"""Pruebas de Mis temas: cuántos temas hay, tarjetas y abrir un tema."""

import unittest

from apoyo_interfaz import abrir_pagina, textos

from cliente_api import ClienteMock
MIS_TEMAS = "paginas.estudiante.mis_temas:mostrar"


class ClienteSinTemas(ClienteMock):
    def listar_temas(self):
        return []


class ClienteUnTema(ClienteMock):
    def listar_temas(self):
        return super().listar_temas()[:1]


class PaginaMisTemas(unittest.TestCase):
    def test_mis_temas_sin_estado_ni_filtros(self):
        # Mientras no exista la evaluación, no hay estados que mostrar
        at = abrir_pagina(MIS_TEMAS)
        self.assertEqual(at.title[0].value, "Mis temas")
        self.assertIn("Tienes 2 temas asignados.", textos(at.caption))
        self.assertEqual(len(at.metric), 0)
        self.assertEqual(len(at.get("button_group")), 0)
        self.assertFalse(any("badge[" in m for m in textos(at.markdown)))

    def test_un_solo_tema_en_singular(self):
        at = abrir_pagina(MIS_TEMAS, cliente=ClienteUnTema())
        self.assertIn("Tienes 1 tema asignado.", textos(at.caption))

    def test_una_tarjeta_por_tema_sin_barra(self):
        at = abrir_pagina(MIS_TEMAS)
        markdown = textos(at.markdown)
        self.assertIn("**Redes en OCI**", markdown)
        self.assertIn("**Seguridad en la nube**", markdown)
        self.assertNotIn("**Herramientas de datos**", markdown)  # no está asignado
        self.assertIn("1 documento", textos(at.caption))
        self.assertEqual(len(at.get("progress")), 0)

    def test_abrir_tema_guarda_cual_se_eligio(self):
        at = abrir_pagina(MIS_TEMAS).button(key="abrir_t-seguridad").click().run()
        self.assertEqual(at.session_state["tema_elegido"], "t-seguridad")

    def test_sin_temas_asignados(self):
        at = abrir_pagina(MIS_TEMAS, cliente=ClienteSinTemas())
        self.assertIn("Todavía no tienes temas asignados. Cuando la institución te asigne uno, aparecerá aquí.",
                      textos(at.info))

    def test_no_pide_contraer_el_menu(self):
        self.assertNotIn("menu_pedido", abrir_pagina(MIS_TEMAS).session_state)

    def test_solo_para_estudiantes(self):
        at = abrir_pagina(MIS_TEMAS, usuario="admin")
        self.assertIn("No tienes permiso para ver esta página.", textos(at.error))


if __name__ == "__main__":
    unittest.main()
