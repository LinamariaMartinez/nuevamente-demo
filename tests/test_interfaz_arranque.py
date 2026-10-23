"""Pruebas de app/arranque.py (arranque en Streamlit Cloud). No prenden el backend ni usan OCI."""

import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
for ruta in (RAIZ, RAIZ / "src", RAIZ / "app"):
    sys.path.insert(0, str(ruta))

import arranque


class LlaveOciTest(unittest.TestCase):
    def test_escribe_la_llave_y_apunta_oci_key_file(self):
        with patch.dict(os.environ, {"OCI_KEY_CONTENT": "llave-de-prueba\nlinea-2"}, clear=False):
            os.environ.pop("OCI_KEY_FILE", None)
            arranque._llave_oci_a_archivo()
            ruta = Path(os.environ["OCI_KEY_FILE"])
            self.assertTrue(ruta.read_text().startswith("llave-de-prueba"))
            self.assertEqual(ruta.stat().st_mode & 0o777, 0o600)

    def test_no_pisa_un_oci_key_file_existente(self):
        with patch.dict(os.environ, {"OCI_KEY_CONTENT": "x", "OCI_KEY_FILE": "/ruta/propia.pem"}):
            arranque._llave_oci_a_archivo()
            self.assertEqual(os.environ["OCI_KEY_FILE"], "/ruta/propia.pem")


class AdminDemoTest(unittest.TestCase):
    def setUp(self):
        from api import database

        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_anterior = database.DB_PATH
        database.DB_PATH = Path(self.carpeta.name) / "demo.sqlite3"
        self.db = database.DB_PATH

    def tearDown(self):
        from api import database

        database.DB_PATH = self.ruta_anterior
        self.carpeta.cleanup()

    def admins(self):
        with sqlite3.connect(self.db) as conexion:
            return conexion.execute("SELECT usuario FROM usuarios WHERE rol = 'admin'").fetchall()

    def test_crea_el_admin_una_sola_vez(self):
        with patch.dict(os.environ, {"ADMIN_DEMO_USUARIO": "jurado", "ADMIN_DEMO_CONTRASENA": "una-clave-larga-123"}):
            arranque._admin_demo()
            arranque._admin_demo()
        self.assertEqual(self.admins(), [("jurado",)])

    def test_si_cambia_la_contrasena_en_los_secretos_se_actualiza(self):
        from api.auth import verify_password

        with patch.dict(os.environ, {"ADMIN_DEMO_USUARIO": "jurado", "ADMIN_DEMO_CONTRASENA": "la-primera-clave-123"}):
            arranque._admin_demo()
        with patch.dict(os.environ, {"ADMIN_DEMO_USUARIO": "jurado", "ADMIN_DEMO_CONTRASENA": "la-segunda-clave-456"}):
            arranque._admin_demo()
        with sqlite3.connect(self.db) as conexion:
            (hash_guardado,) = conexion.execute("SELECT contrasena_hash FROM usuarios WHERE usuario = 'jurado'").fetchone()
        self.assertTrue(verify_password("la-segunda-clave-456", hash_guardado))

    def test_sin_variables_no_hace_nada(self):
        with patch.dict(os.environ, {"ADMIN_DEMO_USUARIO": "", "ADMIN_DEMO_CONTRASENA": ""}):
            arranque._admin_demo()
        self.assertFalse(self.db.exists())


class IniciarBackendTest(unittest.TestCase):
    def test_sin_arrancar_backend_no_prende_nada(self):
        with patch.dict(os.environ, {"ARRANCAR_BACKEND": ""}), patch.object(arranque, "_puerto_libre") as puerto:
            self.assertFalse(arranque.iniciar_backend.__wrapped__())
            puerto.assert_not_called()


if __name__ == "__main__":
    unittest.main()
