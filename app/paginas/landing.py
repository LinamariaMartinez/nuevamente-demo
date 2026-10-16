"""Landing (v2.2): qué es NuevaMente, para el jurado y quien visite el proyecto; lleva a Iniciar sesión (spec §6.0)."""

import streamlit as st

import marca
import sesion
from paginas import ir_a

TITULAR = "De documentación técnica a material de estudio, en minutos."
EXPLICACION = ("Tu institución sube sus manuales; NuevaMente los convierte en material adaptado a cada nivel, "
               "con fuentes y control de calidad.")
FORMATOS_LEGIBLES = ("Guía paso a paso", "Flashcards", "Quiz", "Resumen", "Guion de clase")
PASOS = (
    ("Sube documentos", "La institución carga sus manuales y arma temas."),
    ("Tres agentes", "El Investigador busca, el Redactor adapta y el Revisor verifica."),
    ("Estudia y evalúa", "Material a tu nivel, con fuentes; luego, la evaluación del tema."),
)
POR_DENTRO = (
    ("Fiel a las fuentes", "RAG: cada material cita los fragmentos de los documentos que usó."),
    ("Calidad revisada", "Puntaje de 0.8 o más; si no lo alcanza, se corrige hasta 3 veces."),
    ("Listo para integrar", "Salida en JSON estructurado y documentos en OCI Object Storage."),
)
# Solo existen en modo mock (app/mocks/institucion/usuarios.json)
CUENTAS_DEMO = (
    ("Estudiante", "laura", "demo-estudiante"),
    ("Con contraseña temporal", "mateo", "temporal-123"),
    ("Administración", "admin", "demo-admin"),
)


def _tarjetas(titulo, ancla, elementos, numerar=False):
    st.subheader(titulo, anchor=ancla)
    for numero, (columna, (nombre, texto)) in enumerate(zip(st.columns(len(elementos)), elementos), start=1):
        with columna.container(border=True):
            st.markdown(f"**{numero}. {nombre}**" if numerar else f"**{nombre}**")
            st.caption(texto)


def _demo():
    with st.container(border=True):
        st.markdown("**Prueba la demo**")
        if sesion.cliente_de_sesion().es_mock:
            for rol, usuario, contrasena in CUENTAS_DEMO:
                st.markdown(f"{rol}: `{usuario}` / `{contrasena}`")
        else:
            st.caption("Pide tu usuario a quien administra la plataforma.")
        st.markdown(" ".join(f":gray-badge[{formato}]" for formato in FORMATOS_LEGIBLES))


def mostrar():
    mensaje, demo = st.columns([3, 2], gap="large", vertical_alignment="center")
    with mensaje:
        st.image(str(marca.logo_principal(st.context.theme.type)), width=320)
        st.title(TITULAR)
        st.write(EXPLICACION)
        entrar, como = st.columns([1, 2], vertical_alignment="center")
        if entrar.button("Iniciar sesión", key="ir_acceso", type="primary"):
            ir_a("acceso")
        como.markdown("[Ver cómo funciona](#como-funciona)")
    with demo:
        _demo()
    _tarjetas("Cómo funciona", "como-funciona", PASOS, numerar=True)
    _tarjetas("Por dentro", "por-dentro", POR_DENTRO)
