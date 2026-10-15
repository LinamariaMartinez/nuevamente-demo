import os

from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import SecretStr

from the_keys import GEMINI_API_KEY
from the_models import GEMINI_EMBEDDINGS

# Carpeta donde se guarda el índice FAISS (relativa a donde se ejecuta el script).
RUTA_VECTORSTORE = "vectorstore"


def crear_modelo_embeddings():
    """Modelo de embeddings compartido: crear y cargar el índice deben usar el mismo."""
    return GoogleGenerativeAIEmbeddings(
        model=GEMINI_EMBEDDINGS,
        api_key=SecretStr(GEMINI_API_KEY) if GEMINI_API_KEY else None,
    )


def crear_vectorstore(docs, chunk_size=1000, chunk_overlap=100):
    """Construye un índice aislado en memoria para una generación."""
    if not docs:
        raise ValueError("No hay documentos para procesar.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    docs_splits = splitter.split_documents(docs)

    return FAISS.from_documents(docs_splits, crear_modelo_embeddings())


def chunk_embeddings(docs, chunk_size=1000, chunk_overlap=100, ruta=RUTA_VECTORSTORE):
    """Construye y persiste el índice global usado por el CLI."""
    vectorstore = crear_vectorstore(docs, chunk_size, chunk_overlap)
    vectorstore.save_local(ruta)

    return vectorstore


def cargar_vectorstore(ruta=RUTA_VECTORSTORE):
    """Carga el índice FAISS guardado para consultarlo (ej. desde el agente investigador)."""
    if not os.path.isdir(ruta):
        raise FileNotFoundError(
            f"No existe el índice en '{ruta}'. Genéralo primero con chunk_embeddings()."
        )

    # allow_dangerous_deserialization: FAISS guarda metadatos con pickle.
    # Es seguro solo porque el índice lo generamos nosotros; nunca cargar uno de terceros.
    return FAISS.load_local(
        ruta, crear_modelo_embeddings(), allow_dangerous_deserialization=True
    )
