"""Páginas de la app. cliente_de_sesion() guarda un solo cliente por sesión del navegador."""

import streamlit as st

from cliente_api import obtener_cliente


def cliente_de_sesion():
    if "cliente" not in st.session_state:
        st.session_state["cliente"] = obtener_cliente()
    return st.session_state["cliente"]
