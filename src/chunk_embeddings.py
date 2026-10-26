from array import array
from collections import OrderedDict
import os
import threading

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import SecretStr

from the_keys import GEMINI_API_KEY
from the_models import GEMINI_EMBEDDINGS

# Carpeta donde se guarda el índice FAISS (relativa a donde se ejecuta el script).
RUTA_VECTORSTORE = "vectorstore"

# Vectores ya calculados, por (modelo, texto del fragmento). Viven mientras dure el proceso.
# Tope: con 3072 dimensiones, cada vector ocupa ~24 KB → 5000 vectores ≈ 120 MB.
MAXIMO_VECTORES_EN_MEMORIA = 5000
_VECTORES = OrderedDict()
_CANDADO = threading.Lock()


class EmbeddingsConMemoria(Embeddings):
    """Envuelve el modelo y recuerda los vectores de los fragmentos que ya calculó.

    Cada generación arma el índice del tema desde cero; sin esta memoria, todos sus fragmentos
    se vuelven a pedir a Gemini y se agota rápido el límite por minuto. Los vectores son los mismos
    que devuelve el modelo (se guardan en doble precisión, sin redondeo). Las consultas no se guardan.
    """

    def __init__(self, modelo):
        self._modelo = modelo

    def embed_documents(self, texts):
        with _CANDADO:
            faltan = [t for t in dict.fromkeys(texts) if (GEMINI_EMBEDDINGS, t) not in _VECTORES]
        nuevos = dict(zip(faltan, self._modelo.embed_documents(faltan))) if faltan else {}
        with _CANDADO:
            resultado = []
            for texto in texts:
                clave = (GEMINI_EMBEDDINGS, texto)
                if texto in nuevos:
                    _VECTORES[clave] = array("d", nuevos[texto])
                    resultado.append(list(nuevos[texto]))
                else:
                    _VECTORES.move_to_end(clave)
                    resultado.append(list(_VECTORES[clave]))
            while len(_VECTORES) > MAXIMO_VECTORES_EN_MEMORIA:
                _VECTORES.popitem(last=False)
        return resultado

    def embed_query(self, text):
        return self._modelo.embed_query(text)


def crear_modelo_embeddings():
    """Modelo de embeddings compartido: crear y cargar el índice deben usar el mismo."""
    return EmbeddingsConMemoria(GoogleGenerativeAIEmbeddings(
        model=GEMINI_EMBEDDINGS,
        api_key=SecretStr(GEMINI_API_KEY) if GEMINI_API_KEY else None,
    ))


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
