"""Mis temas (estudiante): resumen y una tarjeta por tema asignado (spec §6.2)."""

import streamlit as st

import sesion
from cliente_api import ErrorCliente
from paginas import ir_a, mostrar_error, mostrar_modo_demo

COLOR_ESTADO = {"Pendiente": "orange", "Aprobado": "green", "Sin intentos": "red", "Sin evaluación": "gray"}
FILTROS = ("Todos", "Pendientes", "Aprobados")
ICONOS = (":material/description:", ":material/cloud:", ":material/dataset:", ":material/hub:")
VACIO = "Todavía no tienes temas asignados. Cuando la institución te asigne uno, aparecerá aquí."


def estado_del_tema(tema):
    """Pieza 1: todavía no hay evaluaciones. En la pieza 2 sale de EstadoEvaluacion (spec §5.6)."""
    return "Sin evaluación"


def filtrar(temas_y_estados, filtro):
    """Pendientes = todo tema que no esté Aprobado (spec §6.2)."""
    if filtro == "Aprobados":
        return [(t, e) for t, e in temas_y_estados if e == "Aprobado"]
    if filtro == "Pendientes":
        return [(t, e) for t, e in temas_y_estados if e != "Aprobado"]
    return list(temas_y_estados)


def _documentos(cantidad):
    return "1 documento" if cantidad == 1 else f"{cantidad} documentos"


def _tarjeta(numero, tema, estado):
    # Sin barra de progreso: la app no mide cuánto ha estudiado cada persona (spec v2.1)
    with st.container(border=True):
        icono, info, accion = st.columns([1, 7, 3], vertical_alignment="center")
        icono.markdown(f"### {ICONOS[numero % len(ICONOS)]}")
        with info:
            st.markdown(f"**{tema.nombre}**")
            st.badge(estado, color=COLOR_ESTADO[estado])
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

    con_estado = [(tema, estado_del_tema(tema)) for tema in temas]
    aprobados = sum(1 for _, estado in con_estado if estado == "Aprobado")
    asignados_col, pendientes_col, aprobados_col = st.columns(3)
    asignados_col.metric("Asignados", len(temas), border=True)
    pendientes_col.metric("Pendientes", len(temas) - aprobados, border=True)
    aprobados_col.metric("Aprobados", aprobados, border=True)

    filtro = st.pills("Mostrar", FILTROS, default="Todos", key="filtro_temas", required=True,
                      label_visibility="collapsed")
    visibles = filtrar(con_estado, filtro)
    if not visibles:
        st.info("No hay temas en este filtro.")
        return
    for numero, (tema, estado) in enumerate(visibles):
        _tarjeta(numero, tema, estado)
