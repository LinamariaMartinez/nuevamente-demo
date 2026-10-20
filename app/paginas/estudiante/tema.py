"""Página del tema (estudiante): estudiar con material hecho a partir de los documentos del tema (spec §6.3)."""

import streamlit as st

import sesion
from cliente_api import ErrorCliente
from contrato import FORMATOS, LARGO_MAXIMO_TEMA, PERFILES, MaterialEnRevision, SolicitudPaquete
from paginas import contraer_menu, fecha_local, ir_a, mostrar_error, mostrar_modo_demo
from vistas import mostrar_paquete

EN_REVISION = "Este material necesita una revisión adicional antes de estar disponible."
AYUDA_NIVEL = "La dificultad cambia la profundidad de la explicación, no las fuentes utilizadas."
PRACTICA = "Práctica: no cuenta para tu nota."
TEMA_NO_DISPONIBLE = "Este tema ya no está disponible. Vuelve a Mis temas para ver los que tienes asignados."
RESERVADO = "Elige tu nivel y formato y pulsa Generar material. Aquí aparecerá tu material."
SIN_MATERIAL = "Aquí aparecerá el material que generes."


def _tema_elegido(cliente):
    """El tema que se abrió desde Mis temas, o None si ya no está asignado. Lanza ErrorCliente."""
    id_tema = st.session_state.get("tema_elegido")
    for tema in cliente.listar_temas():
        if tema.id_tema == id_tema:
            return tema
    return None


def _quitar_material_si_cambio(id_tema):
    """Si cambian el tema, el nivel o el formato, el material anterior ya no corresponde."""
    elegido = (id_tema, st.session_state.get("perfil"), st.session_state.get("formato"))
    if st.session_state.get("material_de") != elegido:
        st.session_state.pop("paquete", None)
        st.session_state.pop("error_generacion", None)


def _generar(cliente, tema):
    solicitud = SolicitudPaquete(
        id_tema=tema.id_tema,
        tema=st.session_state.get("pedido", ""),
        perfil_destinatario=st.session_state["perfil"],
        formato_salida=st.session_state["formato"],
    )
    st.session_state.pop("error_generacion", None)
    st.session_state.pop("paquete", None)
    st.session_state["material_de"] = (tema.id_tema, solicitud.perfil_destinatario, solicitud.formato_salida)
    try:
        with st.spinner("Estamos preparando el material a partir de los documentos de tu institución."):
            st.session_state["paquete"] = cliente.generar_paquete(solicitud)
    except ErrorCliente as error:
        if error.tipo == "sesion_vencida":
            mostrar_error(error)  # vuelve a Iniciar sesión
        st.session_state["error_generacion"] = error


def _mi_material(cliente, tema):
    """Lo que la persona generó en este tema y lo que el admin le aprobó; Abrir lo muestra a la derecha."""
    with st.container(border=True):
        st.subheader("Mi material")
        try:
            materiales = cliente.listar_mi_material(tema.id_tema)
        except ErrorCliente as error:
            mostrar_error(error)
            return
        if not materiales:
            st.info(SIN_MATERIAL)
            return
        for material in sorted(materiales, key=lambda m: m.creado_en, reverse=True):
            info, accion = st.columns([3, 1], vertical_alignment="center")
            info.markdown(f"**{material.titulo or material.tema}**")
            info.caption(f"{material.formato} · {fecha_local(material.creado_en)}")
            if accion.button("Abrir", key=f"abrir_material_{material.id}"):
                _abrir(cliente, tema, material.id)


def _abrir(cliente, tema, id_paquete):
    try:
        st.session_state["paquete"] = cliente.obtener_paquete(id_paquete)
    except ErrorCliente as error:
        mostrar_error(error)
        return
    st.session_state.pop("error_generacion", None)
    # Queda abierto hasta que la persona cambie el nivel o el formato
    st.session_state["material_de"] = (tema.id_tema, st.session_state.get("perfil"), st.session_state.get("formato"))


def _boton_reintentar(etiqueta="Reintentar"):
    if st.button(etiqueta, key="reintentar"):
        st.session_state["reintentar_pedido"] = True
        st.rerun()


def _mostrar_resultado():
    error = st.session_state.get("error_generacion")
    if error is not None:
        mostrar_error(error)
        _boton_reintentar()
        return
    paquete = st.session_state.get("paquete")
    if paquete is None:
        st.info(RESERVADO, icon=":material/auto_stories:")  # reserva el lugar: la pantalla no salta
        return
    if isinstance(paquete, MaterialEnRevision):
        # No superó la revisión automática: no se muestra hasta que lo revise un administrador
        st.info(EN_REVISION)
        _boton_reintentar("Generar otra versión")
        return
    contraer_menu()  # hay material a la derecha: más espacio para leer
    if paquete.metadatos.formato_generado == "Quiz":
        st.caption(PRACTICA)
    mostrar_paquete(paquete)


def mostrar():
    sesion.exigir_rol("estudiante")
    cliente = sesion.cliente_de_sesion()
    if st.button("Mis temas", key="volver", icon=":material/arrow_back:"):
        ir_a("mis-temas")
    if "tema_elegido" not in st.session_state:  # llegó sin elegir tema: vuelve a la lista
        ir_a("mis-temas")
    try:
        tema = _tema_elegido(cliente)
    except ErrorCliente as error:
        mostrar_error(error)
        return
    if tema is None:
        st.info(TEMA_NO_DISPONIBLE)
        return

    st.title(tema.nombre)
    if tema.descripcion:
        st.write(tema.descripcion)
    st.caption("Documentos de este tema: " + ", ".join(d.titulo for d in tema.documentos))
    mostrar_modo_demo(cliente)
    disponible = cliente.salud()
    if not disponible:
        st.warning("El servicio no está disponible en este momento. Inténtalo de nuevo más tarde.")

    # Dos columnas (spec §6.6): el formulario a la izquierda, el material a la derecha
    izquierda, derecha = st.columns([1, 2], gap="large")
    with izquierda:
        with st.container(border=True):
            st.subheader("Estudiar")
            st.selectbox("Tu nivel", PERFILES, key="perfil", help=AYUDA_NIVEL)
            st.selectbox("Formato", FORMATOS, key="formato")
            st.text_input("¿Algo en particular? (opcional)", key="pedido", max_chars=LARGO_MAXIMO_TEMA,
                          placeholder="Ej.: reglas de seguridad")
            st.caption(f"Sector: {tema.nicho_sector}")  # lo elige el admin en el tema
            _quitar_material_si_cambio(tema.id_tema)
            reintentar = st.session_state.pop("reintentar_pedido", False)
            if st.button("Generar material", key="generar", type="primary") or reintentar:
                _generar(cliente, tema)
        _mi_material(cliente, tema)  # después de generar: así ya aparece lo nuevo
    with derecha:
        _mostrar_resultado()
