"""Vista genérica (capa 1): dibuja cualquier paquete, sea cual sea su formato."""

import streamlit as st

AVISO_REVISION = ("Este material no superó la revisión automática de calidad. "
                  "Un administrador lo va a revisar.")


def mostrar_encabezado(paquete):
    contenido = paquete.contenido_adaptado
    metadatos = paquete.metadatos
    calidad = paquete.evaluacion_calidad
    st.header(contenido.titulo)
    if calidad.requiere_revision_admin:
        st.warning(AVISO_REVISION)
    if contenido.introduccion_contextualizada:
        st.write(contenido.introduccion_contextualizada)
    tiempo, anclaje, intentos = st.columns(3)
    tiempo.metric("Tiempo estimado", f"{metadatos.tiempo_estimado_estudio_minutos} min")
    anclaje.metric("Anclaje en fuentes", f"{calidad.anclaje_fuente_score:.0%}")
    intentos.metric("Intentos de revisión", calidad.intentos_revision)
    if metadatos.conceptos_clave:
        st.markdown("**Conceptos clave:** " + " · ".join(metadatos.conceptos_clave))
    if metadatos.prerrequisitos:
        st.markdown("**Prerrequisitos:** " + " · ".join(metadatos.prerrequisitos))
    st.caption(f"{metadatos.perfil_aplicado} · {metadatos.formato_generado} · {metadatos.nicho_sector}")


def mostrar_items(paquete):
    items = paquete.contenido_adaptado.items
    if not items:
        st.info("Este paquete no trae contenido.")
        return
    for numero, item in enumerate(items, start=1):
        st.markdown(f"**{numero}.**")
        for clave, valor in item.items():
            if valor in (None, "", []):
                continue
            if isinstance(valor, list):
                valor = " · ".join(str(v) for v in valor)
            st.markdown(f"*{clave.replace('_', ' ').capitalize()}:* {valor}")


def mostrar_pie(paquete):
    if paquete.evaluacion_calidad.observaciones:
        with st.expander("Observaciones del revisor"):
            st.write(paquete.evaluacion_calidad.observaciones)
    if paquete.fuentes:
        with st.expander(f"Fuentes ({len(paquete.fuentes)})"):
            for fuente in paquete.fuentes:
                st.markdown(f"- **{fuente.documento}**, fragmento {fuente.fragmento}: {fuente.extracto}")
    st.download_button(
        "Descargar JSON",
        data=paquete.model_dump_json(indent=2),
        file_name=f"{paquete.id_paquete}.json",
        mime="application/json",
        key=f"descargar_{paquete.id_paquete}",
    )
