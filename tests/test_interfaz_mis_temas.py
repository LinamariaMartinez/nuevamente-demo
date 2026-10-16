"""Pruebas de Mis temas: métricas, filtro en píldoras, tarjetas y abrir un tema."""

import unittest

from apoyo_interfaz import abrir_pagina, textos

from cliente_api import ClienteMock
from contrato import Tema
from paginas.estudiante.mis_temas import COLOR_ESTADO, filtrar

MIS_TEMAS = "paginas.estudiante.mis_temas:mostrar"


class ClienteSinTemas(ClienteMock):
    def listar_temas(self):
        return []


def tema(id_tema):
    return Tema(id_tema=id_tema, nombre=id_tema, documentos=["a.pdf"])


class ReglasDelFiltro(unittest.TestCase):
    def test_pendientes_es_todo_lo_que_no_esta_aprobado(self):
        lista = [(tema("a"), "Aprobado"), (tema("b"), "Pendiente"), (tema("c"), "Sin evaluación"), (tema("d"), "Sin intentos")]
        self.assertEqual([t.id_tema for t, _ in filtrar(lista, "Aprobados")], ["a"])
        self.assertEqual([t.id_tema for t, _ in filtrar(lista, "Pendientes")], ["b", "c", "d"])
        self.assertEqual(len(filtrar(lista, "Todos")), 4)

    def test_cada_estado_tiene_su_color(self):
        self.assertEqual(COLOR_ESTADO, {"Pendiente": "orange", "Aprobado": "green",
                                        "Sin intentos": "red", "Sin evaluación": "gray"})


class PaginaMisTemas(unittest.TestCase):
    def test_metricas_de_los_temas_asignados(self):
        at = abrir_pagina(MIS_TEMAS)
        self.assertEqual(at.title[0].value, "Mis temas")
        self.assertEqual([(m.label, m.value) for m in at.metric],
                         [("Asignados", "2"), ("Pendientes", "2"), ("Aprobados", "0")])

    def test_una_tarjeta_por_tema_con_su_estado_y_sin_barra(self):
        at = abrir_pagina(MIS_TEMAS)
        markdown = textos(at.markdown)
        self.assertIn("**Redes en OCI**", markdown)
        self.assertIn("**Seguridad en la nube**", markdown)
        self.assertNotIn("**Herramientas de datos**", markdown)  # no está asignado
        self.assertEqual(markdown.count(":gray-badge[Sin evaluación]"), 2)
        self.assertIn("1 documento", textos(at.caption))
        self.assertEqual(len(at.get("progress")), 0)

    def test_filtro_de_aprobados_sin_resultados(self):
        at = abrir_pagina(MIS_TEMAS)
        at = at.pills(key="filtro_temas").set_value("Aprobados").run()
        self.assertIn("No hay temas en este filtro.", textos(at.info))

    def test_abrir_tema_guarda_cual_se_eligio(self):
        at = abrir_pagina(MIS_TEMAS).button(key="abrir_t-seguridad").click().run()
        self.assertEqual(at.session_state["tema_elegido"], "t-seguridad")

    def test_sin_temas_asignados(self):
        at = abrir_pagina(MIS_TEMAS, cliente=ClienteSinTemas())
        self.assertIn("Todavía no tienes temas asignados. Cuando la institución te asigne uno, aparecerá aquí.",
                      textos(at.info))
        self.assertEqual(len(at.metric), 0)

    def test_no_pide_contraer_el_menu(self):
        self.assertNotIn("menu_pedido", abrir_pagina(MIS_TEMAS).session_state)

    def test_solo_para_estudiantes(self):
        at = abrir_pagina(MIS_TEMAS, usuario="admin")
        self.assertIn("No tienes permiso para ver esta página.", textos(at.error))


if __name__ == "__main__":
    unittest.main()
