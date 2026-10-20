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

import estilo
import marca
import menu
import sesion
from paginas import DESTINOS, acceso, aplicar_estado_menu, landing
from paginas.admin import configuracion, documentos, revision, temas, usuarios
from paginas.estudiante import mis_temas, tema

# Pantalla ancha (v2.2): las pantallas de acción usan dos columnas (spec §6.6)
st.set_page_config(page_title="NuevaMente", page_icon=str(marca.FAVICON), layout="wide")

FUNCIONES = {
    "mis-temas": mis_temas.mostrar,
    "documentos": documentos.mostrar,
    "temas": temas.mostrar,
    "revision": revision.mostrar,
    "usuarios": usuarios.mostrar,
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
    # Con sesión vencida se va directo a Iniciar sesión: en la landing el aviso se perdería
    vencida = "aviso_acceso" in st.session_state
    DESTINOS["landing"] = st.Page(landing.mostrar, title="NuevaMente", url_path="inicio", default=not vencida)
    DESTINOS["acceso"] = st.Page(acceso.mostrar_inicio, title="Iniciar sesión", url_path="acceso", default=vencida,
                                 visibility="hidden")
    st.navigation([DESTINOS["landing"], DESTINOS["acceso"]]).run()
elif usuario.debe_cambiar_contrasena:
    DESTINOS.clear()
    st.navigation([st.Page(acceso.mostrar_cambio, title="Cambia tu contraseña", url_path="contrasena")]).run()
else:
    # El logo va solo dentro de la app: st.logo hace aparecer la barra lateral, y la landing y el acceso no llevan menú.
    # El menú es verde oscuro en los dos modos: el logo del menú es siempre la versión clara
    st.logo(str(marca.LOGO_MENU), size="large", icon_image=str(marca.ICONO))
    pagina = st.navigation(_paginas_del_rol(usuario.rol))
    # st.navigation usa el ícono de cada página como favicon: se vuelve a fijar el de NuevaMente
    st.set_page_config(page_icon=str(marca.FAVICON))
    estilo.aplicar()  # nombre, rol y Cerrar sesión al fondo del menú
    _mostrar_usuario(usuario)
    # Las páginas pueden saber si la persona acaba de llegar (por ejemplo, Usuarios borra avisos viejos)
    st.session_state["pagina_anterior"] = st.session_state.get("pagina_actual")
    # Por el nombre interno: la página por defecto tiene url_path vacío
    st.session_state["pagina_actual"] = next((n for n, p in DESTINOS.items() if p is pagina), pagina.url_path)
    pagina.run()
    aplicar_estado_menu()  # al final: la página ya dijo si quiere el menú contraído
