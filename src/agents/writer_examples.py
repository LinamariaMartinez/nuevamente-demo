"""Ejemplos ficticios de estilo; nunca son fuentes para la consulta real."""
import unicodedata


EXAMPLES = (
    (
        "El sistema Luma guarda una copia al pulsar Guardar. No guarda automáticamente.",
        "¿Cómo se conserva el trabajo en Luma?",
        {
            "principiante": "Para conservar tu trabajo, pulsa Guardar. Luma crea una copia cuando lo haces; no lo hace por sí solo.",
            "intermedio": "Luma requiere un guardado manual: pulsar Guardar crea una copia. No dispone de guardado automático.",
            "avanzado": "La persistencia descrita es explícita: Guardar crea una copia. La fuente descarta el guardado automático, pero no especifica versionado ni recuperación.",
            "general": "Pulsa Guardar para crear una copia del trabajo. El sistema no guarda automáticamente.",
        },
    ),
    (
        "El sensor Nara muestra una luz azul mientras registra datos. La guía no indica su autonomía.",
        "¿Qué indica la luz azul y cuánto dura la batería?",
        {
            "principiante": "La luz azul significa que el sensor está registrando datos. El texto no dice cuánto dura la batería, así que no podemos dar una duración.",
            "intermedio": "El indicador azul señala que hay un registro de datos en curso. La autonomía no está documentada en la fuente disponible.",
            "avanzado": "La señal azul identifica el estado de registro. No hay datos de autonomía en la fuente; no se puede inferir una duración de batería a partir de ese indicador.",
            "general": "La luz azul indica que se están registrando datos. La fuente no informa cuánto dura la batería.",
        },
    ),
)


def profile_examples(profile: str) -> list[tuple[str, str]]:
    """Dos pares entrada/salida por nivel; perfiles libres usan estilo general.

    La petición original del usuario se conserva en el prompt principal.
    No se intenta deducir nivel a partir de profesiones ni de textos ambiguos.
    """
    normalized = unicodedata.normalize("NFKD", profile.strip().casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    level = normalized if normalized in {"principiante", "intermedio", "avanzado"} else "general"
    messages = []
    for context, query, answers in EXAMPLES:
        messages.extend([
            ("human", f"EJEMPLO FICTICIO DE ESTILO\nPerfil: {level}\nFormato: Resumen\nFuente del ejemplo: {context}\nPregunta: {query}"),
            ("ai", answers[level]),
        ])
    return messages
