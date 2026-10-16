"""Ayudas comunes de las páginas: errores, aviso de modo demostración y cambio de página."""

import streamlit as st

import sesion

# nombre → st.Page. Lo llena inicio.py en cada ejecución; en las pruebas por página queda vacío
DESTINOS = {}


def ir_a(nombre):
    destino = DESTINOS.get(nombre)
    if destino is not None:
        st.switch_page(destino)


def mostrar_error(error):
    """Muestra un ErrorCliente ya traducido.

    Sesión vencida → vuelve a Iniciar sesión con el aviso. El detalle técnico solo lo ve el admin.
    """
    if error.tipo == "sesion_vencida":
        sesion.cerrar(aviso=error.mensaje)
        st.rerun()
    st.error(error.mensaje)
    usuario = sesion.usuario_actual()
    if error.detalle and usuario is not None and usuario.rol == "admin":
        with st.expander("Ver detalle"):
            st.code(error.detalle)


def mostrar_modo_demo(cliente):
    if cliente.es_mock:
        st.info("Modo demostración: datos de ejemplo")
