"""Reintentos acotados; no confundir errores de API con revisiones del contenido."""
import random
import time

from google.genai.errors import APIError


def invoke_with_retry(chain, inputs, max_attempts=4):
    for attempt in range(max_attempts):
        try:
            return chain.invoke(inputs)
        except APIError as error:
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == max_attempts - 1:
                raise
            time.sleep(2 ** attempt + random.uniform(0, 0.25))
    raise RuntimeError("No se obtuvo una respuesta del proveedor")
