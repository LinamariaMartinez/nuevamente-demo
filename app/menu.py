"""Menú por rol (spec §3). Una pantalla que no está lista (`lista=False`) no aparece."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Entrada:
    nombre: str  # clave interna y url_path
    titulo: str
    icono: str
    seccion: str = ""  # el admin agrupa su menú por secciones; el estudiante no
    lista: bool = True


MENU = {
    "estudiante": (
        Entrada("mis-temas", "Mis temas", ":material/menu_book:"),
        Entrada("evaluaciones", "Evaluaciones", ":material/task_alt:", lista=False),  # pieza 2
    ),
    "admin": (
        Entrada("documentos", "Documentos", ":material/description:", "Contenido"),
        Entrada("temas", "Temas", ":material/topic:", "Contenido"),
        Entrada("examenes", "Exámenes", ":material/quiz:", "Contenido", lista=False),  # pieza 2
        Entrada("revision", "Material en revisión", ":material/rate_review:", "Contenido"),
        Entrada("usuarios", "Usuarios", ":material/group:", "Personas", lista=False),  # pieza 3
        Entrada("progreso", "Progreso", ":material/monitoring:", "Personas", lista=False),  # pieza 3
        # Sin uso por ahora: el sector se elige en cada tema (decisión del 19-oct)
        Entrada("configuracion", "Configuración", ":material/settings:", "Ajustes", lista=False),
    ),
}


def entradas(rol):
    return [entrada for entrada in MENU[rol] if entrada.lista]
