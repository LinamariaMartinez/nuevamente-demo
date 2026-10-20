"""Mis temas (estudiante): una tarjeta por tema asignado (spec §6.2).

Sin estados ni filtros de evaluación: vuelven cuando exista la evaluación del tema (decisión del 19-oct).
"""

import streamlit as st

import sesion
from cliente_api import ErrorCliente
from paginas import ir_a, mostrar_error, mostrar_modo_demo

ICONOS = (":material/description:", ":material/cloud:", ":material/dataset:", ":material/hub:")
VACIO = "Todavía no tienes temas asignados. Cuando la institución te asigne uno, aparecerá aquí."


def _documentos(cantidad):
    return "1 documento" if cantidad == 1 else f"{cantidad} documentos"


def _asignados(cantidad):
    return "Tienes 1 tema asignado." if cantidad == 1 else f"Tienes {cantidad} temas asignados."


def _tarjeta(numero, tema):
    # Sin barra de progreso: la app no mide cuánto ha estudiado cada persona (spec v2.1)
    with st.container(border=True):
        icono, info, accion = st.columns([1, 7, 3], vertical_alignment="center")
        icono.markdown(f"### {ICONOS[numero % len(ICONOS)]}")
        with info:
            st.markdown(f"**{tema.nombre}**")
            st.caption(_documentos(len(tema.documentos)))
        if accion.button("Abrir tema", key=f"abrir_{tema.id_tema}", type="primary"):
            st.session_state["tema_elegido"] = tema.id_tema
            ir_a("tema")


def mostrar():
    sesion.exigir_rol("estudiante")
    cliente = sesion.cliente_de_sesion()
    st.title("Mis temas")
    st.caption("Consulta tus temas asignados y continúa donde lo dejaste.")
    mostrar_modo_demo(cliente)
    try:
        temas = cliente.listar_temas()
    except ErrorCliente as error:
        mostrar_error(error)
        return
    if not temas:
        st.info(VACIO)
        return

    st.caption(_asignados(len(temas)))
    for numero, tema in enumerate(temas):
        _tarjeta(numero, tema)
