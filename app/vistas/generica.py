"""Vista genérica (capa 1): dibuja cualquier paquete, sea cual sea su formato."""

import streamlit as st

AVISO_REVISION = ("Este material no superó la revisión automática de calidad "
                  "y está oculto para quienes estudian.")
# Nombres de los campos de los items tal como se ven cuando un formato cae en esta vista
ETIQUETAS = {
    "frente": "Frente", "dorso": "Dorso", "pista_didactica": "Pista didáctica",
    "pregunta": "Pregunta", "opciones": "Opciones", "respuesta_correcta": "Respuesta correcta",
    "justificacion": "Justificación", "titulo": "Título", "instrucciones": "Instrucciones",
    "subtitulo": "Subtítulo", "texto": "Texto", "narracion": "Narración",
}


def texto_seguro(texto):
    """Texto del material para markdown: "$" se muestra tal cual (sin escaparlo, "$50.000 y $80.000" sería una fórmula)."""
    return str(texto).replace("$", "\\$")


def mostrar_encabezado(paquete, compacto=False):
    """`compacto`: sin introducción ni conceptos clave, porque la vista del formato los muestra a su manera."""
    contenido = paquete.contenido_adaptado
    metadatos = paquete.metadatos
    calidad = paquete.evaluacion_calidad
    st.header(texto_seguro(contenido.titulo))
    if paquete.status == "requiere_revision":
        st.warning(AVISO_REVISION)
    if contenido.introduccion_contextualizada and not compacto:
        st.markdown(texto_seguro(contenido.introduccion_contextualizada))
    tiempo, anclaje, intentos = st.columns(3)
    tiempo.metric("Tiempo estimado", f"{metadatos.tiempo_estimado_estudio_minutos} min")
    anclaje.metric("Anclaje en fuentes", f"{calidad.anclaje_fuente_score:.0%}")
    intentos.metric("Intentos de revisión", calidad.intentos_revision)
    if metadatos.conceptos_clave and not compacto:
        st.markdown("**Conceptos clave:** " + texto_seguro(" · ".join(metadatos.conceptos_clave)))
    if metadatos.prerrequisitos:
        st.markdown("**Prerrequisitos:** " + texto_seguro(" · ".join(metadatos.prerrequisitos)))
    st.caption(f"{metadatos.perfil_aplicado} · {metadatos.formato_generado} · {metadatos.nicho_sector}")


def mostrar_items(paquete):
    items = paquete.contenido_adaptado.items
    if not items:
        st.info("Este material no trae contenido.")
        return
    for numero, item in enumerate(items, start=1):
        st.markdown(f"**{numero}.**")
        for clave, valor in item.items():
            if valor in (None, "", []):
                continue
            if isinstance(valor, list):
                valor = " · ".join(str(v) for v in valor)
            etiqueta = ETIQUETAS.get(clave, clave.replace("_", " ").capitalize())
            st.markdown(f"*{etiqueta}:* {texto_seguro(valor)}")


def mostrar_pie(paquete):
    if paquete.evaluacion_calidad.observaciones:
        with st.expander("Observaciones del revisor"):
            st.markdown(texto_seguro(paquete.evaluacion_calidad.observaciones))
    if paquete.fuentes:
        with st.expander(f"Fuentes ({len(paquete.fuentes)})"):
            st.caption("Consulta los documentos utilizados para preparar este material.")
            for fuente in paquete.fuentes:
                pagina = f", página {fuente.pagina}" if fuente.pagina else ""
                st.markdown(f"- **{fuente.documento}**, fragmento {fuente.fragmento}{pagina}: "
                            f"{texto_seguro(fuente.extracto)}")
