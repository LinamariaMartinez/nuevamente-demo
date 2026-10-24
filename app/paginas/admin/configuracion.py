"""Configuración (admin): sector de la institución (spec §6.5)."""

import streamlit as st

import sesion
from cliente_api import ErrorCliente
from contrato import NICHOS
from paginas import mostrar_error, mostrar_modo_demo


def mostrar():
    sesion.exigir_rol("admin")
    cliente = sesion.cliente_de_sesion()
    st.title("Configuración")
    mostrar_modo_demo(cliente)
    with st.container(border=True):
        st.subheader("Sector de la institución")
        try:
            actual = cliente.obtener_configuracion().sector
        except ErrorCliente as error:
            mostrar_error(error)
            return
        elegido = st.selectbox("El material se adapta a este sector", NICHOS, index=NICHOS.index(actual), key="sector")
        st.caption("El sector adapta los ejemplos y el vocabulario del material; no cambia lo que dicen los documentos.")
        if st.button("Guardar cambios", key="guardar_sector", type="primary"):
            try:
                st.success(f"Sector guardado: {cliente.guardar_configuracion(elegido).sector}")
            except ErrorCliente as error:
                mostrar_error(error)
