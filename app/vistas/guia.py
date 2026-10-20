"""Vista interactiva de la guía paso a paso (capa 2): pasos numerados con avance."""

import streamlit as st


def mostrar(paquete, items):
    clave = f"guia_{paquete.id_paquete}"
    pasos = sorted(items, key=lambda p: p.paso)
    hechos = sum(1 for i in range(len(pasos)) if st.session_state.get(f"{clave}_{i}"))
    st.progress(hechos / len(pasos))
    st.caption(f"{hechos} de {len(pasos)} pasos completados")
    for i, paso in enumerate(pasos):
        with st.container(border=True):
            st.markdown(f"**Paso {paso.paso}. {paso.titulo}**")
            st.write(paso.explicacion)
            if paso.ejemplo:
                st.info(f"Ejemplo: {paso.ejemplo}")
            st.checkbox("Hecho", key=f"{clave}_{i}")
