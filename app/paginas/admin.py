"""Página del admin: sube documentos, revisa su estado y revisa los paquetes marcados."""

import hmac

import streamlit as st

from cliente_api import ErrorCliente
from contrato import NICHOS
from paginas import cliente_de_sesion
from vistas import mostrar_paquete

EXTENSIONES = ("pdf", "md", "txt")
TAMANO_MAXIMO_MB = 10


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


def _contrasena_configurada():
    try:
        return st.secrets.get("contrasena_admin") or None
    except Exception:  # no existe .streamlit/secrets.toml
        return None


def _pedir_contrasena():
    esperada = _contrasena_configurada()
    if esperada is None:
        st.error("Falta configurar la contraseña del admin (contrasena_admin en .streamlit/secrets.toml).")
        return
    clave = st.text_input("Contraseña", type="password", key="clave_admin")
    if st.button("Entrar", key="entrar"):
        if hmac.compare_digest(clave.encode(), str(esperada).encode()):
            st.session_state["admin_ok"] = True
            st.rerun()
        else:
            st.error("La contraseña no es correcta. Revísala e inténtalo de nuevo.")


def _mostrar_error(error):
    st.error(error.mensaje)
    if error.detalle:
        with st.expander("Ver detalle"):
            st.code(error.detalle)


def _seccion_sector(cliente):
    st.subheader("Sector de la institución")
    try:
        actual = cliente.obtener_configuracion().sector
    except ErrorCliente as error:
        _mostrar_error(error)
        return
    elegido = st.selectbox("El material se adapta a este sector", NICHOS, index=NICHOS.index(actual), key="sector")
    st.caption("El sector adapta los ejemplos y el vocabulario del material; no cambia lo que dicen los documentos.")
    if st.button("Guardar cambios", key="guardar_sector"):
        try:
            st.success(f"Sector guardado: {cliente.guardar_configuracion(elegido).sector}")
        except ErrorCliente as error:
            _mostrar_error(error)


def _seccion_subir(cliente):
    st.subheader("Subir documento")
    archivo = st.file_uploader(f"PDF, Markdown o TXT (máximo {TAMANO_MAXIMO_MB} MB)", type=list(EXTENSIONES), key="archivo")
    if archivo is None or not st.button("Subir e indexar", key="subir"):
        return
    problema = validar_archivo(archivo.name, archivo.size)
    if problema:
        st.error(problema)
        return
    try:
        documento = cliente.subir_documento(archivo.name, archivo.getvalue())
        st.success(f"{documento.nombre}: {documento.estado}")
    except ErrorCliente as error:
        _mostrar_error(error)


def _seccion_documentos(cliente):
    st.subheader("Documentos")
    try:
        documentos = cliente.listar_documentos()
    except ErrorCliente as error:
        _mostrar_error(error)
        return
    if not documentos:
        st.info("Todavía no hay documentos. Sube el primero en la sección de arriba.")
        return
    for documento in documentos:
        if documento.estado == "error":
            st.error(f"{documento.nombre}: {documento.error or 'error sin detalle.'}")
        else:
            st.markdown(f"**{documento.nombre}** · {documento.estado} · {documento.chunks} fragmentos")


def _seccion_revision(cliente):
    st.subheader("Paquetes por revisar")
    try:
        resumenes = cliente.listar_paquetes_revision()
    except ErrorCliente as error:
        _mostrar_error(error)
        return
    if not resumenes:
        st.info("No hay paquetes pendientes de revisión.")
        return
    for resumen in resumenes:
        st.markdown(f"**{resumen.tema}** · {resumen.formato} · anclaje {resumen.anclaje_fuente_score:.0%}"
                    f" · {resumen.creado_en:%Y-%m-%d %H:%M}")
        if st.button("Abrir", key=f"abrir_{resumen.id_paquete}"):
            st.session_state["paquete_admin"] = resumen.id_paquete
    elegido = st.session_state.get("paquete_admin")
    if elegido:
        try:
            paquete = cliente.obtener_paquete(elegido)
        except ErrorCliente as error:
            _mostrar_error(error)
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
    st.title("Panel del administrador")
    if not st.session_state.get("admin_ok"):
        _pedir_contrasena()
        return
    cliente = cliente_de_sesion()
    if cliente.es_mock:
        st.info("Modo demostración: datos de ejemplo")
    _seccion_sector(cliente)
    _seccion_subir(cliente)
    _seccion_documentos(cliente)
    _seccion_revision(cliente)
