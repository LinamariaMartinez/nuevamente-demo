"""Mini-app para probar una página con AppTest.

La página se elige con st.session_state["pagina"] = "modulo:funcion". Si no hay página (por ejemplo,
porque se cerró la sesión y se borró todo), muestra Iniciar sesión, como la app real.
"""

import importlib
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
for ruta in (RAIZ / "src", RAIZ / "app"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

import streamlit as st

from paginas import aplicar_estado_menu

modulo, funcion = st.session_state.get("pagina", "paginas.acceso:mostrar_inicio").split(":")
getattr(importlib.import_module(modulo), funcion)()
if st.session_state.get("aplicar_menu"):  # imita a inicio.py al terminar la página
    aplicar_estado_menu()
