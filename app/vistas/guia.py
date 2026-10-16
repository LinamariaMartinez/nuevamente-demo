"""Vista interactiva de la guía paso a paso (capa 2): pasos numerados con avance."""

import streamlit as st

from vistas.generica import texto_seguro


def mostrar(paquete, items):
    clave = f"guia_{paquete.id_paquete}"
    pasos = sorted(items, key=lambda p: p.paso)
    hechos = sum(1 for i in range(len(pasos)) if st.session_state.get(f"{clave}_{i}"))
    st.progress(hechos / len(pasos))
    st.caption(f"{hechos} de {len(pasos)} pasos completados")
    for i, paso in enumerate(pasos):
        with st.container(border=True):
            st.markdown(f"**Paso {paso.paso}. {texto_seguro(paso.titulo)}**")
            st.markdown(texto_seguro(paso.explicacion))
            if paso.ejemplo:
                st.info(f"Ejemplo: {texto_seguro(paso.ejemplo)}")
            st.checkbox("Hecho", key=f"{clave}_{i}")
