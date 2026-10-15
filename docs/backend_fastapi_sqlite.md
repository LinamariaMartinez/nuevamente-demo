# F06: salida estructurada, FastAPI y SQLite

Fecha: 15 de octubre de 2026. Repositorio: G-10-Latam-equipo30. Rama: Feature/F06-Output-Estructurado.

## Requisitos y alcance acordado

Se revisó el PDF de siete páginas del proyecto NuevaMente, recibido como `8ff50960-0506-45ed-ad16-556e98058efc.pdf`. Las páginas 3–5 exigen validación de entradas/salidas, adaptación mediante RAG, una API o interfaz y un paquete JSON con metadatos, contenido y evaluación. La nueva instrucción limita los perfiles a Principiante, Intermedio y Avanzado e incorpora SQLite y FastAPI.

El alcance confirmado es **documentos, generación e historial**, sin login ni roles. La tabla del frontend asigna rutas y lógica HTTP a `api/`, modelos compartidos a `src/contrato.py` y comunicación HTTP a `app/cliente_api.py`. Los dos últimos archivos no existen en esta rama y la tabla no especifica rutas ni campos. Por eso la API ofrece una propuesta documentada, no una afirmación de compatibilidad ya verificada. No se crea ni modifica el contrato compartido del equipo sin tener su contenido.

OCI continúa siendo un requisito del proyecto completo descrito en el PDF. Esta entrega persiste localmente en SQLite y no informa una subida OCI ficticia.

## Adaptación al trabajo del equipo

La rama ya contenía ejemplos de estilo por perfil, reintentos acotados y un revisor de tres dimensiones. Se preservan:

- Los ejemplos ficticios de `writer_examples.py` y la separación entre ejemplos y fuentes reales.
- `invoke_with_retry()` y sus cuatro intentos para errores transitorios del proveedor.
- Los tres umbrales de aprobación: fidelidad 0.80, pedagogía 0.75, formato 0.75.
- El límite de tres revisiones del contenido, independiente de los reintentos HTTP.
- `approved`, `review_status`, `requires_admin_review` y la regla de que `final_content` solo existe al aprobar.
- Las salidas tempranas sin llamadas LLM para fuente o borrador vacíos.

Se añade un timeout de 60 segundos por llamada del redactor/revisor y se deshabilitan los reintentos internos del SDK para evitar multiplicarlos por los del helper. Esto no es un límite total del pipeline: incluye embeddings, revisiones y reintentos.

## Contrato educativo

`src/schemas.py` define modelos estrictos para solicitudes, borradores, revisión y respuesta final. El redactor recibe el esquema correspondiente al formato mediante `method="json_schema"`. El revisor conserva su esquema con los tres puntajes y la aprobación se recalcula en código.

La respuesta mantiene cuatro campos superiores:

- `status`: exito o requiere_revision.
- `metadatos`: perfil_aplicado, formato_generado, tiempo_estimado_estudio_minutos, conceptos_clave, prerrequisitos, nicho_sector y nivel_detalle.
- `contenido_adaptado`: titulo, introduccion_contextualizada e items tipados.
- `evaluacion_calidad`: anclaje_fuente_score, claridad_pedagogica, observaciones e intentos_revision; además, calidad_pedagogica_score y cumplimiento_formato_score para conservar las métricas de esta rama.

`claridad_pedagogica` se deriva del puntaje pedagógico: Alta desde 0.75, Media desde 0.50, Baja por debajo. El estado de éxito exige los tres umbrales; no basta con fidelidad alta.

El nodo final expone `final_response` como diccionario y `final_json` como texto. `final_content` conserva su significado anterior: borrador aprobado, o cadena vacía si no se aprobó. El borrador ahora es JSON serializado, por lo que un consumidor antiguo que esperaba prosa debe adaptarse.

## Persistencia e aislamiento

SQLite guarda dos tablas:

| Tabla | Datos |
| --- | --- |
| documentos | ID, título, nombre, extensión, tamaño, fecha UTC, original BLOB y páginas/texto extraído en JSON. |
| contenidos | ID, documento asociado, tema, perfil, formato, estado, score, fecha UTC, solicitud y respuesta completas en JSON. |

Las escrituras se realizan con parámetros SQL y transacciones cortas. Cada operación abre y cierra su conexión; se activan claves foráneas, modo WAL y espera de bloqueo de 15 segundos. El esquema tiene `user_version=1`; una versión futura no compatible provoca un fallo explícito de inicio, sin sobrescribir datos.

La generación consulta solo las páginas del ID seleccionado. Construye un FAISS en memoria, recupera contexto y ejecuta el grafo. No utiliza ni modifica el índice global del CLI. Como no hay caché de embeddings en esta entrega, se recalculan por generación.

Los documentos se guardan antes de generar. Un error del proveedor deja el documento disponible, pero no crea contenido. Solo se confirma HTTP 201 después de guardar correctamente el JSON validado. Los resultados pendientes de revisión también se almacenan.

## Cómo lo consume Streamlit

El flujo esperado dentro del cliente HTTP del frontend es:

1. Obtener `GET /api/v1/catalogos` para poblar perfiles y formatos.
2. Subir un archivo a `POST /api/v1/documentos`, campo multipart `archivo`, o enviar texto a `POST /api/v1/documentos/texto`.
3. Leer el ID del documento y enviar la solicitud a `POST /api/v1/contenidos`.
4. Leer el JSON educativo directamente del cuerpo y guardar la cabecera `X-Contenido-ID`.
5. Consultar `GET /api/v1/contenidos` para mostrar historial. Usar `status=requiere_revision` para localizar contenido pendiente.
6. Recuperar el paquete por ID o descargarlo desde `/api/v1/contenidos/{id}/descarga`.

El mapa completo está en el [README](../README.md) y en `/docs`. Las cabeceras X-Contenido-ID y Location evitan agregar identificadores de persistencia al cuerpo educativo. Los perfiles de aprendizaje no son roles de autenticación.

Ejemplo de consumo Python, para adaptar en el cliente del frontend cuando el equipo acuerde el contrato:

```python
import requests

base = "http://127.0.0.1:8000"
with open("data/arquitectura_redes_vcn_oci.md", "rb") as archivo:
    subida = requests.post(base + "/api/v1/documentos", files={"archivo": archivo}, timeout=30)
subida.raise_for_status()
respuesta = requests.post(base + "/api/v1/contenidos", json={
    "documento_id": subida.json()["id"],
    "tema": "¿Qué es una VCN?",
    "perfil_destinatario": "Intermedio",
    "formato_salida": "Flashcards",
}, timeout=300)
respuesta.raise_for_status()
paquete = respuesta.json()
contenido_id = respuesta.headers["X-Contenido-ID"]
```

Esta muestra es documentación de HTTP: no implementa pantallas, sesión, mocks ni archivos del frontend. Streamlit realiza las llamadas desde su servidor; CORS solo es relevante si el navegador llama directamente a la API. Los orígenes opcionales se configuran en NUEVAMENTE_CORS_ORIGINS.

## Revisión y uso manual

La [guía de uso de la API](uso_api.md) documenta el flujo completo en Swagger y PowerShell. Se comprobó la API con un servidor local, carga del Markdown incluido, recuperación de su texto y descarga del archivo original.

Antes de retirar las pruebas nuevas, la suite ejecutada pasó con 119 casos y 12 subpruebas, usando modelos simulados. Este resultado es una verificación de desarrollo, no una suite F06 que se entregue ahora: por instrucción del usuario, se eliminaron los archivos nuevos de pruebas, su script HTTP y la configuración añadida para ejecutarlos. Se conservan las pruebas del equipo, adaptadas al contrato estructurado. Por petición posterior del usuario se eliminó hito3-tests.yml, por lo que ese workflow ya no ejecuta las pruebas automáticamente en GitHub Actions.

La comprobación de dependencias con `pip check` no encontró incompatibilidades. No se ejecutó generación real con Gemini en este repositorio: falta configurar su propia clave en `.env`.

## Archivos principales

| Archivo | Cambio |
| --- | --- |
| src/schemas.py | Perfiles cerrados, cinco esquemas pedagógicos y JSON de salida. |
| src/agents/writer.py | Structured Outputs conservando ejemplos y reintentos. |
| src/agents/reviewer.py | Validación estricta y método JSON Schema, conservando las tres dimensiones. |
| src/review_policy.py | Centraliza los tres umbrales y su comprobación. |
| src/output.py, src/graph.py, src/state.py | Ensamblan y transportan la salida JSON sin alterar la aprobación existente. |
| src/agents/researcher.py, src/chunk_embeddings.py | RAG aislado por documento para peticiones HTTP. |
| src/generation.py, src/errors.py | Servicio de generación y errores de configuración/contexto. |
| src/the_keys.py | Carga el .env de este repositorio, independientemente del directorio de ejecución. |
| src/generate.py | CLI de JSON para el índice global. |
| api/main.py, api/contracts.py | Endpoints, validaciones, OpenAPI, cabeceras y errores. |
| api/database.py, api/documents.py, api/errors.py | SQLite, extracción segura desde bytes y errores HTTP. |
| tests/test_review_flow.py, tests/test_writer_prompt.py, tests/test_fase3.py, tests/validate_live_review.py | Ajustes de compatibilidad en las pruebas ya existentes del equipo. |
| requirements.txt, .env.example, .gitignore | Dependencias, configuración y exclusión de datos locales. |
| README.md, guiapersonal.md, docs/uso_api.md | Inicio, explicación personal y consumo HTTP paso a paso. |

Los modelos Gemini configurados, el frontend y los documentos fuente no se cambian.
