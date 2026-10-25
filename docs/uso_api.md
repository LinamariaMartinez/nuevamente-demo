# Cómo usar la API de NuevaMente

Guía del backend integrado (F06 + F08): documentos, temas, generación estructurada, historial, sesiones y roles. La URL local por defecto es `http://127.0.0.1:8000`. Los endpoints para el frontend están resumidos en la sección 5.

## 1. Preparar e iniciar el backend

Abre una terminal PowerShell en la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edita `.env` y configura `GEMINI_API_KEY`. La clave se queda en el backend.

Crea el primer administrador (interactivo):

```powershell
.\.venv\Scripts\python.exe -m api.crear_admin
```

Inicia el servidor:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

SQLite se crea automáticamente en `storage/nuevamente.sqlite3` (cambia la ruta con `NUEVAMENTE_DB_PATH`). Una base creada con versiones anteriores de F06 se migra sola al iniciar. Generar contenido requiere Gemini; el resto de operaciones no.

## 2. Autenticación y roles

Todas las rutas, salvo `GET /health` y `POST /api/v1/sesion`, requieren la cabecera `Authorization: Bearer <token>`. El token se obtiene con `POST /api/v1/sesion` y dura 8 horas.

| Rol | Puede |
| --- | --- |
| `admin` | Subir y consultar documentos; crear temas y configurar su nicho y nivel de detalle; asociar documentos a temas; crear estudiantes y asignarles temas; generar sobre cualquier tema o documento; ver todo el historial, incluido el material `requiere_revision`, y aprobarlo o rechazarlo. |
| `estudiante` | Ver sus temas asignados y los títulos de sus documentos; generar solo sobre temas asignados; ver únicamente su propio historial aprobado (`exito`). |

Un usuario con contraseña temporal debe cambiarla (`PUT /api/v1/sesion/contrasena`) antes de usar el resto de rutas.

## 3. Flujo completo desde PowerShell

```powershell
$base = "http://127.0.0.1:8000"
$json = "application/json; charset=utf-8"

# Administrador: iniciar sesión.
$login = @{ usuario = "admin"; contrasena = "TU_CONTRASENA" } | ConvertTo-Json
$admin = @{ Authorization = "Bearer " + (Invoke-RestMethod -Method Post -Uri "$base/api/v1/sesion" -ContentType $json -Body $login).token }

# Administrador: crear el tema con su nicho y asociarle un documento.
$tema = @{ id_tema = "redes-oci"; nombre = "Redes en OCI"; nicho_sector = "Cloud"; nivel_detalle = "Práctico" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/api/v1/temas" -Headers $admin -ContentType $json -Body ([System.Text.Encoding]::UTF8.GetBytes($tema))
$documento = curl.exe --silent --show-error --fail-with-body -X POST "$base/api/v1/documentos" -H "Authorization: $($admin.Authorization)" -F "archivo=@data/arquitectura_redes_vcn_oci.md" | ConvertFrom-Json
Invoke-RestMethod -Method Put -Uri "$base/api/v1/temas/redes-oci/documentos/$($documento.id)" -Headers $admin

# Administrador: crear un estudiante con el tema asignado.
$alumno = @{ nombre = "Ana"; usuario = "ana"; contrasena_temporal = "temporal-123456"; temas = @("redes-oci") } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/api/v1/usuarios" -Headers $admin -ContentType $json -Body $alumno

# Estudiante: la contraseña temporal debe cambiarse antes de usar el resto de rutas.
$login = @{ usuario = "ana"; contrasena = "temporal-123456" } | ConvertTo-Json
$temporal = @{ Authorization = "Bearer " + (Invoke-RestMethod -Method Post -Uri "$base/api/v1/sesion" -ContentType $json -Body $login).token }
$cambio = @{ contrasena_actual = "temporal-123456"; contrasena_nueva = "definitiva-123456" } | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri "$base/api/v1/sesion/contrasena" -Headers $temporal -ContentType $json -Body $cambio
$login = @{ usuario = "ana"; contrasena = "definitiva-123456" } | ConvertTo-Json
$ana = @{ Authorization = "Bearer " + (Invoke-RestMethod -Method Post -Uri "$base/api/v1/sesion" -ContentType $json -Body $login).token }

# Estudiante: ver sus temas y generar contenido sobre uno asignado.
Invoke-RestMethod -Uri "$base/api/v1/temas" -Headers $ana
$solicitud = @{
    id_tema = "redes-oci"
    tema = "¿Qué es una VCN y cuáles son sus componentes?"
    perfil_destinatario = "Intermedio"
    formato_salida = "Flashcards"
} | ConvertTo-Json
$respuesta = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/api/v1/contenidos" -Headers $ana -ContentType $json -Body ([System.Text.Encoding]::UTF8.GetBytes($solicitud)) -TimeoutSec 300
$paquete = $respuesta.Content | ConvertFrom-Json
$paquete.id; $paquete.fuentes

# Historial propio y descarga.
Invoke-RestMethod -Uri "$base/api/v1/contenidos?limit=20&offset=0" -Headers $ana
New-Item -ItemType Directory -Force -Path output | Out-Null
Invoke-WebRequest -UseBasicParsing -Uri "$base/api/v1/contenidos/$($paquete.id)/descarga" -Headers $ana -OutFile "output/contenido.json"
```

Revisa en `/docs` (Swagger) el cuerpo exacto de cada operación; el botón **Authorize** acepta el token.

## 4. Generación

`POST /api/v1/contenidos`:

```json
{
  "id_tema": "redes-oci",
  "tema": "¿Qué es una VCN y cuáles son sus componentes?",
  "perfil_destinatario": "Intermedio",
  "formato_salida": "Flashcards"
}
```

- `tema` es la consulta concreta y es opcional con `id_tema`: si se omite, se genera sobre el tema completo (se usa su nombre). Con `documento_id` es obligatorio. `id_tema` identifica el tema asignado cuyos documentos se usan como fuente.
- El **nicho** y el **nivel de detalle** salen de la configuración del tema (`PATCH /api/v1/temas/{id_tema}`); no se aceptan en la petición con `id_tema`.
- Alternativa solo para administradores: `documento_id` en lugar de `id_tema`, con `nicho_sector` y `nivel_detalle` opcionales (por defecto `General` y `Didáctico`).
- Perfiles: **Principiante**, **Intermedio**, **Avanzado**. Formatos: **Flashcards**, **Resumen**, **Quiz**, **Tutorial**, **Guion**.
- En Quiz, `respuesta_correcta` es el **texto exacto** de una de las `opciones`.

Respuestas:

| HTTP | Cuándo | Cuerpo |
| --- | --- | --- |
| 201 | Material generado (admin: siempre; estudiante: solo si `status` es `exito`). | Paquete educativo + `id`, `creado_en`, `id_tema`, `fuentes`. |
| 202 | Estudiante cuyo material quedó `requiere_revision`. | `{id, creado_en, status: "requiere_revision", mensaje}`; sin contenido. |

Cada elemento de `fuentes` indica de dónde sale el contenido: `documento_id`, `documento` (título), `fragmento` (posición entre los recuperados), `pagina` (PDF, o `null`) y `extracto` (hasta 300 caracteres).

La generación es síncrona. Si vence el timeout del cliente, consulta el historial antes de repetir el POST.

## 5. Mapa de rutas

| Método | Ruta | Rol | Descripción |
| --- | --- | --- | --- |
| GET | `/health` | público | Estado de API y SQLite. |
| POST | `/api/v1/sesion` | público | Login; devuelve `token` y datos del usuario. |
| GET | `/api/v1/sesion` | autenticado | Quién soy: usuario, rol, `debe_cambiar_contrasena` y temas (admin: todos). |
| DELETE | `/api/v1/sesion` | autenticado | Cierra la sesión. |
| PUT | `/api/v1/sesion/contrasena` | autenticado | Cambia la contraseña y revoca las sesiones. |
| GET | `/api/v1/usuarios` | admin | Lista usuarios con sus temas asignados. |
| POST | `/api/v1/usuarios` | admin | Crea un estudiante con contraseña temporal y temas. |
| PUT | `/api/v1/usuarios/{id_usuario}` | admin | Modifica un estudiante: `nombre`, `activo` o `contrasena_temporal` (desactivar o resetear revoca sus sesiones). |
| POST | `/api/v1/usuarios/{id_usuario}/desbloqueo` | admin | Quita el bloqueo de login por intentos fallidos (204). El login devuelve `429 DEMASIADOS_INTENTOS` con `Retry-After` tras 5 fallos. |
| GET | `/api/v1/temas` | autenticado | Admin: todos; estudiante: sus temas asignados. |
| POST | `/api/v1/temas` | admin | Crea un tema (`nicho_sector`, `nivel_detalle` y `documentos` opcionales). |
| GET | `/api/v1/temas/{id_tema}` | asignado/admin | Detalle y configuración del tema. |
| PATCH | `/api/v1/temas/{id_tema}` | admin | Cambia nombre, descripción, nicho o nivel de detalle. |
| DELETE | `/api/v1/temas/{id_tema}` | admin | Borra el tema y sus asociaciones; el historial se conserva. |
| GET | `/api/v1/temas/{id_tema}/documentos` | asignado/admin | Documentos asociados (metadatos). |
| PUT / DELETE | `/api/v1/temas/{id_tema}/documentos/{documento_id}` | admin | Asocia o desasocia un documento. |
| GET | `/api/v1/temas/{id_tema}/estudiantes` | admin | Estudiantes asignados. |
| PUT / DELETE | `/api/v1/temas/{id_tema}/estudiantes/{id_usuario}` | admin | Asigna o retira el tema a un estudiante. |
| GET | `/api/v1/catalogos` | autenticado | Perfiles, formatos, sectores y límites. |
| POST | `/api/v1/documentos` | admin | Multipart: `archivo`, `documento_titulo` opcional. |
| POST | `/api/v1/documentos/texto` | admin | JSON: `documento_titulo`, `documento_contenido`. |
| GET | `/api/v1/documentos[/{id}[/original]]` | admin | Lista, detalle con texto y original. |
| POST | `/api/v1/contenidos` | autenticado | Generación (sección 4). |
| GET | `/api/v1/contenidos` | autenticado | Historial paginado; filtros `id_tema`, `documento_id`, `perfil`, `status` y (admin) `id_usuario`, `pendiente`. |
| GET | `/api/v1/contenidos/{id}[/descarga]` | dueño/admin | Paquete completo o descarga JSON. |
| POST | `/api/v1/contenidos/{id}/aprobar` | admin | Aprueba material pendiente: pasa a ser visible para el estudiante (`aprobado_en`). |
| POST | `/api/v1/contenidos/{id}/rechazar` | admin | Elimina material pendiente; el estudiante puede volver a generarlo. |

Los listados devuelven `items`, `total`, `limit` (1–100, por defecto 20) y `offset`.

## 6. Errores

Todos los errores usan el mismo sobre:

```json
{ "status": "error", "error": { "codigo": "TEMA_NO_ASIGNADO", "mensaje": "No tienes asignado este tema." } }
```

| HTTP | Códigos |
| --- | --- |
| 401 | `AUTENTICACION_REQUERIDA`: falta el token, es inválido, expiró o las credenciales no coinciden. |
| 403 | `PERMISOS_INSUFICIENTES` (acción de admin o contraseña temporal pendiente), `TEMA_NO_ASIGNADO`. |
| 404 | `TEMA_NO_ENCONTRADO`, `DOCUMENTO_NO_ENCONTRADO`, `CONTENIDO_NO_ENCONTRADO`, `ESTUDIANTE_NO_ENCONTRADO`, `ASOCIACION_NO_ENCONTRADA`, `ASIGNACION_NO_ENCONTRADA`, `RECURSO_NO_ENCONTRADO`. |
| 409 | `CONFLICTO`: usuario o tema duplicado. `CONTENIDO_NO_PENDIENTE`: se intenta aprobar o rechazar material que no está en revisión. |
| 413 / 415 | Archivo demasiado grande o tipo no admitido (PDF, MD, TXT). |
| 422 | `ENTRADA_INVALIDA`, `SIN_DOCUMENTOS_ASOCIADOS`, `SIN_CONTEXTO` y errores de lectura del documento. |
| 502 | `GENERACION_FALLIDA`, `SALIDA_INVALIDA`. |
| 503 | `CONFIGURACION_INCOMPLETA` (falta `GEMINI_API_KEY`), `BASE_DATOS_NO_DISPONIBLE`. |
| 500 | `ERROR_INTERNO`. |

Un estudiante que pide un contenido ajeno o pendiente de revisión recibe 404, para no revelar qué identificadores existen.

## 7. Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --ignore=tests/validate_live_review.py --ignore=tests/check_models.py
```

`tests/test_api_integracion.py` cubre autorización por tema, generación por `id_tema`, fuentes, material en revisión con aprobación y rechazo, aislamiento del historial y migración de la base; usa un generador simulado y no llama a Gemini.

Si un navegador llama directamente a la API, declara sus orígenes en `NUEVAMENTE_CORS_ORIGINS` (se admite la cabecera `Authorization`).
