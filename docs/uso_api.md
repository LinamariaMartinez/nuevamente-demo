# Cómo usar la API de NuevaMente

Esta guía corresponde a **G-10-Latam-equipo30**, rama **Feature/F06-Output-Estructurado**. La URL local por defecto es `http://127.0.0.1:8000`.

## 1. Preparar e iniciar el backend

Abre una terminal PowerShell en la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edita `.env` y sustituye `tu_clave_aqui` por tu clave en `GEMINI_API_KEY`. El backend lee el archivo de este repositorio. La clave se queda en el backend.

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Mantén esa terminal abierta. SQLite se crea automáticamente en `storage/nuevamente.sqlite3`; puedes cambiar la ruta con `NUEVAMENTE_DB_PATH`. No necesitas instalar un servidor de base de datos ni ejecutar `src/main.py` para usar la API. Ctrl+C detiene el servidor.

Puedes cargar y consultar documentos sin clave; **generar contenido sí requiere Gemini**. El contenido guardado se puede consultar sin volver a llamar al modelo.

## 2. Usarlo desde Swagger

Abre **http://127.0.0.1:8000/docs**. En cada operación pulsa **Try it out** y luego **Execute**:

1. `GET /health`: debe responder `{"status":"ok","base_datos":"sqlite"}`.
2. `GET /api/v1/catalogos`: muestra los perfiles, formatos y límites aceptados.
3. `POST /api/v1/documentos`: selecciona un archivo PDF, MD o TXT en `archivo`. `documento_titulo` es opcional; si no lo necesitas, no envíes un valor vacío. Copia el `id` del documento creado.
4. `POST /api/v1/contenidos`: completa el cuerpo de abajo con ese ID. Espera a que terminen recuperación, redacción y revisión.
5. Lee `status` y los cuatro bloques del resultado. La cabecera `X-Contenido-ID` identifica el contenido creado.
6. `GET /api/v1/contenidos`: muestra el historial y sus IDs. Recupera el paquete completo por ID o descárgalo con `GET /api/v1/contenidos/{contenido_id}/descarga`.

Cuerpo de generación; reemplaza el ID de ejemplo por el recibido al cargar:

```json
{
  "documento_id": "REEMPLAZAR_CON_EL_ID_RECIBIDO",
  "tema": "¿Qué es una VCN y cuáles son sus componentes?",
  "perfil_destinatario": "Intermedio",
  "formato_salida": "Flashcards",
  "nicho_sector": "General",
  "nivel_detalle": "Didáctico"
}
```

Campos obligatorios: `documento_id`, `tema`, `perfil_destinatario` y `formato_salida`. Los otros dos toman los valores mostrados si se omiten. No se aceptan campos adicionales.

- Perfiles exactos: **Principiante**, **Intermedio**, **Avanzado**.
- Formatos exactos: **Flashcards**, **Resumen**, **Quiz**, **Tutorial**, **Guion**.
- IDs: 32 caracteres hexadecimales generados por el servidor.

## 3. Ejemplo completo desde PowerShell

Con el servidor iniciado, abre una segunda terminal en el repositorio. Estos comandos cargan el Markdown incluido, generan contenido y consultan el resultado. La generación consume la API de Gemini.

```powershell
$base = "http://127.0.0.1:8000"

# Comprobar servicio y opciones disponibles.
Invoke-RestMethod "$base/health"
Invoke-RestMethod "$base/api/v1/catalogos"

# Cargar un archivo. Es multipart: el campo se llama archivo.
$documento = curl.exe --silent --show-error --fail-with-body -X POST "$base/api/v1/documentos" -F "archivo=@data/arquitectura_redes_vcn_oci.md" | ConvertFrom-Json
$documento.id

# Consultar los documentos y el texto extraído.
Invoke-RestMethod "$base/api/v1/documentos?limit=20&offset=0"
Invoke-RestMethod "$base/api/v1/documentos/$($documento.id)"

# Generar contenido para ese documento.
$solicitud = @{
    documento_id = $documento.id
    tema = "¿Qué es una VCN y cuáles son sus componentes?"
    perfil_destinatario = "Intermedio"
    formato_salida = "Flashcards"
    nicho_sector = "General"
    nivel_detalle = "Didáctico"
} | ConvertTo-Json

$respuesta = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/api/v1/contenidos" -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($solicitud)) -TimeoutSec 300
$paquete = $respuesta.Content | ConvertFrom-Json
$contenidoId = $respuesta.Headers["X-Contenido-ID"]
$paquete | ConvertTo-Json -Depth 20

# Consultar el paquete guardado y el historial.
Invoke-RestMethod "$base/api/v1/contenidos/$contenidoId"
Invoke-RestMethod "$base/api/v1/contenidos?perfil=Intermedio&limit=20&offset=0"
Invoke-RestMethod "$base/api/v1/contenidos?status=requiere_revision"

# Descargar el JSON y el documento original.
New-Item -ItemType Directory -Force -Path output | Out-Null
Invoke-WebRequest -UseBasicParsing "$base/api/v1/contenidos/$contenidoId/descarga" -OutFile "output/contenido.json"
Invoke-WebRequest -UseBasicParsing "$base/api/v1/documentos/$($documento.id)/original" -OutFile "output/documento-original.md"
```

Si prefieres enviar texto en lugar de un archivo, usa este endpoint; los pasos de generación son los mismos:

```powershell
$texto = @{
    documento_titulo = "Introducción a VCN"
    documento_contenido = "Una VCN es una red privada y personalizable en Oracle Cloud Infrastructure."
} | ConvertTo-Json

$documento = Invoke-RestMethod -Method Post -Uri "$base/api/v1/documentos/texto" -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($texto))
$documento.id
```

Cada POST crea un registro nuevo. La generación es síncrona y su duración depende del proveedor, los embeddings y las revisiones. Si vence el timeout del cliente, consulta el historial antes de repetir el POST: el servidor puede seguir trabajando.

## 4. Qué recibe el frontend

La creación devuelve HTTP **201** y directamente un objeto con:

| Campo | Significado |
| --- | --- |
| `status` | `exito` o `requiere_revision`. |
| `metadatos` | Perfil, formato, sector, detalle, minutos estimados de estudio, conceptos clave y prerrequisitos. |
| `contenido_adaptado` | Título, introducción e items según el formato. |
| `evaluacion_calidad` | Puntajes de fidelidad, pedagogía y formato; claridad, observaciones e intentos de revisión. |

Ejemplo completo: [respuesta_flashcards.json](../examples/respuesta_flashcards.json). Es ilustrativo.

HTTP 201 confirma que el resultado se guardó. **No equivale a aprobación educativa**: revisa `status`. La aprobación exige fidelidad >= 0.80, pedagogía >= 0.75 y formato >= 0.75. Si no se alcanzan después de tres revisiones, se guarda como `requiere_revision`.

El cuerpo mantiene el paquete educativo. Sus datos de persistencia se obtienen de:

- `X-Contenido-ID`: ID del contenido creado.
- `Location`: ruta para recuperarlo.
- Historial: ID, documento asociado, tema, título, perfil, formato, estado, score de fidelidad y fecha UTC.

Los listados devuelven `items`, `total`, `limit` y `offset`. `limit` permite 1–100 y vale 20 por defecto; `offset` empieza en 0. El historial acepta filtros opcionales `documento_id`, `perfil` y `status`.

## 5. Mapa de rutas

| Método | Ruta | Entrada / respuesta |
| --- | --- | --- |
| GET | `/health` | Estado de API y SQLite. |
| GET | `/api/v1/catalogos` | Perfiles, formatos, extensiones y límites. |
| POST | `/api/v1/documentos` | Multipart: `archivo`, título opcional. Devuelve metadatos e ID del documento (201). |
| POST | `/api/v1/documentos/texto` | JSON: `documento_titulo`, `documento_contenido`. Devuelve metadatos e ID (201). |
| GET | `/api/v1/documentos` | Lista paginada de documentos. |
| GET | `/api/v1/documentos/{documento_id}` | Metadatos y `documento_contenido` extraído. |
| GET | `/api/v1/documentos/{documento_id}/original` | Bytes del archivo original como adjunto. |
| POST | `/api/v1/contenidos` | Solicitud de generación; devuelve paquete educativo (201). |
| GET | `/api/v1/contenidos` | Historial paginado y filtrable. |
| GET | `/api/v1/contenidos/{contenido_id}` | Paquete educativo completo. |
| GET | `/api/v1/contenidos/{contenido_id}/descarga` | El paquete como archivo JSON adjunto. |

El esquema legible por herramientas está en **http://127.0.0.1:8000/openapi.json**.

## 6. Errores y límites

Los errores tienen un formato uniforme:

```json
{
  "status": "error",
  "error": {
    "codigo": "CONFIGURACION_INCOMPLETA",
    "mensaje": "Configura GEMINI_API_KEY en el backend para generar contenido."
  }
}
```

| HTTP | Qué revisar |
| --- | --- |
| 404 | El documento o contenido no existe. |
| 413 | Archivo mayor de 10 MiB, PDF de más de 100 páginas o texto de más de 250000 caracteres. |
| 415 | Solo se aceptan PDF, MD y TXT. |
| 422 | Campos inválidos, perfil fuera de catálogo, PDF protegido/ilegible, texto insuficiente o consulta sin contexto recuperable. |
| 502 | Fallo de Gemini o respuesta del modelo incompatible con el esquema. |
| 503 | Clave sin configurar o SQLite no disponible. |
| 500 | Error interno inesperado. |

MD y TXT deben estar en UTF-8. Los PDF deben contener texto seleccionable; los escaneados necesitan OCR previo. Solo se guarda contenido después de validar la respuesta completa. Si falla la generación, el documento cargado sigue disponible.

## 7. Conexión con Streamlit

El servidor Streamlit llama a estas rutas desde `app/cliente_api.py`. Las pantallas reciben el JSON validado y no acceden directamente al grafo ni a SQLite.

Hay que comparar esta propuesta de rutas y campos con el contenido real de `src/contrato.py` y con el cliente del equipo, que no están en esta rama. La imagen de responsabilidades no define esos campos. Esta entrega no modifica el frontend ni su contrato compartido.

Este backend cubre documentos, generación e historial compartido. No recibe tokens ni implementa sesiones o roles. Si en el futuro un navegador llama directamente a la API, `NUEVAMENTE_CORS_ORIGINS` permite declarar sus orígenes; las llamadas desde el servidor de Streamlit no necesitan CORS.
