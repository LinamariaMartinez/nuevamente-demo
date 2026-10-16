"""Documentos (admin): subir la documentación de la institución y ver su estado (spec §6.5)."""

import streamlit as st

import sesion
from cliente_api import ErrorCliente
from paginas import mostrar_error, mostrar_modo_demo

EXTENSIONES = ("pdf", "md", "txt")
TAMANO_MAXIMO_MB = 10
ESTADO_DOCUMENTO = {
    "indexado": ("Indexado", "green"),
    "procesando": ("Procesando", "blue"),
    "error": ("Con error", "red"),
}
VACIO = "Todavía no hay documentos. Sube el primero en la sección de arriba."


def validar_archivo(nombre, tamano_bytes):
    """Devuelve el mensaje de error para el admin, o None si el archivo se puede subir."""
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension not in EXTENSIONES:
        return "Solo se aceptan archivos PDF, Markdown o TXT."
    if tamano_bytes == 0:
        return "El archivo está vacío."
    if tamano_bytes > TAMANO_MAXIMO_MB * 1024 * 1024:
        return f"El archivo supera {TAMANO_MAXIMO_MB} MB."
    return None


def temas_por_documento(temas):
    """nombre del documento → nombres de los temas que lo usan."""
    usos = {}
    for tema in temas:
        for nombre in tema.documentos:
            usos.setdefault(nombre, []).append(tema.nombre)
    return usos


def _subir(cliente):
    with st.container(border=True):
        st.subheader("Subir documento")
        archivo = st.file_uploader(f"PDF, Markdown o TXT (máximo {TAMANO_MAXIMO_MB} MB)",
                                   type=list(EXTENSIONES), key="archivo")
        if archivo is None or not st.button("Subir e indexar", key="subir", type="primary"):
            return
        problema = validar_archivo(archivo.name, archivo.size)
        if problema:
            st.error(problema)
            return
        try:
            documento = cliente.subir_documento(archivo.name, archivo.getvalue())
        except ErrorCliente as error:
            mostrar_error(error)
            return
        st.success(f"{documento.nombre}: {ESTADO_DOCUMENTO[documento.estado][0]}")


def _lista(cliente):
    with st.container(border=True):
        st.subheader("Documentos subidos")
        try:
            documentos = cliente.listar_documentos()
        except ErrorCliente as error:
            mostrar_error(error)
            return
        if not documentos:
            st.info(VACIO)
            return
        try:
            usos = temas_por_documento(cliente.listar_temas())
        except ErrorCliente:
            usos = {}  # la lista de documentos sigue siendo útil sin la columna de temas
        for documento in documentos:
            nombre, estado, fragmentos, temas = st.columns([4, 2, 2, 4], vertical_alignment="center")
            nombre.markdown(f"**{documento.nombre}**")
            etiqueta, color = ESTADO_DOCUMENTO[documento.estado]
            with estado:
                st.badge(etiqueta, color=color)
            fragmentos.text(f"{documento.chunks} fragmentos")
            temas.text(", ".join(usos.get(documento.nombre, [])) or "—")
            if documento.error:
                st.caption(f"Error: {documento.error}")


def mostrar():
    sesion.exigir_rol("admin")
    cliente = sesion.cliente_de_sesion()
    st.title("Documentos")
    st.caption("Sube la documentación de la institución. Con ella se arma el material de estudio.")
    mostrar_modo_demo(cliente)
    _subir(cliente)
    _lista(cliente)
