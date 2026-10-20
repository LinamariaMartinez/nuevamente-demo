"""Temas (admin): crear, editar y retirar temas. Cada tema agrupa uno o varios documentos (spec §6.5)."""

import streamlit as st
from pydantic import ValidationError

import sesion
from cliente_api import ErrorCliente
from contrato import LARGO_MAXIMO_DESCRIPCION, LARGO_MAXIMO_NOMBRE_TEMA, NICHOS, DatosTema
from paginas import contraer_menu, ir_a, mostrar_error, mostrar_modo_demo

DATOS_INCOMPLETOS = "Escribe un nombre y elige al menos un documento."
SIN_DOCUMENTOS = "Todavía no hay documentos. Sube al menos uno para crear un tema."
VACIO = "Todavía no hay temas. Crea el primero con el formulario de la izquierda."
AYUDA_SECTOR = "Adapta los ejemplos y el vocabulario del material; no cambia lo que dicen los documentos."
CLAVES_NUEVO = ("nuevo_nombre", "nuevo_descripcion", "nuevo_sector", "nuevo_documentos")


def _formulario(clave, titulos, tema=None):
    """Crear (tema=None) o editar. `titulos`: id del documento → título.

    Devuelve DatosTema si se envió y es válido; si no, None.

    st.form conserva lo escrito cuando algo falla.
    """
    with st.form(f"form_{clave}"):
        nombre = st.text_input("Nombre", value=tema.nombre if tema else "", max_chars=LARGO_MAXIMO_NOMBRE_TEMA,
                               key=f"{clave}_nombre")
        descripcion = st.text_area("Descripción", value=tema.descripcion if tema else "",
                                   max_chars=LARGO_MAXIMO_DESCRIPCION, key=f"{clave}_descripcion")
        # Un sector que no está en la lista (por ejemplo, creado por /docs) abre en General
        sector = tema.nicho_sector if tema and tema.nicho_sector in NICHOS else "General"
        st.selectbox("Sector", NICHOS, index=NICHOS.index(sector), key=f"{clave}_sector", help=AYUDA_SECTOR)
        elegidos = [d.id for d in (tema.documentos if tema else []) if d.id in titulos]
        # Se muestra el título y se guarda el id
        documentos = st.multiselect("Documentos", list(titulos), default=elegidos, format_func=titulos.get,
                                    key=f"{clave}_documentos", placeholder="Elige uno o varios")
        enviado = st.form_submit_button("Guardar cambios" if tema else "Crear tema", type="primary",
                                        key=f"{clave}_enviar")
    if not enviado:
        return None
    try:
        return DatosTema(nombre=nombre, descripcion=descripcion, nicho_sector=st.session_state[f"{clave}_sector"],
                         documentos=documentos)
    except ValidationError:
        st.warning(DATOS_INCOMPLETOS)
        return None


def _crear(cliente, titulos):
    with st.container(border=True):
        st.subheader("Crear tema")
        if not titulos:
            st.info(SIN_DOCUMENTOS)
            if st.button("Ir a Documentos", key="ir_documentos"):
                ir_a("documentos")
            return
        datos = _formulario("nuevo", titulos)
        if datos is None:
            return
        try:
            tema = cliente.crear_tema(datos)
        except ErrorCliente as error:
            mostrar_error(error)
            return
        for clave in CLAVES_NUEVO:  # formulario limpio para el siguiente tema
            st.session_state.pop(clave, None)
        st.session_state["aviso_temas"] = f"Tema creado: {tema.nombre}"
        st.rerun()


def _editar(cliente, tema, titulos):
    datos = _formulario(f"editar_{tema.id_tema}", titulos, tema)
    if st.button("Cancelar", key=f"cancelar_editar_{tema.id_tema}"):
        st.session_state.pop("editando_tema", None)
        st.rerun()
    if datos is None:
        return
    try:
        editado = cliente.editar_tema(tema.id_tema, datos)
    except ErrorCliente as error:
        mostrar_error(error)
        return
    st.session_state.pop("editando_tema", None)
    st.session_state["aviso_temas"] = f"Cambios guardados: {editado.nombre}"
    st.rerun()


def _confirmar_retiro(cliente, tema):
    # Acción sensible: se confirma con un segundo botón en la misma pantalla (spec §6.6)
    st.warning(f"¿Retirar «{tema.nombre}»? Quienes lo tienen asignado dejarán de verlo.")
    si, no = st.columns(2)
    if si.button("Sí, retirar", key=f"confirmar_retirar_{tema.id_tema}", type="primary"):
        try:
            cliente.retirar_tema(tema.id_tema)
        except ErrorCliente as error:
            mostrar_error(error)
            return
        st.session_state.pop("retirando_tema", None)
        st.session_state["aviso_temas"] = f"Tema retirado: {tema.nombre}"
        st.rerun()
    if no.button("Cancelar", key=f"cancelar_retirar_{tema.id_tema}"):
        st.session_state.pop("retirando_tema", None)
        st.rerun()


def _tarjeta(cliente, tema, titulos):
    with st.container(border=True):
        if st.session_state.get("editando_tema") == tema.id_tema:
            _editar(cliente, tema, titulos)
            return
        st.markdown(f"**{tema.nombre}**")
        if tema.descripcion:
            st.write(tema.descripcion)
        st.caption(f"Sector: {tema.nicho_sector} · Documentos: " + ", ".join(d.titulo for d in tema.documentos))
        if st.session_state.get("retirando_tema") == tema.id_tema:
            _confirmar_retiro(cliente, tema)
            return
        editar, retirar = st.columns(2)
        if editar.button("Editar", key=f"editar_{tema.id_tema}", icon=":material/edit:"):
            st.session_state["editando_tema"] = tema.id_tema
            st.rerun()
        if retirar.button("Retirar", key=f"retirar_{tema.id_tema}", icon=":material/delete:"):
            st.session_state["retirando_tema"] = tema.id_tema
            st.rerun()


def mostrar():
    sesion.exigir_rol("admin")
    contraer_menu()  # la lista de temas ocupa siempre la columna derecha
    cliente = sesion.cliente_de_sesion()
    st.title("Temas")
    st.caption("Agrupa documentos en temas. Quien estudia solo ve los temas que le asignan.")
    mostrar_modo_demo(cliente)
    aviso = st.session_state.pop("aviso_temas", None)
    if aviso:
        st.success(aviso)
    try:
        documentos = cliente.listar_documentos()
        temas = cliente.listar_temas()
    except ErrorCliente as error:
        mostrar_error(error)
        return
    titulos = {d.id: d.titulo for d in documentos}
    # Dos columnas (spec §6.6): crear a la izquierda, la lista a la derecha
    izquierda, derecha = st.columns([1, 2], gap="large")
    with izquierda:
        _crear(cliente, titulos)
    with derecha:
        st.subheader("Temas creados")
        if not temas:
            st.info(VACIO)
            return
        for tema in temas:
            _tarjeta(cliente, tema, titulos)
