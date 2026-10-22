"""Directorio de vistas: decide cómo se dibuja un paquete según su formato.

Para agregar una vista interactiva (capa 2): crear vistas/<nombre>.py con una función
mostrar(paquete, items) y registrarla en VISTAS. Si un formato no tiene vista propia, o si
sus items no cumplen el contrato, se usa la vista genérica.
"""

import streamlit as st
from pydantic import ValidationError

from contrato import items_validos
from vistas import flashcards, generica, guia, guion, quiz, resumen

VISTAS = {
    "Flashcards": flashcards,
    "Quiz": quiz,
    "Tutorial": guia,
    "Resumen": resumen,
    "Guion": guion,
}
# Formatos cuya vista muestra la introducción y los conceptos clave a su manera
COMPACTOS = {"Resumen"}


def mostrar_paquete(paquete, para_admin=False):
    """`para_admin`: además muestra los datos internos del Revisor (anclaje, intentos y observaciones)."""
    formato = paquete.metadatos.formato_generado
    vista = VISTAS.get(formato)
    items = None
    if vista is not None:
        try:
            items = items_validos(paquete)
        except (ValidationError, KeyError):
            items = None
    propia = vista is not None and bool(items)
    generica.mostrar_encabezado(paquete, compacto=propia and formato in COMPACTOS, para_admin=para_admin)
    if propia:
        vista.mostrar(paquete, items)
    else:
        generica.mostrar_items(paquete)
    generica.mostrar_pie(paquete, para_admin=para_admin)
