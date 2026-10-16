"""Material en revisión (admin): lo que no superó el control de calidad, con Exportar JSON (spec §6.5)."""

import streamlit as st

import sesion
from cliente_api import ErrorCliente
from paginas import mostrar_error, mostrar_modo_demo
from vistas import mostrar_paquete


def _paquete_abierto(cliente):
    elegido = st.session_state.get("paquete_admin")
    if not elegido:
        return
    try:
        paquete = cliente.obtener_paquete(elegido)
    except ErrorCliente as error:
        mostrar_error(error)
        return
    mostrar_paquete(paquete)
    # El JSON es para integrarlo con otros sistemas de la institución (por ejemplo, su LMS)
    st.download_button(
        "Exportar JSON",
        data=paquete.model_dump_json(indent=2),
        file_name=f"{paquete.id_paquete}.json",
        mime="application/json",
        key=f"exportar_{paquete.id_paquete}",
        icon=":material/download:",
    )


def mostrar():
    sesion.exigir_rol("admin")
    cliente = sesion.cliente_de_sesion()
    st.title("Material en revisión")
    st.caption("Material que no superó la revisión automática de calidad. Quien estudia no lo ve.")
    mostrar_modo_demo(cliente)
    try:
        resumenes = cliente.listar_paquetes_revision()
    except ErrorCliente as error:
        mostrar_error(error)
        return
    if not resumenes:
        st.info("No hay material pendiente de revisión.")
        return
    for resumen in resumenes:
        with st.container(border=True):
            info, accion = st.columns([8, 2], vertical_alignment="center")
            info.markdown(f"**{resumen.tema}** · {resumen.formato} · anclaje {resumen.anclaje_fuente_score:.0%}"
                          f" · {resumen.creado_en:%Y-%m-%d %H:%M}")
            if accion.button("Abrir", key=f"abrir_{resumen.id_paquete}"):
                st.session_state["paquete_admin"] = resumen.id_paquete
    _paquete_abierto(cliente)
