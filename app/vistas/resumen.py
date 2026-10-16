"""Vista del Resumen (v2.2): la idea central destacada, cada sección como tarjeta y los conceptos clave al final."""

import streamlit as st

from vistas.generica import texto_seguro

POR_FILA = 3


def mostrar(paquete, items):
    introduccion = paquete.contenido_adaptado.introduccion_contextualizada
    if introduccion:
        with st.container(border=True):
            st.markdown(":material/lightbulb: **En pocas palabras**")
            st.markdown(texto_seguro(introduccion))
    for inicio in range(0, len(items), POR_FILA):
        # Siempre POR_FILA columnas: las tarjetas miden lo mismo aunque la última fila quede incompleta
        for columna, item in zip(st.columns(POR_FILA), items[inicio:inicio + POR_FILA]):
            with columna.container(border=True):
                st.markdown(f"**{texto_seguro(item.titulo)}**")
                st.markdown(texto_seguro(item.contenido))
    conceptos = paquete.metadatos.conceptos_clave
    if conceptos:
        st.markdown("**Conceptos clave:** " + " ".join(f":gray-badge[{texto_seguro(c)}]" for c in conceptos))
