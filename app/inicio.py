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

from paginas import estudiante

st.set_page_config(page_title="NuevaMente", layout="centered")

paginas = [st.Page(estudiante.mostrar, title="Estudiante", url_path="estudiante", default=True)]
st.navigation(paginas).run()
