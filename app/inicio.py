"""Punto de entrada de NuevaMente. Se corre desde la raíz del repo:

    streamlit run app/inicio.py

Streamlit busca .streamlit/ (tema y límite de subida) en la carpeta desde donde se lanza:
si se corre desde otra carpeta, la app abre sin la identidad visual.
"""

from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
for ruta in (RAIZ / "src", RAIZ / "app"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

import streamlit as st

import marca
import menu
import sesion
from paginas import DESTINOS, acceso
from paginas.admin import configuracion, documentos, revision, temas
from paginas.estudiante import mis_temas, tema

st.set_page_config(page_title="NuevaMente", page_icon=str(marca.ICONO), layout="centered")
# El menú es verde oscuro en los dos modos: el logo del menú es siempre la versión clara
st.logo(str(marca.LOGO_MENU), size="large", icon_image=str(marca.ICONO))

FUNCIONES = {
    "mis-temas": mis_temas.mostrar,
    "documentos": documentos.mostrar,
    "temas": temas.mostrar,
    "revision": revision.mostrar,
    "configuracion": configuracion.mostrar,
}


def _paginas_del_rol(rol):
    """Arma el menú del rol y llena DESTINOS (para st.switch_page desde las páginas)."""
    DESTINOS.clear()
    secciones = {}
    for entrada in menu.entradas(rol):
        pagina = st.Page(FUNCIONES[entrada.nombre], title=entrada.titulo, icon=entrada.icono, url_path=entrada.nombre)
        DESTINOS[entrada.nombre] = pagina
        secciones.setdefault(entrada.seccion, []).append(pagina)
    if rol == "estudiante":
        # La página del tema no sale en el menú: se abre desde Mis temas
        DESTINOS["tema"] = st.Page(tema.mostrar, title="Tema", url_path="tema", visibility="hidden")
        secciones[""].append(DESTINOS["tema"])
    # Sin secciones (estudiante), una lista simple evita un encabezado vacío
    return secciones[""] if list(secciones) == [""] else secciones


def _mostrar_usuario(usuario):
    with st.sidebar:
        st.markdown(f"**{usuario.nombre}**")
        st.caption(sesion.ROL_LEGIBLE[usuario.rol])
        if st.button("Cerrar sesión", key="cerrar_sesion", icon=":material/logout:"):
            sesion.cerrar()
            st.rerun()


usuario = sesion.usuario_actual()
if usuario is None:
    DESTINOS.clear()
    st.navigation([st.Page(acceso.mostrar_inicio, title="Iniciar sesión", url_path="acceso")],
                  position="hidden").run()
elif usuario.debe_cambiar_contrasena:
    DESTINOS.clear()
    st.navigation([st.Page(acceso.mostrar_cambio, title="Cambia tu contraseña", url_path="contrasena")],
                  position="hidden").run()
else:
    pagina = st.navigation(_paginas_del_rol(usuario.rol))
    # st.navigation usa el ícono de cada página como favicon: se vuelve a fijar el de NuevaMente
    st.set_page_config(page_icon=str(marca.ICONO))
    _mostrar_usuario(usuario)
    pagina.run()
