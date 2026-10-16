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


def marcar_contrasena_cambiada():
    sesion = st.session_state["sesion"]
    usuario = sesion.usuario.model_copy(update={"debe_cambiar_contrasena": False})
    st.session_state["sesion"] = sesion.model_copy(update={"usuario": usuario})


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
