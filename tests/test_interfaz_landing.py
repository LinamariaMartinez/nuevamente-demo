"""Pruebas de la landing (v2.2): qué es NuevaMente, cómo funciona y acceso a la demo."""

import unittest

from apoyo_interfaz import abrir_pagina, textos

from cliente_api import ClienteMock
from paginas.landing import TITULAR

LANDING = "paginas.landing:mostrar"


class ClienteReal(ClienteMock):
    """Se comporta como la API real: no hay cuentas de demostración."""

    es_mock = False


class PaginaLanding(unittest.TestCase):
    def test_mensaje_principal_y_boton_de_entrada(self):
        at = abrir_pagina(LANDING, usuario=None)
        self.assertEqual(at.title[0].value, TITULAR)
        self.assertEqual(at.button(key="ir_acceso").label, "Iniciar sesión")
        self.assertIn("[Ver cómo funciona](#como-funciona)", textos(at.markdown))

    def test_como_funciona_y_por_dentro(self):
        at = abrir_pagina(LANDING, usuario=None)
        self.assertEqual([s.value for s in at.subheader], ["Cómo funciona", "Por dentro"])
        markdown = textos(at.markdown)
        for texto in ("**1. Sube documentos**", "**2. Tres agentes**", "**3. Estudia y evalúa**",
                      "**Fiel a las fuentes**", "**Calidad revisada**", "**Listo para integrar**"):
            with self.subTest(texto=texto):
                self.assertIn(texto, markdown)

    def test_cuentas_de_demostracion_solo_en_modo_mock(self):
        markdown = " ".join(textos(abrir_pagina(LANDING, usuario=None).markdown))
        self.assertIn("`laura` / `demo-estudiante`", markdown)
        at = abrir_pagina(LANDING, usuario=None, cliente=ClienteReal())
        self.assertNotIn("`laura`", " ".join(textos(at.markdown)))
        self.assertIn("Pide tu usuario a quien administra la plataforma.", textos(at.caption))


if __name__ == "__main__":
    unittest.main()
