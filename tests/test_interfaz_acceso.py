"""Pruebas de la sesión y de las pantallas de acceso: iniciar sesión y cambiar la contraseña temporal."""

import unittest

from streamlit.proto.TextInput_pb2 import TextInput

from apoyo_interfaz import abrir_pagina, textos

from cliente_api import ClienteMock, ErrorCliente
from paginas.acceso import LARGO_MINIMO_CONTRASENA, validar_contrasena_nueva
from paginas.landing import SIN_CUENTAS_DEMO

INICIO = "paginas.acceso:mostrar_inicio"
CAMBIO = "paginas.acceso:mostrar_cambio"


class ClienteReal(ClienteMock):
    es_mock = False


def _html(at):
    return " ".join(elemento.proto.body for elemento in at.get("html"))


def _en_orden(nodo):
    """Tipos de los elementos en el orden en que se dibujan (recorre contenedores y columnas)."""
    hijos = getattr(nodo, "children", None)
    if hijos is None:
        return [nodo.type]
    return [tipo for clave in sorted(hijos) for tipo in _en_orden(hijos[clave])]


class ClienteQueCuenta(ClienteMock):
    def __init__(self):
        super().__init__()
        self.intentos = 0

    def iniciar_sesion(self, usuario, contrasena):
        self.intentos += 1
        return super().iniciar_sesion(usuario, contrasena)


class ClienteBloqueado(ClienteMock):
    def iniciar_sesion(self, usuario, contrasena):
        raise ErrorCliente("demasiados_intentos", "429", mensaje="Demasiados intentos. Intenta de nuevo en 5 minutos.")


class ClienteQueNoDejaVolver(ClienteMock):
    """Deja entrar una vez (al abrir la página); al volver a entrar tras cambiar la contraseña, está bloqueado."""

    def __init__(self):
        super().__init__()
        self.entradas = 0

    def iniciar_sesion(self, usuario, contrasena):
        self.entradas += 1
        if self.entradas > 1:
            raise ErrorCliente("demasiados_intentos", "429")
        return super().iniciar_sesion(usuario, contrasena)


def entrar(at, usuario, contrasena):
    at.text_input(key="acceso_usuario").input(usuario)
    at.text_input(key="acceso_contrasena").input(contrasena)
    return at.button(key="iniciar_sesion").click().run()


class IniciarSesion(unittest.TestCase):
    def test_muestra_el_lema_y_el_formulario(self):
        at = abrir_pagina(INICIO, usuario=None)
        html = _html(at)
        for texto in ("Aprender hoy,", "construir mañana.", "Consulta tus temas", "Inicia sesión"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        self.assertEqual(at.text_input(key="acceso_contrasena").proto.type, TextInput.PASSWORD)

    def test_tarjeta_con_panel_oscuro_y_formulario(self):
        at = abrir_pagina(INICIO, usuario=None)
        html = _html(at)
        # st.html quita los <svg>: el logo y los íconos van como <img> con el SVG en data:
        self.assertNotIn("<svg", html)
        self.assertIn('src="data:image/svg+xml;base64,', html)
        self.assertIn(".st-key-acceso_tarjeta", html)  # el CSS de la tarjeta
        self.assertEqual(at.button(key="volver_landing").proto.type, "tertiary")  # enlace, no botón con borde

    def test_cuentas_de_demostracion_solo_en_modo_mock(self):
        html = _html(abrir_pagina(INICIO, usuario=None))
        for texto in ("laura", "demo-estudiante", "mateo", "temporal-123", "admin", "demo-admin"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        html = _html(abrir_pagina(INICIO, usuario=None, cliente=ClienteReal()))
        self.assertNotIn("demo-estudiante", html)
        self.assertIn(SIN_CUENTAS_DEMO, html)

    def test_los_avisos_van_arriba_de_los_campos(self):
        at = entrar(abrir_pagina(INICIO, usuario=None), "   ", "")
        orden = _en_orden(at.main)
        self.assertLess(orden.index("warning"), orden.index("text_input"))

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

    def test_demasiados_intentos_muestra_su_mensaje(self):
        at = entrar(abrir_pagina(INICIO, usuario=None, cliente=ClienteBloqueado()), "laura", "otra")
        self.assertIn("Demasiados intentos. Intenta de nuevo en 5 minutos.", textos(at.error))

    def test_muestra_el_aviso_de_sesion_vencida(self):
        at = abrir_pagina(INICIO, usuario=None, estado={"aviso_acceso": "Tu sesión terminó. Inicia sesión de nuevo."})
        self.assertIn("Tu sesión terminó. Inicia sesión de nuevo.", textos(at.info))


class CambiarContrasena(unittest.TestCase):
    def cambiar(self, actual, nueva, confirmar, cliente=None):
        at = abrir_pagina(CAMBIO, usuario="mateo", cliente=cliente)
        at.text_input(key="cambio_actual").input(actual)
        at.text_input(key="cambio_nueva").input(nueva)
        at.text_input(key="cambio_confirmar").input(confirmar)
        return at.button(key="guardar_contrasena").click().run()

    def test_reglas_de_la_contrasena_nueva(self):
        self.assertEqual(validar_contrasena_nueva("", "nueva-clave-12", "nueva-clave-12"), "Escribe tu contraseña actual.")
        self.assertEqual(LARGO_MINIMO_CONTRASENA, 12)  # como el backend
        self.assertEqual(validar_contrasena_nueva("a", "corta", "corta"),
                         "La nueva contraseña debe tener al menos 12 caracteres.")
        self.assertEqual(validar_contrasena_nueva("a", "x" * 11, "x" * 11),
                         "La nueva contraseña debe tener al menos 12 caracteres.")
        self.assertEqual(validar_contrasena_nueva("a", "nueva-clave-12", "nueva-clave-123"), "Las contraseñas no coinciden.")
        self.assertEqual(validar_contrasena_nueva("nueva-clave-12", "nueva-clave-12", "nueva-clave-12"),
                         "La nueva contraseña debe ser distinta de la actual.")
        self.assertIsNone(validar_contrasena_nueva("temporal-123", "nueva-clave-12", "nueva-clave-12"))

    def test_cambio_correcto_quita_la_marca_de_temporal(self):
        at = self.cambiar("temporal-123", "nueva-clave-12", "nueva-clave-12")
        self.assertFalse(at.session_state["sesion"].usuario.debe_cambiar_contrasena)

    def test_tras_cambiar_la_contrasena_sigue_adentro(self):
        # El backend cierra las sesiones al cambiar la contraseña: la interfaz vuelve a entrar sola
        at = self.cambiar("temporal-123", "nueva-clave-12", "nueva-clave-12")
        self.assertEqual([t.id_tema for t in at.session_state["cliente"].listar_temas()], ["t-redes"])

    def test_si_no_puede_volver_a_entrar_va_al_inicio_de_sesion(self):
        at = self.cambiar("temporal-123", "nueva-clave-12", "nueva-clave-12", cliente=ClienteQueNoDejaVolver())
        self.assertNotIn("sesion", at.session_state)
        self.assertEqual(len(at.exception), 0)
        self.assertIn("Tu contraseña cambió. Inicia sesión con la nueva.", textos(at.info))

    def test_actual_incorrecta_muestra_el_mensaje(self):
        at = self.cambiar("equivocada", "nueva-clave-12", "nueva-clave-12")
        self.assertIn("La contraseña actual no es correcta.", textos(at.error))
        self.assertTrue(at.session_state["sesion"].usuario.debe_cambiar_contrasena)

    def test_no_coinciden_no_llama_a_la_api(self):
        at = self.cambiar("temporal-123", "nueva-clave-12", "otra-clave-123")
        self.assertIn("Las contraseñas no coinciden.", textos(at.warning))
        self.assertTrue(at.session_state["sesion"].usuario.debe_cambiar_contrasena)

    def test_misma_tarjeta_con_el_saludo(self):
        at = abrir_pagina(CAMBIO, usuario="mateo")
        html = _html(at)
        self.assertIn(".st-key-acceso_tarjeta", html)
        self.assertIn("Hola, Mateo", html)
        self.assertIn("Cambia tu contraseña", html)
        self.assertEqual(at.button(key="salir_cambio").proto.type, "tertiary")

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
        at.text_input(key="cambio_nueva").input("nueva-clave-12")
        at.text_input(key="cambio_confirmar").input("nueva-clave-12")
        at = at.button(key="guardar_contrasena").click().run()
        self.assertNotIn("sesion", at.session_state)
        self.assertIn("Tu sesión terminó. Inicia sesión de nuevo.", textos(at.info))  # ya en Iniciar sesión


if __name__ == "__main__":
    unittest.main()
