"""Acceso: iniciar sesión y cambiar la contraseña temporal (spec §6.1).

Las dos pantallas son una tarjeta flotante (v2.4): panel oscuro con la marca a la izquierda y el formulario a la
derecha. Los campos y botones son de Streamlit; el diseño lo da el CSS de app/plantillas/acceso.html.
"""

import base64
from html import escape
from pathlib import Path
from string import Template

import streamlit as st

import marca
import sesion
from cliente_api import ErrorCliente
from contrato import LARGO_MINIMO_CONTRASENA
from paginas import ir_a, mostrar_error
from paginas.landing import CUENTAS_DEMO, SIN_CUENTAS_DEMO

ESTILO = Path(__file__).resolve().parents[1] / "plantillas" / "acceso.html"

LEMA = ("Aprender hoy,", "construir mañana.")
PASOS = ("Consulta tus temas", "Estudia con material a tu medida", "Presenta la evaluación")
# Nombres cortos para que las cuentas quepan en una línea debajo de la tarjeta (la landing usa los largos)
ROL_CORTO = {"Con contraseña temporal": "Temporal", "Administración": "Admin"}

_PERSONA = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" '
            'stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>')
_LLAVE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" '
          'stroke-linecap="round"><circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3"/></svg>')
_HOJA = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
         '<path d="M29 60C12 57 3 41 6 16c17 2 28 16 26 36-.3 3-1.3 6-3 8Z" fill="#A9CDBD"/>'
         '<path d="M33 60c-5-22 3-44 25-54 8 25 2 47-22 54-1 .2-2 .2-3 0Z" fill="#A9CDBD"/></svg>')


def _datos_svg(svg):
    """st.html quita los <svg>: van como imagen con el SVG en data:."""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def html_estilo():
    iconos = {"icono_usuario": _datos_svg(_PERSONA.format(color="#7D948B")),
              "icono_llave": _datos_svg(_LLAVE.format(color="#7D948B"))}
    return Template(ESTILO.read_text(encoding="utf-8")).substitute(iconos)


def html_panel(titulo, texto=None, pasos=PASOS):
    """Panel oscuro de la tarjeta: logo, título (dos líneas, la segunda en verde claro) y pasos o un texto."""
    logo = _datos_svg(marca.LOGO_MENU.read_text(encoding="utf-8"))  # versión clara del logo
    primera, segunda = titulo
    detalle = (f'<p class="ac-texto">{escape(texto)}</p>' if texto else
               '<ol class="ac-pasos">' + "".join(f"<li><b>{i:02d}</b>{escape(p)}</li>" for i, p in enumerate(pasos, 1))
               + "</ol>")
    return ('<div class="ac-panel">'
            f'<img class="ac-hoja" src="{_datos_svg(_HOJA)}" alt="">'
            f'<img class="ac-logo" src="{logo}" alt="NuevaMente">'
            f'<div class="ac-pie"><p class="ac-lema">{escape(primera)} <br><span>{escape(segunda)}</span></p>{detalle}</div>'
            '</div>')


def html_encabezado(titulo, subtitulo):
    return f'<div><p class="ac-titulo">{escape(titulo)}</p><p class="ac-sub">{escape(subtitulo)}</p></div>'


def html_cuentas(es_mock):
    """Debajo de la tarjeta. Sin decir "usuario" ni "contraseña": la persona y la llave son las mismas de los campos."""
    if not es_mock:
        return f'<p class="ac-demo">{escape(SIN_CUENTAS_DEMO)}</p>'
    persona = _datos_svg(_PERSONA.format(color="#205E58"))
    llave = _datos_svg(_LLAVE.format(color="#205E58"))
    cuentas = "".join(
        f'<span class="ac-cuenta">{escape(ROL_CORTO.get(rol, rol))}'
        f'<img class="ac-icono" src="{persona}" alt="Usuario"><span class="ac-usuario">{escape(usuario)}</span>'
        f'<span class="ac-clave"><img class="ac-icono" src="{llave}" alt="Contraseña">{escape(contrasena)}</span></span>'
        for rol, usuario, contrasena in CUENTAS_DEMO)
    return f'<div class="ac-demo"><span class="ac-ceja">Demo</span>{cuentas}</div>'


def _tarjeta(panel):
    """Abre la tarjeta: dibuja el panel oscuro y devuelve la columna (300 px) donde va el formulario."""
    with st.container(key="acceso_tarjeta", horizontal=True, gap=None):
        with st.container(key="acceso_panel"):
            st.html(panel)
        with st.container(key="acceso_formulario", vertical_alignment="center", horizontal_alignment="center"):
            return st.container(key="acceso_campos", width=300)


def validar_contrasena_nueva(actual, nueva, confirmar):
    """Devuelve el problema para mostrar, o None si se puede enviar. Backend también valida."""
    if not actual:
        return "Escribe tu contraseña actual."
    if len(nueva) < LARGO_MINIMO_CONTRASENA:
        return f"La nueva contraseña debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres."
    if nueva != confirmar:
        return "Las contraseñas no coinciden."
    if nueva == actual:
        return "La nueva contraseña debe ser distinta de la actual."
    return None


def mostrar_inicio():
    st.html(html_estilo())
    with st.container(key="acceso"):
        if st.button("Volver al inicio", key="volver_landing", icon=":material/arrow_back:", type="tertiary"):
            ir_a("landing")
        with _tarjeta(html_panel(LEMA)):
            st.html(html_encabezado("Inicia sesión", "Con el usuario que te dio tu institución."))
            avisos = st.container()  # arriba de los campos; se llena después de enviar
            aviso = st.session_state.pop("aviso_acceso", None)
            if aviso:
                avisos.info(aviso)
            with st.form("form_acceso", border=False):  # en un formulario, Enter también envía
                usuario = st.text_input("Usuario", key="acceso_usuario")
                contrasena = st.text_input("Contraseña", type="password", key="acceso_contrasena")
                enviado = st.form_submit_button("Iniciar sesión", type="primary", key="iniciar_sesion", width="stretch")
        st.html(html_cuentas(sesion.cliente_de_sesion().es_mock))
    if not enviado:
        return
    if not usuario.strip() or not contrasena:
        avisos.warning("Escribe tu usuario y tu contraseña.")
        return
    try:
        sesion.iniciar(usuario, contrasena)
    except ErrorCliente as error:
        avisos.error(error.mensaje)  # sin detalle: todavía no sabemos quién es
        return
    st.rerun()


def mostrar_cambio():
    usuario = sesion.usuario_actual()
    st.html(html_estilo())
    with st.container(key="acceso"):
        panel = html_panel((f"Hola, {usuario.nombre}.", "Tu contraseña es temporal."),
                           texto="Crea una nueva para entrar a tus temas.")
        with _tarjeta(panel):
            st.html(html_encabezado("Cambia tu contraseña", f"Mínimo {LARGO_MINIMO_CONTRASENA} caracteres."))
            avisos = st.container()
            with st.form("form_cambio", border=False):
                actual = st.text_input("Contraseña actual", type="password", key="cambio_actual")
                nueva = st.text_input("Nueva contraseña", type="password", key="cambio_nueva",
                                      help=f"Mínimo {LARGO_MINIMO_CONTRASENA} caracteres.")
                confirmar = st.text_input("Confirma la nueva contraseña", type="password", key="cambio_confirmar")
                enviado = st.form_submit_button("Guardar contraseña", type="primary", key="guardar_contrasena",
                                                width="stretch")
            if st.button("Salir", key="salir_cambio", icon=":material/logout:", type="tertiary"):
                sesion.cerrar()
                st.rerun()
    if not enviado:
        return
    problema = validar_contrasena_nueva(actual, nueva, confirmar)
    if problema:
        avisos.warning(problema)
        return
    try:
        sesion.cambiar_contrasena(actual, nueva)
    except ErrorCliente as error:
        with avisos:
            mostrar_error(error)
        return
    st.rerun()
