"""Página del estudiante: pide su material de estudio y lo ve."""

import streamlit as st

from cliente_api import ErrorCliente
from contrato import FORMATOS, LARGO_MAXIMO_TEMA, NICHOS, PERFILES, SolicitudPaquete
from paginas import cliente_de_sesion
from vistas import mostrar_paquete

MENSAJES_POR_CODIGO = {
    "sin_contexto": "No encontré ese tema en los documentos cargados. Prueba con otras palabras.",
}


def _generar(cliente):
    solicitud = SolicitudPaquete(
        tema=st.session_state["tema"],
        perfil=st.session_state["perfil"],
        formato=st.session_state["formato"],
        nicho=st.session_state["nicho"],
    )
    st.session_state.pop("error_generacion", None)
    st.session_state.pop("paquete", None)
    try:
        with st.spinner("Generando tu material… puede tardar un poco."):
            st.session_state["paquete"] = cliente.generar_paquete(solicitud)
    except ErrorCliente as error:
        st.session_state["error_generacion"] = error


def _boton_reintentar():
    if st.button("Reintentar", key="reintentar"):
        st.session_state["reintentar_pedido"] = True
        st.rerun()


def mostrar():
    cliente = cliente_de_sesion()
    st.title("Genera tu material de estudio")
    if cliente.es_mock:
        st.info("Modo demostración: datos de ejemplo")
    if not cliente.salud():
        st.warning("El servicio no está disponible en este momento.")

    st.text_input("¿Qué quieres aprender?", key="tema", max_chars=LARGO_MAXIMO_TEMA,
                  placeholder="Ej.: redes VCN en OCI")
    st.selectbox("Tu perfil", PERFILES, key="perfil")
    st.selectbox("Formato", FORMATOS, key="formato")
    st.selectbox("Contexto de aplicación", NICHOS, key="nicho")

    tema_vacio = not st.session_state.get("tema", "").strip()
    reintentar = st.session_state.pop("reintentar_pedido", False)
    generar = st.button("Generar", key="generar", type="primary", disabled=tema_vacio)
    if (generar or reintentar) and not tema_vacio:
        _generar(cliente)

    error = st.session_state.get("error_generacion")
    if error is not None:
        st.error(error.mensaje)
        if error.detalle:
            with st.expander("Ver detalle"):
                st.code(error.detalle)
        _boton_reintentar()
        return

    paquete = st.session_state.get("paquete")
    if paquete is None:
        return
    if paquete.status == "error":
        st.error(MENSAJES_POR_CODIGO.get(paquete.codigo_error,
                                         paquete.mensaje_error or "No se pudo generar el material."))
        _boton_reintentar()
        return
    mostrar_paquete(paquete)
