"""Landing (v2.4): qué es NuevaMente, para el jurado y quien visite el proyecto; lleva a Iniciar sesión (spec §6.0).

La página es HTML y CSS (app/plantillas/landing.html) dibujado con st.html, sin JavaScript: el movimiento son
animaciones de CSS y lo que se puede tocar (perfil, formato, flashcard, quiz, pilares) usa radios y casillas.
Solo el botón Iniciar sesión es de Streamlit, porque cambia de página dentro de la misma sesión.
"""

import base64
from html import escape
from pathlib import Path
import re
from string import Template

import streamlit as st

import sesion
from paginas import ir_a

PLANTILLA = Path(__file__).resolve().parents[1] / "plantillas" / "landing.html"

TITULAR = "De documentación técnica a material de estudio, en minutos."
TITULAR_DESTACADO = "material de estudio"  # va en verde claro dentro del titular
EXPLICACION = ("Tu institución sube sus manuales; NuevaMente los convierte en material adaptado a cada nivel, "
               "con fuentes y control de calidad.")
# (nombre, minutos de estudio del ejemplo): los minutos salen de los mocks de cada formato
FORMATOS = (("Flashcards", 5), ("Quiz", 8), ("Guía paso a paso", 10), ("Resumen", 3), ("Guion de clase", 6))
PERFILES = ("Principiante", "Intermedio", "Avanzado")
SECTORES = ("General", "Salud", "Fintech", "E-commerce")
PASOS = (
    ("Sube documentos", "La institución carga sus manuales y arma temas, cada uno con su sector."),
    ("Tres agentes", "El Investigador busca, el Redactor adapta y el Revisor verifica."),
    ("Estudia a tu nivel", "Flashcards, quiz, guía o resumen, con sus fuentes. El quiz te muestra tu puntaje al instante."),
)
AGENTES = (
    ("Investigador", "Busca los fragmentos que responden al tema."),
    ("Redactor", "Adapta al perfil, el formato y el sector."),
    ("Revisor", "Verifica fidelidad y calidad didáctica."),
)
INSTITUCION = ("Sube documentos y arma temas con su sector",
               "Revisa y aprueba el material que no pasa el control de calidad",
               "Crea usuarios y asigna temas a cada persona")
ESTUDIANTE = ("Ve solo los temas que le asignaron",
              "Elige perfil y formato: flashcards, quiz, guía y más",
              "Guarda su material aprobado en Mi material")
# (nombre, clave, texto, bloque del paquete JSON que se muestra al lado). Los campos son los del contrato común (F06):
# quien abra /docs de la API debe ver los mismos nombres
POR_DENTRO = (
    ("Fiel a las fuentes", "RAG",
     "Cada material cita los fragmentos de los documentos que usó. Si el tema no tiene contexto suficiente, "
     "lo dice en lugar de inventar.",
     "fuentes", '"fuentes": [\n  {\n    "documento_id": "d-redes",\n    "documento": "Redes VCN en OCI",\n'
                '    "fragmento": 1,\n    "pagina": 12,\n    "extracto": "Una VCN es una red privada…"\n  }\n]'),
    ("Calidad revisada", "≥ 0.8",
     "El Revisor puntúa fidelidad a las fuentes, pedagogía y formato; si no alcanza el mínimo, se corrige hasta "
     "3 veces. Lo que aun así no pasa queda en revisión para la institución.",
     "evaluacion_calidad", '"status": "exito",\n"evaluacion_calidad": {\n  "anclaje_fuente_score": 0.86,\n'
                           '  "calidad_pedagogica_score": 0.9,\n  "cumplimiento_formato_score": 0.95,\n'
                           '  "claridad_pedagogica": "Alta",\n  "observaciones": "Fiel a las fuentes.",\n'
                           '  "intentos_revision": 2\n}'),
    ("Listo para integrar", "JSON",
     "La salida es JSON estructurado, con metadatos de aprendizaje. Documentos y paquetes se guardan en "
     "OCI Object Storage.",
     "metadatos", '"metadatos": {\n  "tiempo_estimado_estudio_minutos": 5,\n  "conceptos_clave": [\n'
                  '    "VCN", "Subredes",\n    "Internet Gateway", "NAT Gateway"\n  ],\n  "prerrequisitos": [],\n'
                  '  "perfil_aplicado": "Principiante",\n  "formato_generado": "Flashcards",\n'
                  '  "nicho_sector": "General",\n  "nivel_detalle": "Didáctico"\n}'),
)
# Arquitectura de la demo (04-decisiones.md, 23-oct): app en Streamlit Community Cloud + OCI Object Storage (Always Free);
# LLM por la API de Gemini
COMPONENTES_VM = (("Interfaz", "Streamlit"), ("API", "FastAPI · /api/v1"), ("Agentes", "LangGraph · RAG"),
                  ("Datos de la app", "SQLite e índice vectorial"))
ALMACENAMIENTO = (("PDF", "Documentos que sube la institución"), ("JSON", "Paquetes de material aprobado"),
                  ("PRIV", "Bucket privado: sin acceso público"))
VENTAJAS_OCI = (("Sin costo de nube:", "todo cabe en la capa Always Free."),
                ("Privado por defecto:", "la app comprueba el bucket antes de guardar cada archivo."),
                ("Integrable:", "otros sistemas leen los paquetes JSON directamente."))
CIERRE_TITULO = "Aprender hoy, construir mañana."
CIERRE_TEXTO = "Entra con una cuenta de demostración y recorre la plataforma como estudiante o como administración."
SIN_CUENTAS_DEMO = "Pide tu usuario a quien administra la plataforma."
# Solo existen en modo mock (app/mocks/institucion/usuarios.json)
CUENTAS_DEMO = (
    ("Estudiante", "laura", "demo-estudiante"),
    ("Con contraseña temporal", "mateo", "temporal-123"),
    ("Administración", "admin", "demo-admin"),
)

# Colores que cambian con el tema y que van dentro de íconos (una imagen no lee las variables de CSS)
COLORES = {
    False: {"color_acento": "#205E58", "color_exito": "#166534"},
    True: {"color_acento": "#7DC1B0", "color_exito": "#86E0AC"},
}

_CHULO = ('<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{color}" '
          'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex: 0 0 20px; margin-top: 1px">'
          '<path d="M20 6 9 17l-5-5"></path></svg>')
_CHIP = ('<span style="font-size: 12px; font-weight: {peso}; padding: 3px 10px; border-radius: 999px; '
         'background: {fondo}; color: {color}">{texto}</span>')
_HOJAS = ('<svg aria-hidden="true" viewBox="0 0 64 64" style="width: 24px; height: 24px">'
          '<path d="M29 60C12 57 3 41 6 16c17 2 28 16 26 36-.3 3-1.3 6-3 8Z" fill="#A9CDBD"></path>'
          '<path d="M33 60c-5-22 3-44 25-54 8 25 2 47-22 54-1 .2-2 .2-3 0Z" fill="#F5F7F5"></path></svg>')


def _chips(nombre, minutos):
    perfiles = "".join(f'<span class="nm-perfil-nombre nm-perfil-nombre-{i}">{escape(p)}</span>'
                       for i, p in enumerate(PERFILES))
    return ('<div style="display: flex; flex-wrap: wrap; gap: 6px">'
            + _CHIP.format(peso=700, fondo="#205E58", color="#FFFFFF", texto=escape(nombre))
            + _CHIP.format(peso=600, fondo="#E7EEE8", color="#142E2A", texto=perfiles)
            + _CHIP.format(peso=600, fondo="#E7EEE8", color="#142E2A", texto=f"{minutos} min de estudio")
            + "</div>")


def _pestanas():
    return "".join(
        f'<input class="nm-oculto nm-f" type="radio" name="nm-formato" id="nm-f{i}">'
        f'<label class="nm-pestana nm-pestana-{i}" for="nm-f{i}">{escape(nombre)}<span class="nm-barra"></span></label>'
        for i, (nombre, _) in enumerate(FORMATOS))


def _cinta():
    elementos = ([("Formato", f) for f, _ in FORMATOS] + [("Perfil", p) for p in PERFILES]
                 + [("Sector", s) for s in SECTORES])
    piezas = "".join(
        '<span style="display: inline-flex; align-items: center; gap: 14px; padding: 0 22px; font-size: 16px; '
        'font-weight: 600; color: #C2D2CB; white-space: nowrap"><span style="font-size: 12px; color: #7DC1B0; '
        f'font-weight: 700; letter-spacing: .08em; text-transform: uppercase">{tipo}</span>{escape(texto)}</span>'
        for tipo, texto in elementos)
    # Dos copias seguidas: la animación corre la mitad del ancho y vuelve a empezar sin salto; la copia no se lee
    return f'<div style="display: flex">{piezas}</div><div aria-hidden="true" style="display: flex">{piezas}</div>'


def _pasos():
    return "".join(
        '<div class="nm-tarjeta" style="background: var(--nm-superficie); border: 1px solid var(--nm-borde); '
        'border-radius: 14px; padding: 28px">'
        f'<div aria-hidden="true" style="font-size: 56px; font-weight: 800; line-height: 1; color: var(--nm-acento)">'
        f'{numero:02d}</div>'
        f'<h3 style="margin-top: 18px; font-size: 22px; font-weight: 700">{numero}. {escape(nombre)}</h3>'
        f'<p style="margin-top: 8px; font-size: 16px; line-height: 1.5; color: var(--nm-texto2)">{escape(texto)}</p>'
        '</div>'
        for numero, (nombre, texto) in enumerate(PASOS, start=1))


def _agentes():
    piezas = []
    for i, (nombre, tarea) in enumerate(AGENTES):
        flecha = ('' if i == len(AGENTES) - 1 else
                  '<div aria-hidden="true" class="nm-conector" style="flex: 0 0 26px; position: relative; height: 8px">'
                  '<div style="position: absolute; left: 3px; right: 3px; top: 3px; height: 2px; background: #3A8277">'
                  '</div><span class="nm-flujo-punto" style="animation-duration: 1.2s"></span></div>')
        piezas.append(
            '<div class="nm-agente-caja" style="flex: 1 1 130px; display: flex; align-items: center; min-width: 0">'
            f'<div class="nm-agente nm-agente-{i}">'
            '<div class="nm-mono" style="width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; '
            f'justify-content: center; background: #A9CDBD; color: #142E2A; font-size: 15px; font-weight: 600">{i + 1:02d}</div>'
            f'<div style="font-size: 17px; font-weight: 700; margin-top: 12px">{escape(nombre)}</div>'
            f'<div style="font-size: 14px; line-height: 1.4; margin-top: 4px; color: #C2D2CB">{escape(tarea)}</div>'
            f'</div>{flecha}</div>')
    return "".join(piezas)


def _lista(elementos, color_chulo):
    chulo = _CHULO.format(color=color_chulo)
    return "".join(f'<li style="display: flex; gap: 10px; align-items: flex-start">{chulo}{escape(e)}</li>'
                   for e in elementos)


def _pilares():
    return "".join(
        f'<input class="nm-oculto nm-pi" type="radio" name="nm-pilar" id="nm-pi{i}"{" checked" if i == 0 else ""}>'
        f'<label class="nm-pilar" for="nm-pi{i}">'
        '<span style="display: flex; justify-content: space-between; align-items: center; gap: 12px; font-size: 19px; '
        f'font-weight: 700">{escape(nombre)}<span class="nm-mono" style="font-size: 13px; font-weight: 600; '
        f'color: var(--nm-acento)">{escape(clave)}</span></span>'
        f'<span class="nm-pilar-texto">{escape(texto)}</span></label>'
        for i, (nombre, clave, texto, _, _) in enumerate(POR_DENTRO))


def _codigos():
    return "".join(
        f'<pre class="nm-mono nm-codigo nm-codigo-{i}" style="margin: 0; padding: 22px 24px; font-size: 14px; '
        'line-height: 1.65; color: #EAF2EF; background: transparent; white-space: pre-wrap; min-height: 330px; '
        f'border: 0">{escape(codigo)}</pre>'
        for i, (_, _, _, _, codigo) in enumerate(POR_DENTRO))


def _archivos():
    return "".join(f'<span class="nm-archivo nm-archivo-{i}">{escape(archivo)}</span>'
                   for i, (_, _, _, archivo, _) in enumerate(POR_DENTRO))


def _componentes_vm():
    return "".join(
        '<div style="background: #1A3530; border: 1px solid #2E5A52; border-radius: 10px; padding: 14px">'
        f'<div style="font-size: 15px; font-weight: 700">{escape(nombre)}</div>'
        f'<div style="margin-top: 2px; font-size: 14px; color: #C2D2CB">{escape(detalle)}</div></div>'
        for nombre, detalle in COMPONENTES_VM)


def _almacenamiento():
    return "".join(
        '<li style="display: flex; gap: 10px; align-items: center; background: var(--nm-fondo); border-radius: 8px; '
        f'padding: 10px 12px"><span class="nm-mono" style="font-size: 12px; font-weight: 600; color: var(--nm-acento); '
        f'flex: 0 0 52px">{escape(tipo)}</span>{escape(texto)}</li>'
        for tipo, texto in ALMACENAMIENTO)


def _ventajas_oci(color_chulo):
    chulo = _CHULO.format(color=color_chulo)
    return "".join(
        '<div style="display: flex; gap: 12px; align-items: flex-start; font-size: 15px; line-height: 1.45">'
        f'{chulo}'
        f'<span><strong>{escape(titulo)}</strong> {escape(texto)}</span></div>'
        for titulo, texto in VENTAJAS_OCI)


_SVG = re.compile(r"<svg\b([^>]*)>(.*?)</svg>", re.S)
_ATRIBUTO = re.compile(r'([\w:-]+)="([^"]*)"')


def _svg_a_img(coincidencia):
    """st.html limpia el HTML y quita los <svg>; como <img> con el SVG en data: sí se conservan."""
    atributos = dict(_ATRIBUTO.findall(coincidencia.group(1)))
    estilo = atributos.pop("style", "")
    texto_alt = atributos.pop("aria-label", "")
    for quitar in ("role", "aria-hidden"):
        atributos.pop(quitar, None)
    ancho, alto = atributos.get("width"), atributos.get("height")
    medidas = (f"width: {ancho}px; " if ancho else "") + (f"height: {alto}px; " if alto else "")
    propios = " ".join(f'{nombre}="{valor}"' for nombre, valor in atributos.items())
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" {propios}>{coincidencia.group(2)}</svg>'
    datos = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (f'<img src="data:image/svg+xml;base64,{datos}" alt="{texto_alt}" '
            f'style="{medidas}flex-shrink: 0; {estilo}">')


def _sin_svg(html):
    return _SVG.sub(_svg_a_img, html)


def html_principal(tema_oscuro=False):
    """Todo lo que va antes del cierre: hero, cómo funciona, para quién, por dentro y OCI (con el CSS de la landing)."""
    colores = COLORES[tema_oscuro]
    titular = escape(TITULAR).replace(TITULAR_DESTACADO,
                                      f'<span style="color: #7DC1B0">{TITULAR_DESTACADO}</span>', 1)
    valores = {
        "clase_tema": "nm nm-oscuro" if tema_oscuro else "nm",
        "titular_html": titular,
        "explicacion": escape(EXPLICACION),
        "pestanas": _pestanas(),
        "cinta": _cinta(),
        "pasos": _pasos(),
        "agentes": _agentes(),
        "lista_institucion": _lista(INSTITUCION, colores["color_exito"]),
        "lista_estudiante": _lista(ESTUDIANTE, "#A9CDBD"),
        "pilares": _pilares(),
        "codigos": _codigos(),
        "archivos": _archivos(),
        "componentes_vm": _componentes_vm(),
        "almacenamiento": _almacenamiento(),
        "ventajas_oci": _ventajas_oci(colores["color_exito"]),
        **colores,
    }
    valores.update({f"chips_{i}": _chips(nombre, minutos) for i, (nombre, minutos) in enumerate(FORMATOS)})
    return _sin_svg(Template(PLANTILLA.read_text(encoding="utf-8")).substitute(valores))


def html_cuentas(es_mock):
    """Tarjeta de la derecha del cierre: las cuentas de demostración solo existen en modo mock."""
    if es_mock:
        filas = "".join(
            '<div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; '
            'padding: 14px 0; border-bottom: 1px solid #D6E2DC">'
            f'<span style="font-size: 16px; font-weight: 600">{escape(rol)}</span>'
            '<span class="nm-mono" style="font-size: 14px; background: #E7EEE8; padding: 5px 10px; border-radius: 6px">'
            f'{escape(usuario)} / {escape(contrasena)}</span></div>'
            for rol, usuario, contrasena in CUENTAS_DEMO)
        cuerpo = (f'<div style="margin-top: 14px; display: flex; flex-direction: column">{filas}</div>'
                  '<p style="margin-top: 14px; font-size: 14px; color: #4E625D">'
                  'Disponibles solo en el modo de demostración.</p>')
        titulo = "Cuentas de demostración"
    else:
        cuerpo = f'<p style="margin-top: 12px; font-size: 17px; line-height: 1.5">{escape(SIN_CUENTAS_DEMO)}</p>'
        titulo = "¿Cómo entro?"
    return ('<div class="nm" style="background: #FFFFFF; color: #142E2A; border-radius: 16px; padding: 28px">'
            '<div style="font-size: 13px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; '
            f'color: #205E58">{titulo}</div>{cuerpo}</div>')


def html_cierre():
    return ('<div class="nm" style="background: transparent; color: #FFFFFF">'
            '<h2 style="font-size: clamp(34px, 4vw, 52px); line-height: 1.05; font-weight: 800; letter-spacing: -.02em">'
            f'{escape(CIERRE_TITULO)}</h2>'
            '<p style="margin-top: 18px; font-size: 19px; line-height: 1.5; color: #EAF2EF; max-width: 520px">'
            f'{escape(CIERRE_TEXTO)}</p></div>')


def html_pie():
    return ('<footer class="nm" style="background: #102522; color: #C2D2CB">'
            '<div class="nm-ancho" style="padding-top: 32px; padding-bottom: 32px; display: flex; flex-wrap: wrap; '
            'justify-content: space-between; align-items: center; gap: 16px; font-size: 15px">'
            f'<div style="display: flex; align-items: center; gap: 10px; color: #EAF2EF; font-weight: 700">{_sin_svg(_HOJAS)}'
            'NuevaMente</div><div>Hackathon ONE G10 · Oracle Next Education y Alura · Equipo 30</div></div></footer>')


def mostrar():
    st.html(html_principal(tema_oscuro=st.context.theme.type == "dark"))
    with st.container(key="nm_cierre"):
        texto, cuentas = st.columns(2, gap="large", vertical_alignment="center")
        with texto:
            st.html(html_cierre())
            if st.button("Iniciar sesión", key="ir_acceso", type="primary"):
                ir_a("acceso")
        with cuentas:
            st.html(html_cuentas(sesion.cliente_de_sesion().es_mock))
    st.html(html_pie())
