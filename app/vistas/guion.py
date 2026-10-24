"""Vista del Guion de clase (v2.2): escenas numeradas en una columna, como se lee un guion."""

import streamlit as st

from vistas.generica import texto_seguro


def mostrar(paquete, items):
    for numero, item in enumerate(items, start=1):
        with st.container(border=True):
            st.markdown(f"**Escena {numero} · {texto_seguro(item.titulo)}**")
            st.markdown(texto_seguro(item.narracion))
