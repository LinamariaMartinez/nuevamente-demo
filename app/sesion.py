"""Sesión de quien usa la app: cliente, iniciar, cerrar, usuario actual y permisos por rol.

Todo vive en st.session_state, que se pierde al recargar la página (F5 pide iniciar sesión de nuevo).
"""

import streamlit as st

from cliente_api import ErrorCliente, obtener_cliente

ROL_LEGIBLE = {"estudiante": "Estudiante", "admin": "Administración"}


def cliente_de_sesion():
    """Un solo cliente por sesión del navegador: en modo http guarda el token."""
    if "cliente" not in st.session_state:
        st.session_state["cliente"] = obtener_cliente()
    return st.session_state["cliente"]


def usuario_actual():
    sesion = st.session_state.get("sesion")
    return sesion.usuario if sesion is not None else None


def iniciar(usuario, contrasena):
    """Inicia sesión y la guarda. Lanza ErrorCliente si los datos no sirven."""
    sesion = cliente_de_sesion().iniciar_sesion(usuario.strip(), contrasena)
    st.session_state["sesion"] = sesion
    return sesion.usuario


def cambiar_contrasena(actual, nueva):
    """Cambia la contraseña y vuelve a entrar con la nueva. Lanza ErrorCliente si el cambio falla.

    Backend cierra todas las sesiones de la persona al cambiarla. Si volver a entrar falla
    (por ejemplo, demasiados intentos), la manda al inicio de sesión con un aviso.
    """
    usuario = usuario_actual().usuario
    cliente_de_sesion().cambiar_contrasena(actual, nueva)
    try:
        iniciar(usuario, nueva)
    except ErrorCliente:
        cerrar(aviso="Tu contraseña cambió. Inicia sesión con la nueva.")


def cerrar(aviso=None):
    """Cierra la sesión en la API (si falla, igual se cierra aquí) y borra todo: token, cliente y material."""
    cliente = st.session_state.get("cliente")
    if cliente is not None:
        try:
            cliente.cerrar_sesion()
        except ErrorCliente:
            pass
    for clave in list(st.session_state.keys()):
        del st.session_state[clave]
    if aviso:
        st.session_state["aviso_acceso"] = aviso


def exigir_rol(rol):
    """Ocultar el menú es comodidad, no protección: cada página vuelve a comprobar el rol al cargar."""
    usuario = usuario_actual()
    if usuario is None or usuario.rol != rol:
        st.error("No tienes permiso para ver esta página.")
        st.stop()
    return usuario
