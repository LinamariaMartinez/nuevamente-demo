"""Pruebas de la sesión y de las pantallas de acceso: iniciar sesión y cambiar la contraseña temporal."""

import unittest

from streamlit.proto.TextInput_pb2 import TextInput

from apoyo_interfaz import abrir_pagina, textos

from cliente_api import ClienteMock, ErrorCliente
from paginas.acceso import validar_contrasena_nueva

INICIO = "paginas.acceso:mostrar_inicio"
CAMBIO = "paginas.acceso:mostrar_cambio"


class ClienteQueCuenta(ClienteMock):
    def __init__(self):
        super().__init__()
        self.intentos = 0

    def iniciar_sesion(self, usuario, contrasena):
        self.intentos += 1
        return super().iniciar_sesion(usuario, contrasena)


def entrar(at, usuario, contrasena):
    at.text_input(key="acceso_usuario").input(usuario)
    at.text_input(key="acceso_contrasena").input(contrasena)
    return at.button(key="iniciar_sesion").click().run()


class IniciarSesion(unittest.TestCase):
    def test_muestra_el_lema_y_el_formulario(self):
        at = abrir_pagina(INICIO, usuario=None)
        self.assertIn("**Aprender hoy, construir mañana.**", textos(at.markdown))
        self.assertEqual(at.text_input(key="acceso_contrasena").proto.type, TextInput.PASSWORD)

    def test_inicio_correcto_guarda_la_sesion(self):
        at = entrar(abrir_pagina(INICIO, usuario=None), "laura", "demo-estudiante")
        self.assertEqual(at.session_state["sesion"].usuario.nombre, "Laura Gómez")

    def test_usuario_con_espacios_funciona(self):
        at = entrar(abrir_pagina(INICIO, usuario=None), "  laura ", "demo-estudiante")
        self.assertEqual(at.session_state["sesion"].usuario.usuario, "laura")

    def test_datos_malos_muestran_el_mensaje_y_conservan_el_usuario(self):
        at = entrar(abrir_pagina(INICIO, usuario=None), "laura", "otra")
        self.assertIn(ErrorCliente.MENSAJES["credenciales"], textos(at.error))
        self.assertEqual(at.text_input(key="acceso_usuario").value, "laura")
        self.assertNotIn("sesion", at.session_state)

    def test_campos_vacios_no_llaman_a_la_api(self):
        cliente = ClienteQueCuenta()
        at = abrir_pagina(INICIO, usuario=None, cliente=cliente)
        at = entrar(at, "   ", "")
        self.assertIn("Escribe tu usuario y tu contraseña.", textos(at.warning))
        self.assertEqual(cliente.intentos, 0)

    def test_muestra_el_aviso_de_sesion_vencida(self):
        at = abrir_pagina(INICIO, usuario=None, estado={"aviso_acceso": "Tu sesión terminó. Inicia sesión de nuevo."})
        self.assertIn("Tu sesión terminó. Inicia sesión de nuevo.", textos(at.info))


class CambiarContrasena(unittest.TestCase):
    def cambiar(self, actual, nueva, confirmar):
        at = abrir_pagina(CAMBIO, usuario="mateo")
        at.text_input(key="cambio_actual").input(actual)
        at.text_input(key="cambio_nueva").input(nueva)
        at.text_input(key="cambio_confirmar").input(confirmar)
        return at.button(key="guardar_contrasena").click().run()

    def test_reglas_de_la_contrasena_nueva(self):
        self.assertEqual(validar_contrasena_nueva("", "nueva-1234", "nueva-1234"), "Escribe tu contraseña actual.")
        self.assertEqual(validar_contrasena_nueva("a", "corta", "corta"),
                         "La nueva contraseña debe tener al menos 8 caracteres.")
        self.assertEqual(validar_contrasena_nueva("a", "nueva-1234", "nueva-12345"), "Las contraseñas no coinciden.")
        self.assertEqual(validar_contrasena_nueva("nueva-1234", "nueva-1234", "nueva-1234"),
                         "La nueva contraseña debe ser distinta de la actual.")
        self.assertIsNone(validar_contrasena_nueva("temporal-123", "nueva-1234", "nueva-1234"))

    def test_cambio_correcto_quita_la_marca_de_temporal(self):
        at = self.cambiar("temporal-123", "nueva-1234", "nueva-1234")
        self.assertFalse(at.session_state["sesion"].usuario.debe_cambiar_contrasena)

    def test_actual_incorrecta_muestra_el_mensaje(self):
        at = self.cambiar("equivocada", "nueva-1234", "nueva-1234")
        self.assertIn("La contraseña actual no es correcta.", textos(at.error))
        self.assertTrue(at.session_state["sesion"].usuario.debe_cambiar_contrasena)

    def test_no_coinciden_no_llama_a_la_api(self):
        at = self.cambiar("temporal-123", "nueva-1234", "otra-12345")
        self.assertIn("Las contraseñas no coinciden.", textos(at.warning))
        self.assertTrue(at.session_state["sesion"].usuario.debe_cambiar_contrasena)

    def test_salir_cierra_la_sesion(self):
        at = abrir_pagina(CAMBIO, usuario="mateo").button(key="salir_cambio").click().run()
        self.assertNotIn("sesion", at.session_state)


class ErroresComunes(unittest.TestCase):
    """Regla central de mostrar_error: sesión vencida → vuelve a Iniciar sesión con el aviso."""

    def test_sesion_vencida_borra_todo_y_deja_el_aviso(self):
        class ClienteVencido(ClienteMock):
            def cambiar_contrasena(self, actual, nueva):
                raise ErrorCliente("sesion_vencida", "401")

        at = abrir_pagina(CAMBIO, usuario="mateo", cliente=ClienteVencido())
        at.text_input(key="cambio_actual").input("temporal-123")
        at.text_input(key="cambio_nueva").input("nueva-1234")
        at.text_input(key="cambio_confirmar").input("nueva-1234")
        at = at.button(key="guardar_contrasena").click().run()
        self.assertNotIn("sesion", at.session_state)
        self.assertIn("Tu sesión terminó. Inicia sesión de nuevo.", textos(at.info))  # ya en Iniciar sesión


if __name__ == "__main__":
    unittest.main()
