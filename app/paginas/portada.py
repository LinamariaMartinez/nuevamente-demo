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
    st.markdown("**De documentación técnica a material de estudio a la medida de cada persona.**")
    st.write(
        "Tu institución convierte sus manuales, documentación y artículos técnicos en material educativo "
        "adaptado al nivel de cada persona y al sector de la institución. Todo lo que se genera está anclado "
        "en los documentos originales."
    )

    st.subheader("Cómo funciona")
    st.markdown(
        "1. **El administrador sube los documentos** y define el sector de la institución.\n"
        "2. **Los agentes preparan el material**: uno busca la información, otro la adapta y otro revisa "
        "que sea fiel a la fuente.\n"
        "3. **El estudiante elige tema, nivel y formato**, y recibe su material con su puntaje de calidad "
        "y sus fuentes."
    )
    st.caption("Formatos: Guía paso a paso · Flashcards · Quiz · Resumen ejecutivo · Guion de clase")

    estudiante, admin = st.columns(2)
    with estudiante:
        _acceso("Soy estudiante", "Genera tu material de estudio.",
                "Entrar como estudiante", "ir_estudiante", destino_estudiante)
    with admin:
        _acceso("Soy administrador", "Sube documentos, define el sector y revisa el material generado.",
                "Entrar como administrador", "ir_admin", destino_admin)
