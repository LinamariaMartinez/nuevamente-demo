"""Punto de entrada de NuevaMente. Se corre desde la raíz del repo:

    streamlit run app/inicio.py
"""

from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
for ruta in (RAIZ / "src", RAIZ / "app"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

import streamlit as st

from paginas import admin, estudiante, portada

st.set_page_config(page_title="NuevaMente", layout="centered")

pagina_estudiante = st.Page(estudiante.mostrar, title="Estudiante", url_path="estudiante")
pagina_admin = st.Page(admin.mostrar, title="Admin", url_path="admin")


def _portada():
    portada.mostrar(destino_estudiante=pagina_estudiante, destino_admin=pagina_admin)


pagina_portada = st.Page(_portada, title="Inicio", url_path="inicio", default=True)
st.navigation([pagina_portada, pagina_estudiante, pagina_admin]).run()
