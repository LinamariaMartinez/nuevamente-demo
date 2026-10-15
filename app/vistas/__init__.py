"""Directorio de vistas: decide cómo se dibuja un paquete según su formato.

Para agregar una vista interactiva (capa 2): crear vistas/<nombre>.py con una función
mostrar(paquete, items) y registrarla en VISTAS. Si un formato no tiene vista propia, o si
sus items no cumplen el contrato, se usa la vista genérica.
"""

import streamlit as st
from pydantic import ValidationError

from contrato import items_validos
from vistas import flashcards, generica, guia, quiz

VISTAS = {
    "Flashcards": flashcards,
    "Quiz": quiz,
    "Tutorial": guia,
}


def mostrar_paquete(paquete):
    if paquete.status == "error":  # un paquete de error no trae contenido que dibujar
        st.error(paquete.mensaje_error or "No se pudo generar este material. Inténtalo de nuevo.")
        return
    generica.mostrar_encabezado(paquete)
    vista = VISTAS.get(paquete.metadatos.formato_generado)
    items = None
    if vista is not None:
        try:
            items = items_validos(paquete)
        except (ValidationError, KeyError):
            items = None
    if vista is not None and items:
        vista.mostrar(paquete, items)
    else:
        generica.mostrar_items(paquete)
    generica.mostrar_pie(paquete)
