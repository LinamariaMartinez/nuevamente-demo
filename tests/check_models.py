import sys
from pathlib import Path

from google import genai

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from the_keys import GEMINI_API_KEY  # noqa: E402
from the_models import GEMINI_EMBEDDINGS, GEMINI_GENERACION, GEMINI_LIGERO  # noqa: E402


def sin_prefijo(nombre):
    """La API devuelve 'models/xxx'; en the_models.py algunos van sin el prefijo."""
    return nombre.removeprefix("models/")


def main():
    if not GEMINI_API_KEY:
        print("Error: no se encontró GEMINI_API_KEY en el archivo .env")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)

    print("Conectando con Google AI...")
    try:
        modelos = {
            sin_prefijo(m.name): (m.supported_actions or []) for m in client.models.list()
        }
    except Exception as e:
        print(f"Error al conectar con la API: {e}")
        sys.exit(1)

    print("\nModelos de embeddings disponibles para tu API key:")
    for nombre, acciones in sorted(modelos.items()):
        if "embedContent" in acciones:
            print(f"   - {nombre}")

    print("\nModelos configurados en the_models.py:")
    faltantes = 0
    for constante, nombre in [
        ("GEMINI_GENERACION", GEMINI_GENERACION),
        ("GEMINI_LIGERO", GEMINI_LIGERO),
        ("GEMINI_EMBEDDINGS", GEMINI_EMBEDDINGS),
    ]:
        if sin_prefijo(nombre) in modelos:
            print(f"   ✅ {constante} = {nombre}")
        else:
            print(f"   ❌ {constante} = {nombre} (no disponible para tu API key)")
            faltantes += 1

    if faltantes:
        sys.exit(1)


if __name__ == "__main__":
    main()
