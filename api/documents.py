"""Extracción de archivos recibidos: sin rutas suministradas por el cliente."""

from io import BytesIO
from pathlib import PurePosixPath

from langchain_core.documents import Document
from pypdf import PdfReader

from ingestion import clean_and_normalize_text
from api.contracts import MAX_DOCUMENT_CHARACTERS, MAX_PDF_PAGES, MAX_UPLOAD_BYTES
from api.errors import ApiError

MIME_TYPES = {"pdf": "application/pdf", "md": "text/markdown", "txt": "text/plain"}


def extract_document(filename: str, raw: bytes) -> tuple[str, str, list[Document]]:
    # Se usa solo como etiqueta; los originales se guardan como BLOB en SQLite.
    filename = PurePosixPath(filename.replace("\\", "/")).name
    if not filename or len(filename) > 255 or any(ord(char) < 32 for char in filename):
        raise ApiError(422, "NOMBRE_INVALIDO", "El archivo debe tener un nombre válido de hasta 255 caracteres.")
    extension = PurePosixPath(filename).suffix.lower().lstrip(".")
    if extension not in MIME_TYPES:
        raise ApiError(415, "FORMATO_NO_SOPORTADO", "Sube un archivo PDF, Markdown (.md) o TXT.")
    if not raw:
        raise ApiError(422, "DOCUMENTO_VACIO", "El archivo está vacío.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "DOCUMENTO_DEMASIADO_GRANDE", "El archivo supera el límite de 10 MiB.")

    if extension == "pdf":
        try:
            reader = PdfReader(BytesIO(raw))
            if reader.is_encrypted:
                raise ApiError(422, "PDF_PROTEGIDO", "Sube un PDF sin contraseña.")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ApiError(413, "DEMASIADAS_PAGINAS", "El PDF supera el límite de 100 páginas.")
            # Extracción incremental para limitar el texto retenido en memoria.
            documents = []
            total = 0
            for number, page in enumerate(reader.pages, 1):
                text = clean_and_normalize_text(page.extract_text() or "")
                total += len(text)
                if total > MAX_DOCUMENT_CHARACTERS:
                    raise ApiError(413, "TEXTO_DEMASIADO_LARGO", "El documento supera 250000 caracteres extraídos.")
                if len(text) > 10:
                    documents.append(Document(page_content=text, metadata={"source": filename, "page": number}))
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(422, "PDF_INVALIDO", "No se pudo leer el PDF. Comprueba que sea un archivo válido.") from exc
    else:
        try:
            text = clean_and_normalize_text(raw.decode("utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise ApiError(422, "CODIFICACION_INVALIDA", "Guarda el archivo MD/TXT con codificación UTF-8.") from exc
        if len(text) > MAX_DOCUMENT_CHARACTERS:
            raise ApiError(413, "TEXTO_DEMASIADO_LARGO", "El documento supera 250000 caracteres extraídos.")
        documents = [Document(page_content=text, metadata={"source": filename})] if len(text) > 10 else []

    if not documents:
        raise ApiError(422, "DOCUMENTO_SIN_TEXTO", "No se encontró texto utilizable. Los PDF escaneados necesitan OCR previo.")
    return filename, extension, documents
