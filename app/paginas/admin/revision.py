"""Material en revisión (admin): lo que no superó el control de calidad. Aprobar, rechazar o exportar (spec §6.5)."""

import streamlit as st

import sesion
from cliente_api import ErrorCliente
from paginas import contraer_menu, mostrar_error, mostrar_modo_demo
from vistas import mostrar_paquete

RESERVADO = "Abre un material de la lista para verlo aquí."
APROBADO = "Material aprobado: ya lo pueden ver."
RECHAZADO = "Material rechazado: se eliminó y se puede generar de nuevo."


def _terminar(aviso):
    st.session_state.pop("paquete_admin", None)
    st.session_state.pop("rechazando_paquete", None)
    st.session_state["aviso_revision"] = aviso
    st.rerun()


def _confirmar_rechazo(cliente, paquete):
    # Acción sensible: se confirma con un segundo botón, igual que Retirar en Temas
    st.warning("¿Rechazar este material? Se eliminará y se podrá generar de nuevo.")
    si, no = st.columns(2)
    if si.button("Sí, rechazar", key=f"confirmar_rechazar_{paquete.id}", type="primary"):
        try:
            cliente.rechazar_paquete(paquete.id)
        except ErrorCliente as error:
            mostrar_error(error)
            return
        _terminar(RECHAZADO)
    if no.button("Cancelar", key=f"cancelar_rechazar_{paquete.id}"):
        st.session_state.pop("rechazando_paquete", None)
        st.rerun()


def _acciones(cliente, paquete):
    if st.session_state.get("rechazando_paquete") == paquete.id:
        _confirmar_rechazo(cliente, paquete)
        return
    aprobar, rechazar, exportar = st.columns(3)
    if aprobar.button("Aprobar", key=f"aprobar_{paquete.id}", type="primary", icon=":material/check:"):
        try:
            cliente.aprobar_paquete(paquete.id)
        except ErrorCliente as error:
            mostrar_error(error)
            return
        _terminar(APROBADO)
    if rechazar.button("Rechazar", key=f"rechazar_{paquete.id}", icon=":material/close:"):
        st.session_state["rechazando_paquete"] = paquete.id
        st.rerun()
    # El JSON es para integrarlo con otros sistemas de la institución (por ejemplo, su LMS)
    exportar.download_button(
        "Exportar JSON",
        data=paquete.model_dump_json(indent=2),
        file_name=f"{paquete.id}.json",
        mime="application/json",
        key=f"exportar_{paquete.id}",
        icon=":material/download:",
    )


def _paquete_abierto(cliente):
    elegido = st.session_state.get("paquete_admin")
    if not elegido:
        st.info(RESERVADO, icon=":material/rate_review:")
        return
    try:
        paquete = cliente.obtener_paquete(elegido)
    except ErrorCliente as error:
        mostrar_error(error)
        return
    contraer_menu()  # hay material a la derecha: más espacio para revisarlo
    _acciones(cliente, paquete)
    mostrar_paquete(paquete)


def mostrar():
    sesion.exigir_rol("admin")
    cliente = sesion.cliente_de_sesion()
    st.title("Material en revisión")
    st.caption("Material que no superó la revisión automática de calidad. Quien estudia no lo ve.")
    mostrar_modo_demo(cliente)
    aviso = st.session_state.pop("aviso_revision", None)
    if aviso:
        st.success(aviso)
    try:
        resumenes = cliente.listar_paquetes_revision()
    except ErrorCliente as error:
        mostrar_error(error)
        return
    if not resumenes:
        st.info("No hay material pendiente de revisión.")
        return
    # Dos columnas (spec §6.6): la lista a la izquierda, el material abierto a la derecha
    izquierda, derecha = st.columns([1, 2], gap="large")
    with izquierda:
        for resumen in resumenes:
            with st.container(border=True):
                st.markdown(f"**{resumen.tema}**")
                st.caption(f"{resumen.formato} · anclaje {resumen.anclaje_fuente_score:.0%}"
                           f" · {resumen.creado_en:%Y-%m-%d %H:%M}")
                if st.button("Abrir", key=f"abrir_{resumen.id}"):
                    st.session_state["paquete_admin"] = resumen.id
    with derecha:
        _paquete_abierto(cliente)
