import os
import re

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document


def clean_and_normalize_text(text: str) -> str:
    """Limpia y normaliza el texto extraído eliminando artefactos y espacios extra."""
    text = re.sub(r"[ \t]+", " ", text)  # Eliminar múltiples espacios/tabs
    text = re.sub(r"\n{3,}", "\n\n", text)  # Reducir saltos de línea continuos
    text = text.replace("\x00", "")  # Eliminar caracteres nulos (común en PDFs)
    text = text.replace("“", '"').replace("”", '"').replace("–", "-")
    return text.strip()


def process_document(file_path: str) -> list[Document]:
    """Carga documentos según su extensión y extrae el texto limpio."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"El archivo {file_path} no existe.")

    ext = os.path.splitext(file_path)[-1].lower()

    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".md":
        loader = UnstructuredMarkdownLoader(file_path)
    elif ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")
    else:
        raise ValueError(f"Formato no soportado: {ext}")

    raw_documents = loader.load()
    cleaned_documents = []

    for doc in raw_documents:
        cleaned_text = clean_and_normalize_text(doc.page_content)
        # Filtrar páginas o fragmentos vacíos tras la limpieza
        if len(cleaned_text) > 10:
            doc.page_content = cleaned_text
            cleaned_documents.append(doc)

    return cleaned_documents


if __name__ == "__main__":
    # Ruta relativa considerando que ejecutamos desde la raíz del proyecto
    sample_file = "data/documento_prueba.md"

    try:
        docs = process_document(sample_file)
        print(f"Éxito: Se procesaron {len(docs)} páginas/fragmentos.")
        if docs:
            print("\n--- Muestra del texto limpio ---")
            print(docs[0].page_content[:300])
    except (OSError, ValueError) as e:
        print(f"Error de ejecución: {e}")
