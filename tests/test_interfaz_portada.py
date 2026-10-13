"""Pruebas de la portada: explica qué es NuevaMente y ofrece los dos accesos."""

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]

from streamlit.testing.v1 import AppTest

APP_PORTADA = str(RAIZ / "tests" / "apps_interfaz" / "portada_app.py")
APP_INICIO = str(RAIZ / "app" / "inicio.py")


class Portada(unittest.TestCase):
    def setUp(self):
        self.at = AppTest.from_file(APP_PORTADA, default_timeout=10).run()

    def test_explica_que_es_nuevamente(self):
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(self.at.title[0].value, "NuevaMente")
        self.assertEqual(self.at.subheader[0].value, "Cómo funciona")

    def test_ofrece_los_dos_accesos(self):
        self.assertEqual(self.at.button(key="ir_estudiante").label, "Entrar como estudiante")
        self.assertEqual(self.at.button(key="ir_admin").label, "Entrar como administrador")


@patch.dict(os.environ, {"MODO_API": "mock"})
class Inicio(unittest.TestCase):
    def test_la_app_abre_en_la_portada(self):
        at = AppTest.from_file(APP_INICIO, default_timeout=15).run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.title[0].value, "NuevaMente")

    def test_los_botones_llevan_a_cada_pagina(self):
        for clave, titulo in (("ir_estudiante", "Genera tu material de estudio"), ("ir_admin", "Panel del administrador")):
            with self.subTest(boton=clave):
                at = AppTest.from_file(APP_INICIO, default_timeout=15).run()
                at = at.button(key=clave).click().run()
                self.assertEqual(at.title[0].value, titulo)


if __name__ == "__main__":
    unittest.main()
