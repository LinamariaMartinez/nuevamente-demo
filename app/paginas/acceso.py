"""Acceso: iniciar sesión y cambiar la contraseña temporal (spec §6.1)."""

import streamlit as st

import marca
import sesion
from cliente_api import ErrorCliente
from paginas import mostrar_error

LARGO_MINIMO_CONTRASENA = 8


def validar_contrasena_nueva(actual, nueva, confirmar):
    """Devuelve el problema para mostrar, o None si se puede enviar. Backend también valida."""
    if not actual:
        return "Escribe tu contraseña actual."
    if len(nueva) < LARGO_MINIMO_CONTRASENA:
        return f"La nueva contraseña debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres."
    if nueva != confirmar:
        return "Las contraseñas no coinciden."
    if nueva == actual:
        return "La nueva contraseña debe ser distinta de la actual."
    return None


def mostrar_inicio():
    st.image(str(marca.LOGO), width=280)
    st.markdown("**Aprender hoy, construir mañana.**")
    st.caption("Consulta tus temas → estudia con material a tu medida → presenta la evaluación.")
    aviso = st.session_state.pop("aviso_acceso", None)
    if aviso:
        st.info(aviso)
    with st.form("form_acceso"):  # en un formulario, Enter también envía
        usuario = st.text_input("Usuario", key="acceso_usuario")
        contrasena = st.text_input("Contraseña", type="password", key="acceso_contrasena")
        enviado = st.form_submit_button("Iniciar sesión", type="primary", key="iniciar_sesion")
    if not enviado:
        return
    if not usuario.strip() or not contrasena:
        st.warning("Escribe tu usuario y tu contraseña.")
        return
    try:
        sesion.iniciar(usuario, contrasena)
    except ErrorCliente as error:
        st.error(error.mensaje)  # sin detalle: todavía no sabemos quién es
        return
    st.rerun()


def mostrar_cambio():
    usuario = sesion.usuario_actual()
    st.title("Cambia tu contraseña")
    st.write(f"Hola, {usuario.nombre}. Tu contraseña es temporal: crea una nueva para continuar.")
    with st.form("form_cambio"):
        actual = st.text_input("Contraseña actual", type="password", key="cambio_actual")
        nueva = st.text_input("Nueva contraseña", type="password", key="cambio_nueva",
                              help=f"Mínimo {LARGO_MINIMO_CONTRASENA} caracteres.")
        confirmar = st.text_input("Confirma la nueva contraseña", type="password", key="cambio_confirmar")
        enviado = st.form_submit_button("Guardar contraseña", type="primary", key="guardar_contrasena")
    if st.button("Salir", key="salir_cambio", icon=":material/logout:"):
        sesion.cerrar()
        st.rerun()
    if not enviado:
        return
    problema = validar_contrasena_nueva(actual, nueva, confirmar)
    if problema:
        st.warning(problema)
        return
    try:
        sesion.cliente_de_sesion().cambiar_contrasena(actual, nueva)
    except ErrorCliente as error:
        mostrar_error(error)
        return
    sesion.marcar_contrasena_cambiada()
    st.rerun()
