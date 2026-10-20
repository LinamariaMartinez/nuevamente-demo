"""Usuarios (admin): crear estudiantes, asignar temas, restablecer la contraseña, activar y desbloquear (spec §6.5).

Backend solo crea y modifica estudiantes: los admins aparecen en la lista, sin acciones.
La contraseña temporal la escribe el admin o la genera la app. Se muestra al guardarla para copiarla;
después no se puede consultar (Backend guarda solo su hash): si el estudiante no puede entrar, se restablece.
"""

import streamlit as st
from pydantic import ValidationError

import sesion
from cliente_api import ErrorCliente
from contrato import LARGO_MINIMO_CONTRASENA, DatosEstudiante, generar_contrasena_temporal
from paginas import contraer_menu, mostrar_error, mostrar_modo_demo

CONTRASENA_CORTA = f"La contraseña temporal debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres."
DATOS_INCOMPLETOS = "Escribe el nombre y el usuario."
PASALA = "Pásasela al estudiante. Al entrar, la app le pedirá cambiarla."
AYUDA_CONTRASENA = f"Mínimo {LARGO_MINIMO_CONTRASENA} caracteres. Escríbela o pulsa Generar una."
CLAVES_NUEVO = ("nuevo_usuario_nombre", "nuevo_usuario_usuario", "nuevo_usuario_contrasena", "nuevo_usuario_temas")


def _generar(clave):
    """on_click de "Generar una": llena el campo antes de que se dibuje."""
    st.session_state[clave] = generar_contrasena_temporal()


def _avisar(texto, contrasena=None):
    """El aviso queda hasta la siguiente acción, para que dé tiempo de copiar la contraseña."""
    st.session_state["aviso_usuarios"] = {"texto": texto, "contrasena": contrasena}
    st.session_state.pop("panel_usuario", None)
    st.rerun()


def _mostrar_aviso():
    # Si viene de otra página, el aviso (y la contraseña) es de una visita anterior: se borra
    if st.session_state.get("pagina_anterior") not in (None, "usuarios"):
        st.session_state.pop("aviso_usuarios", None)
    aviso = st.session_state.get("aviso_usuarios")
    if not aviso:
        return
    st.success(aviso["texto"])
    if aviso["contrasena"]:
        st.code(aviso["contrasena"], language=None)  # st.code trae el botón de copiar
        st.caption(PASALA)


def _campo_contrasena(clave, boton):
    st.text_input("Contraseña temporal", key=clave, help=AYUDA_CONTRASENA)
    st.button("Generar una", key=boton, icon=":material/casino:", on_click=_generar, args=(clave,))


def _crear(cliente, nombres_temas):
    if st.session_state.pop("limpiar_nuevo_usuario", False):  # formulario limpio para el siguiente estudiante
        for clave in CLAVES_NUEVO:
            st.session_state.pop(clave, None)
    with st.container(border=True):
        st.subheader("Crear estudiante")
        st.text_input("Nombre completo", key="nuevo_usuario_nombre")
        st.text_input("Usuario", key="nuevo_usuario_usuario", help="Con este nombre inicia sesión.")
        _campo_contrasena("nuevo_usuario_contrasena", "generar_nueva")
        st.multiselect("Temas", list(nombres_temas), format_func=nombres_temas.get, key="nuevo_usuario_temas",
                       placeholder="Elige uno o varios")
        if not st.button("Crear", key="crear_usuario", type="primary"):
            return
    # Sin espacios al borde: si no, la que se muestra no sería la que se guarda
    contrasena = st.session_state.get("nuevo_usuario_contrasena", "").strip()
    if len(contrasena) < LARGO_MINIMO_CONTRASENA:
        st.warning(CONTRASENA_CORTA)
        return
    try:
        datos = DatosEstudiante(nombre=st.session_state.get("nuevo_usuario_nombre", ""),
                                usuario=st.session_state.get("nuevo_usuario_usuario", ""),
                                contrasena_temporal=contrasena,
                                temas=st.session_state.get("nuevo_usuario_temas", []))
    except ValidationError:
        st.warning(DATOS_INCOMPLETOS)
        return
    try:
        creado = cliente.crear_estudiante(datos)
    except ErrorCliente as error:
        mostrar_error(error)
        return
    st.session_state["limpiar_nuevo_usuario"] = True
    _avisar(f"Estudiante creado: {creado.nombre}", contrasena)


def _panel_temas(cliente, usuario, nombres_temas):
    clave = f"temas_{usuario.id_usuario}_valor"
    st.multiselect("Temas", list(nombres_temas), default=[t for t in usuario.temas if t in nombres_temas],
                   format_func=nombres_temas.get, key=clave, placeholder="Elige uno o varios")
    guardar, cancelar = st.columns(2)
    if guardar.button("Guardar", key=f"guardar_temas_{usuario.id_usuario}", type="primary"):
        try:
            cliente.cambiar_temas(usuario, st.session_state[clave])
        except ErrorCliente as error:
            mostrar_error(error)
            return
        _avisar(f"Temas guardados: {usuario.nombre}")
    _boton_cancelar(cancelar, usuario)


def _panel_contrasena(cliente, usuario):
    clave = f"restablecer_{usuario.id_usuario}_contrasena"
    _campo_contrasena(clave, f"generar_{usuario.id_usuario}")
    guardar, cancelar = st.columns(2)
    if guardar.button("Guardar", key=f"guardar_contrasena_{usuario.id_usuario}", type="primary"):
        contrasena = st.session_state.get(clave, "").strip()
        if len(contrasena) < LARGO_MINIMO_CONTRASENA:
            st.warning(CONTRASENA_CORTA)
            return
        try:
            cliente.restablecer_contrasena(usuario.id_usuario, contrasena)
        except ErrorCliente as error:
            mostrar_error(error)
            return
        st.session_state.pop(clave, None)
        _avisar(f"Contraseña restablecida: {usuario.nombre}", contrasena)
    _boton_cancelar(cancelar, usuario)


def _panel_desactivar(cliente, usuario):
    # Acción sensible: se confirma con un segundo botón, igual que Retirar en Temas
    st.warning(f"¿Desactivar a «{usuario.nombre}»? No podrá iniciar sesión hasta que la actives de nuevo.")
    si, no = st.columns(2)
    if si.button("Sí, desactivar", key=f"confirmar_desactivar_{usuario.id_usuario}", type="primary"):
        _hacer(lambda: cliente.cambiar_activo(usuario.id_usuario, False), f"Cuenta desactivada: {usuario.nombre}")
    _boton_cancelar(no, usuario)


def _boton_cancelar(columna, usuario):
    if columna.button("Cancelar", key=f"cancelar_{usuario.id_usuario}"):
        st.session_state.pop("panel_usuario", None)
        st.rerun()


def _hacer(accion, aviso):
    try:
        accion()
    except ErrorCliente as error:
        mostrar_error(error)
        return
    _avisar(aviso)


def _abrir_panel(nombre, usuario):
    st.session_state.pop("aviso_usuarios", None)
    st.session_state["panel_usuario"] = (nombre, usuario.id_usuario)
    st.rerun()


def _acciones(cliente, usuario, nombres_temas):
    panel = st.session_state.get("panel_usuario")
    if panel == ("temas", usuario.id_usuario):
        _panel_temas(cliente, usuario, nombres_temas)
        return
    if panel == ("contrasena", usuario.id_usuario):
        _panel_contrasena(cliente, usuario)
        return
    if panel == ("desactivar", usuario.id_usuario):
        _panel_desactivar(cliente, usuario)
        return
    temas, contrasena, activo, desbloquear = st.columns(4)
    if temas.button("Temas", key=f"temas_{usuario.id_usuario}", icon=":material/topic:"):
        _abrir_panel("temas", usuario)
    if contrasena.button("Restablecer contraseña", key=f"restablecer_{usuario.id_usuario}", icon=":material/key:"):
        _abrir_panel("contrasena", usuario)
    if usuario.activo:
        if activo.button("Desactivar", key=f"desactivar_{usuario.id_usuario}", icon=":material/person_off:"):
            _abrir_panel("desactivar", usuario)
    elif activo.button("Activar", key=f"activar_{usuario.id_usuario}", icon=":material/person_check:"):
        _hacer(lambda: cliente.cambiar_activo(usuario.id_usuario, True), f"Cuenta activada: {usuario.nombre}")
    if desbloquear.button("Desbloquear", key=f"desbloquear_{usuario.id_usuario}", icon=":material/lock_open:",
                          help="Quita el bloqueo por demasiados intentos fallidos al iniciar sesión."):
        _hacer(lambda: cliente.desbloquear(usuario.id_usuario), f"Cuenta desbloqueada: {usuario.nombre}")


def _tarjeta(cliente, usuario, nombres_temas):
    with st.container(border=True):
        nombre, estado = st.columns([4, 1], vertical_alignment="center")
        nombre.markdown(f"**{usuario.nombre}**")
        estado.markdown(":green-badge[Activa]" if usuario.activo else ":red-badge[Inactiva]")
        detalle = f"{usuario.usuario} · {sesion.ROL_LEGIBLE[usuario.rol]}"
        if usuario.rol == "estudiante":
            temas = ", ".join(nombres_temas.get(t, t) for t in usuario.temas) or "sin temas"
            st.caption(f"{detalle} · Temas: {temas}")
            _acciones(cliente, usuario, nombres_temas)
        else:
            st.caption(detalle)


def mostrar():
    sesion.exigir_rol("admin")
    contraer_menu()  # la lista de usuarios ocupa siempre la columna derecha
    cliente = sesion.cliente_de_sesion()
    st.title("Usuarios")
    st.caption("Crea las cuentas de quienes estudian y asígnales sus temas.")
    mostrar_modo_demo(cliente)
    _mostrar_aviso()
    try:
        usuarios = cliente.listar_usuarios()
        nombres_temas = {tema.id_tema: tema.nombre for tema in cliente.listar_temas()}
    except ErrorCliente as error:
        mostrar_error(error)
        return
    # Dos columnas (spec §6.6): crear a la izquierda, la lista a la derecha
    izquierda, derecha = st.columns([1, 2], gap="large")
    with izquierda:
        _crear(cliente, nombres_temas)
    with derecha:
        st.subheader("Cuentas")
        for usuario in usuarios:
            _tarjeta(cliente, usuario, nombres_temas)
