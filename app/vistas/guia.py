"""Vista interactiva de la guía paso a paso (capa 2): pasos numerados con avance."""

import streamlit as st

from vistas.generica import texto_seguro


def mostrar(paquete, items):
    clave = f"guia_{paquete.id}"
    hechos = sum(1 for i in range(len(items)) if st.session_state.get(f"{clave}_{i}"))
    st.progress(hechos / len(items))
    st.caption(f"{hechos} de {len(items)} pasos completados")
    # El número del paso es su orden en la lista
    for i, paso in enumerate(items):
        with st.container(border=True):
            st.markdown(f"**Paso {i + 1}. {texto_seguro(paso.titulo)}**")
            st.markdown(texto_seguro(paso.instrucciones))
            st.checkbox("Hecho", key=f"{clave}_{i}")
