"""Punto de entrada de NuevaMente. Se corre desde la raíz del repo:

    streamlit run app/inicio.py

Streamlit busca .streamlit/ (tema, límite de subida y contraseña del admin) en la carpeta desde
donde se lanza: si se corre desde otra carpeta, la app abre sin la identidad visual ni el admin.
"""

from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
for ruta in (RAIZ / "src", RAIZ / "app"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

import streamlit as st

import marca
from paginas import admin, estudiante, portada

st.set_page_config(page_title="NuevaMente", page_icon=str(marca.ICONO), layout="centered")
# El menú es verde oscuro en los dos modos: el logo del menú es siempre la versión clara
st.logo(str(marca.LOGO_MENU), size="large", icon_image=str(marca.ICONO))

pagina_estudiante = st.Page(estudiante.mostrar, title="Estudiante", url_path="estudiante", icon=":material/school:")
pagina_admin = st.Page(admin.mostrar, title="Administración", url_path="admin",
                       icon=":material/admin_panel_settings:")


def _portada():
    portada.mostrar(destino_estudiante=pagina_estudiante, destino_admin=pagina_admin)


pagina_portada = st.Page(_portada, title="Inicio", url_path="inicio", default=True, icon=":material/home:")
pagina = st.navigation([pagina_portada, pagina_estudiante, pagina_admin])
# st.navigation usa el ícono de cada página como favicon: se vuelve a fijar el de NuevaMente
st.set_page_config(page_icon=str(marca.ICONO))
pagina.run()
