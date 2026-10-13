"""Mini-app para probar las vistas con AppTest: dibuja el paquete guardado en session_state."""

from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
for ruta in (RAIZ / "src", RAIZ / "app"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

import streamlit as st

from contrato import Paquete
from vistas import mostrar_paquete

mostrar_paquete(Paquete.model_validate(st.session_state["datos_paquete"]))
