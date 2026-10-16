"""El único CSS de la app (spec §9, v2.2): pega al fondo del menú lateral el bloque del usuario.

Streamlit 1.65 no tiene una opción nativa para esto. Usa los data-testid de Streamlit: si una versión futura
los cambia, el bloque vuelve a quedar justo debajo del menú y nada más se rompe.
"""

import streamlit as st

CSS = """
[data-testid="stSidebarContent"] { display: flex; flex-direction: column; }
[data-testid="stSidebarUserContent"] { margin-top: auto; }
"""


def aplicar():
    st.html(f"<style>{CSS}</style>")
