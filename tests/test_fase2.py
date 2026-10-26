import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.append(str(RAIZ / "src"))

from chunk_embeddings import cargar_vectorstore, chunk_embeddings  # noqa: E402
from ingestion import process_document  # noqa: E402

CARPETA_DATOS = RAIZ / "data"
EXTENSIONES = {".pdf", ".md", ".txt"}

# Preguntas con respuesta conocida: (pregunta, archivo del que debe salir el fragmento).
# Solo se revisan las de los archivos que estén en data/.
CONSULTAS_ESPERADAS = [
    (
        "¿Cuál es el límite por noche para el alojamiento en hoteles?",
        "politica_reembolsos_viajes_gastos.pdf",
    ),
    (
        "¿Qué componente permite que una subred privada acceda a internet "
        "sin recibir conexiones entrantes?",
        "arquitectura_redes_vcn_oci.md",
    ),
]


def fallar(mensaje):
    """Muestra el error y termina con código 1 para que el fallo no pase desapercibido."""
    print(f"\n❌ FALLO: {mensaje}")
    sys.exit(1)


def main():
    archivos = sorted(
        p for p in CARPETA_DATOS.iterdir() if p.suffix.lower() in EXTENSIONES
    )
    if not archivos:
        fallar(f"no hay archivos de prueba en {CARPETA_DATOS}")

    print(f"Archivos a procesar: {[a.name for a in archivos]}\n")

    print("1. Ingesta de documentos...")
    docs = []
    for archivo in archivos:
        try:
            docs_archivo = process_document(str(archivo))
        except Exception as e:
            fallar(f"no se pudo procesar {archivo.name}: {e}")
        print(f"   - {archivo.name}: {len(docs_archivo)} páginas/fragmentos base.")
        docs.extend(docs_archivo)

    nombres = {a.name for a in archivos}
    consultas = [(p, f) for p, f in CONSULTAS_ESPERADAS if f in nombres]

    # Carpeta temporal: el test no pisa el vectorstore/ real y se borra al terminar.
    with tempfile.TemporaryDirectory() as carpeta_temporal:
        print(f"\n2. Chunks, embeddings e índice FAISS ({len(docs)} elementos base)...")
        try:
            chunk_embeddings(docs, ruta=carpeta_temporal)
            vectorstore = cargar_vectorstore(carpeta_temporal)
        except Exception as e:
            fallar(f"error al generar o cargar el índice: {e}")
        print("   ✅ Índice generado y cargado.")

        print("\n3. Recuperación con preguntas de respuesta conocida...")
        if not consultas:
            print("   ⚠️  Ningún archivo de data/ tiene preguntas definidas; se omite.")
        for pregunta, esperado in consultas:
            resultados = vectorstore.similarity_search(pregunta, k=1)
            if not resultados:
                fallar(f"la búsqueda no devolvió nada para: {pregunta}")
            fuente = Path(resultados[0].metadata.get("source", "")).name
            if fuente != esperado:
                fallar(f"'{pregunta}' trajo un fragmento de '{fuente}', se esperaba '{esperado}'")
            print(f"   ✅ {pregunta} -> {fuente}")

    print("\n✅ Fase 2 OK: ingesta, embeddings, índice y recuperación funcionan.")


if __name__ == "__main__":
    main()
