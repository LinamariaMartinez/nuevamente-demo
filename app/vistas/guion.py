"""Vista del Guion de clase (v2.2): escenas numeradas en una columna, como se lee un guion."""

import streamlit as st


def mostrar(paquete, items):
    for numero, item in enumerate(items, start=1):
        with st.container(border=True):
            st.markdown(f"**Escena {numero} · {item.titulo}**")
            st.write(item.contenido)
