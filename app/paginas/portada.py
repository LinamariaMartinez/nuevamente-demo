"""Portada: explica qué es NuevaMente y lleva a la página del estudiante o del admin."""

import streamlit as st


def _acceso(titulo, descripcion, boton, clave, destino):
    with st.container(border=True):
        st.markdown(f"**{titulo}**")
        st.write(descripcion)
        if st.button(boton, key=clave, type="primary") and destino is not None:
            st.switch_page(destino)


def mostrar(destino_estudiante, destino_admin):
    """`destino_*` son las páginas (st.Page) a las que llevan los botones; inicio.py las pasa."""
    st.title("NuevaMente")
    st.markdown("**Aprender hoy, construir mañana.**")
    st.write(
        "Tu institución convierte sus manuales, documentación y artículos técnicos en material de estudio "
        "adaptado a tu nivel y al sector en el que trabajas. Cada material indica los documentos en los que "
        "se basa, para que puedas consultarlos."
    )

    st.subheader("Cómo funciona")
    st.markdown(
        "1. **La institución sube sus documentos** y define su sector.\n"
        "2. **Se prepara el material**: un agente busca la información, otro la adapta a tu nivel y otro "
        "revisa que sea fiel a los documentos.\n"
        "3. **Tú eliges tema, nivel y formato**, y estudias con un material que muestra su calidad "
        "y sus fuentes."
    )
    st.caption("Formatos: Guía paso a paso · Flashcards · Quiz · Resumen ejecutivo · Guion de clase")

    estudiante, admin = st.columns(2)
    with estudiante:
        _acceso("Soy estudiante", "Prepara tu material de estudio.",
                "Entrar como estudiante", "ir_estudiante", destino_estudiante)
    with admin:
        _acceso("Soy administrador", "Sube documentos, define el sector y revisa el material que no pasó el control de calidad.",
                "Entrar como administrador", "ir_admin", destino_admin)
