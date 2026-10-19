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
# El logo de la barra lateral cambia con el tema: el claro no se leería sobre el fondo oscuro.
# Límite conocido: si se cambia el tema en ⋮ → Settings, Streamlit no vuelve a correr el script y el
# logo anterior queda hasta el siguiente clic (aceptado el 14-oct).
st.logo(str(marca.logo_para(st.context.theme.type)), size="large", icon_image=str(marca.ICONO))

pagina_estudiante = st.Page(estudiante.mostrar, title="Estudiante", url_path="estudiante", icon=":material/school:")
pagina_admin = st.Page(admin.mostrar, title="Administración", url_path="admin",
                       icon=":material/admin_panel_settings:")


def _portada():
    portada.mostrar(destino_estudiante=pagina_estudiante, destino_admin=pagina_admin)


pagina_portada = st.Page(_portada, title="Inicio", url_path="inicio", default=True, icon=":material/home:")
st.navigation([pagina_portada, pagina_estudiante, pagina_admin]).run()
