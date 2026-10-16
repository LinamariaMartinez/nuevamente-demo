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


def contraer_menu():
    """La página pide el menú contraído porque muestra contenido en la columna derecha (spec §6.6).

    No lo aplica aquí: inicio.py lo hace una sola vez al terminar la página.
    """
    st.session_state["menu_pedido"] = "collapsed"


def aplicar_estado_menu():
    """Lo llama inicio.py al terminar la página. Sin pedido, el menú vuelve a "auto".

    Solo llama a set_page_config si el estado cambió: así el menú no se abre y se cierra en cada recarga.
    Si la persona abrió o cerró el menú a mano, su navegador guarda esa preferencia y Streamlit la respeta.
    """
    pedido = st.session_state.pop("menu_pedido", "auto")
    if st.session_state.get("menu_actual") != pedido:
        st.set_page_config(initial_sidebar_state=pedido)
        st.session_state["menu_actual"] = pedido
