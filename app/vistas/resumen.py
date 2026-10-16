"""Vista del Resumen (v2.2): la idea central destacada, cada sección como tarjeta y los conceptos clave al final."""

import streamlit as st

POR_FILA = 3


def mostrar(paquete, items):
    introduccion = paquete.contenido_adaptado.introduccion_contextualizada
    if introduccion:
        with st.container(border=True):
            st.markdown(":material/lightbulb: **En pocas palabras**")
            st.write(introduccion)
    for inicio in range(0, len(items), POR_FILA):
        # Siempre POR_FILA columnas: las tarjetas miden lo mismo aunque la última fila quede incompleta
        for columna, item in zip(st.columns(POR_FILA), items[inicio:inicio + POR_FILA]):
            with columna.container(border=True):
                st.markdown(f"**{item.titulo}**")
                st.write(item.contenido)
    conceptos = paquete.metadatos.conceptos_clave
    if conceptos:
        st.markdown("**Conceptos clave:** " + " ".join(f":gray-badge[{c}]" for c in conceptos))
