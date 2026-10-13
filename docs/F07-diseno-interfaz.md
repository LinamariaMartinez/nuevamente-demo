# F07 — Diseño de la interfaz de NuevaMente

## 1. Objetivo

Construir la interfaz que pide el reto ("interfaz interactiva, ej. Streamlit o Gradio"). NuevaMente la usa **una
institución para capacitar a su gente** (empleados o contratistas): no es abierta al público ni multiempresa.
La app abre en una **portada** que explica qué es NuevaMente y da acceso a dos paneles:

- **Estudiante:** escribe un tema, elige nivel y formato, y recibe su paquete de contenido: el material,
  los metadatos de aprendizaje, el puntaje de calidad, las fuentes y la descarga del JSON.
- **Admin:** define el **sector de la institución** (el nicho que pide el reto, uno para toda la institución), sube
  documentos (PDF, MD, TXT), revisa que se indexaron bien y revisa los paquetes marcados para revisión.

F07 trabaja con **datos de ejemplo (mock)**. La conexión con el backend real es F08: se cambia una variable de entorno
y las pantallas quedan iguales.

## 2. Alcance

**Capa 1 (obligatoria):** las dos páginas completas y una **vista genérica** que muestra cualquier paquete
(contenido como texto, metadatos, puntaje, observaciones, fuentes y botón "Descargar JSON").

**Capa 2 (si alcanza el tiempo; cada pieza es independiente):** **vistas interactivas por formato**.
- Flashcards: tarjeta que se voltea, con "anterior" y "siguiente".
- Quiz: el estudiante elige una respuesta, ve si acertó y la justificación; al final, su puntaje.
- Guía paso a paso: pasos numerados con avance.

Si un formato no tiene vista interactiva, usa la genérica. Si una vista interactiva no llega a tiempo, la app igual funciona.

**Fuera de alcance (el diseño deja espacio para agregarlo después):** nivel de dificultad, evaluación obligatoria
definida por el admin, mínimo para "cumplir" un curso, que el estudiante elija un documento, progreso en vivo
durante la generación y cuentas de usuario.

## 3. Arquitectura

**Streamlit (Frontend) + API FastAPI (Backend).** El Frontend nunca llama al grafo de agentes directamente:
le pide todo a la API.

```
 Navegador ──► Streamlit (app/) ──► cliente_api.py ──┬─ MODO_API=mock → app/mocks/*.json
                                                     └─ MODO_API=http → API FastAPI (api/) ──► grafo de agentes (src/)
                                                                                         └──► OCI Object Storage (F09)
```

**La costura es `app/cliente_api.py`:** es el único archivo del Frontend que sabe de dónde vienen los datos.
Mientras la API no exista, responde con los mocks. Cuando exista, se cambia `MODO_API=http` en `.env`.
Así Frontend y Backend avanzan en paralelo sin bloquearse.

## 4. Estructura de carpetas y dueños

| Ruta | Rol dueño | Qué es |
|---|---|---|
| `src/contrato.py` | **Compartido** (Frontend + Backend) | Forma del paquete y de las peticiones (modelos Pydantic) y listas fijas de perfiles, formatos y nichos |
| `app/inicio.py` | Frontend | Punto de entrada (`streamlit run app/inicio.py`): menú Estudiante / Admin |
| `app/cliente_api.py` | Frontend | Una función por ruta de la API; modo mock o http; traduce los errores |
| `app/estilo.py` + `.streamlit/config.toml` | Frontend | Tema visual y piezas reutilizables (tarjeta de puntaje, etiquetas de conceptos) |
| `app/paginas/estudiante.py` | Frontend | Formulario y resultado |
| `app/paginas/portada.py` | Frontend | Portada: qué es NuevaMente, cómo funciona y accesos a Estudiante y Admin |
| `app/paginas/admin.py` | Frontend | Contraseña, sector de la institución, subida de documentos, estado de la indexación, paquetes por revisar |
| `app/vistas/__init__.py` | Frontend | Directorio formato → vista; si no hay vista propia, usa `generica` |
| `app/vistas/generica.py` | Frontend | Capa 1 |
| `app/vistas/flashcards.py`, `quiz.py`, `guia.py` | Frontend | Capa 2 (una persona por archivo) |
| `app/mocks/*.json` | Frontend | Paquetes de ejemplo; `flashcards.json` sale del ejemplo del Hito 4 |
| `api/main.py` | Backend | Rutas FastAPI |
| `api/servicios.py` | Backend | Lógica de cada ruta: llamar al grafo, indexar, guardar en Object Storage |
| `tests/test_interfaz_*.py` + `tests/apps_interfaz/` | Frontend | Pruebas de la interfaz, un archivo por pieza; `apps_interfaz/` tiene las mini-apps que usa AppTest (sección 8) |

**Reglas:**
- Cada rol trabaja solo en sus archivos.
- `src/contrato.py` se cambia **solo de común acuerdo**: un cambio ahí afecta a los dos lados. Si se cambia, se actualizan los mocks en el mismo PR.
- Las páginas no saben de HTTP ni de mocks: solo llaman a `cliente_api`. Las vistas no saben de dónde salió el paquete: reciben un paquete ya validado.

## 5. El contrato

### 5.1 El paquete

Base: el JSON de ejemplo del Hito 4 (formato flashcards). Se conservan todos sus campos y nombres y se **agregan**
los marcados con ➕. (Ejemplo anotado: las marcas y los comentarios no son JSON válido. Los JSON
válidos de referencia son los de `app/mocks/`.)

```json
{
  "id_paquete": "3f2a…",                       ➕ identificador único
  "creado_en": "2026-10-14T15:30:00Z",         ➕ fecha y hora (ISO 8601, UTC)
  "status": "exito",                            "exito" | "error"
  "codigo_error": null,                        ➕ si status = "error": "sin_contexto" | "contenido_vacio" | "error_interno"
  "mensaje_error": null,                       ➕ si status = "error": texto para mostrar
  "metadatos": {
    "tema": "Redes VCN en OCI",                ➕ lo que pidió el estudiante
    "tiempo_estimado_estudio_minutos": 5,
    "conceptos_clave": ["VCN", "Subredes"],
    "prerrequisitos": [],
    "perfil_aplicado": "Principiante",
    "formato_generado": "Flashcards",
    "nicho_sector": "General",
    "nivel_detalle": "Didáctico"
  },
  "contenido_adaptado": {
    "titulo": "…",
    "introduccion_contextualizada": "…",
    "items": [ … ]                              la forma depende del formato (5.2)
  },
  "fuentes": [                                 ➕ anclaje en las fuentes (lo pide el reto)
    { "documento": "oci_redes.pdf", "fragmento": 12, "extracto": "Una VCN es una red…" }
  ],
  "evaluacion_calidad": {
    "anclaje_fuente_score": 1.0,
    "claridad_pedagogica": "Alta",
    "observaciones": "…",
    "intentos_revision": 1,
    "requiere_revision_admin": false           ➕ true si no superó la revisión tras el máximo de intentos
  }
}
```

### 5.2 Forma de `items` según el formato

| Formato | Campos de cada item |
|---|---|
| Flashcards | `frente`, `dorso`, `pista_didactica` (sin cambios respecto al Hito 4) |
| Quiz | `pregunta`, `opciones` (lista de textos), `respuesta_correcta` (posición en `opciones`, empezando en 0), `justificacion` |
| Tutorial (guía paso a paso) | `paso` (número), `titulo`, `explicacion`, `ejemplo` (opcional) |
| Resumen (TL;DR) y Guion (de clase o video) | `titulo`, `contenido` |

### 5.3 Listas fijas

Viven en `src/contrato.py`; el formulario y la validación de la API usan las mismas.

| Lista | Valores (los nombres exactos se confirman con el equipo, ver la sección 10) |
|---|---|
| Perfiles | Principiante · Intermedio · Avanzado (los tres niveles del Redactor; acordado en la weekly del 13-oct) |
| Formatos | Tutorial · Flashcards · Quiz · Resumen · Guion |
| Nichos (sector de la institución) | Fintech · Salud · E-commerce · General — lo elige el admin, no el estudiante |

### 5.4 Petición para generar

```json
{ "tema": "Redes VCN en OCI", "perfil": "Principiante", "formato": "Flashcards", "documentos": [] }
```
La petición no lleva nicho: el Backend aplica el sector guardado en la configuración (`{"sector": "General"}`).
`documentos` va vacío: hoy se busca en todos los documentos. Queda reservado para que más adelante el estudiante pueda elegir uno.

### 5.5 Rutas de la API (Backend)

| Ruta | Qué hace | Clave de admin |
|---|---|---|
| `GET /salud` | Indica si la API está viva | No |
| `POST /paquetes` | Recibe la petición (5.4) y devuelve un paquete (5.1) | No |
| `GET /paquetes/{id_paquete}` | Devuelve un paquete guardado | No |
| `GET /paquetes?requiere_revision=true` | Lista resumida: `id_paquete`, `creado_en`, `tema`, `formato`, `anclaje_fuente_score` | **Sí** |
| `POST /documentos` | Recibe un archivo PDF, MD o TXT y lo indexa | **Sí** |
| `GET /documentos` | Lista de documentos: `nombre`, `estado` (`procesando` / `indexado` / `error`), `chunks`, `error` | **Sí** |
| `GET /configuracion` | Devuelve `{"sector": "..."}` (por defecto `"General"`) | No |
| `PUT /configuracion` | Recibe `{"sector": "..."}` y lo guarda; responde la configuración guardada | **Sí** |

**Clave de admin (requisito para Backend):** las rutas marcadas reciben la cabecera `X-Clave-Admin` y la rechazan
con 401 si no coincide. El Frontend la envía desde F07. Cómo y cuándo se implementa la validación lo decide Backend.

**Tiempo de respuesta:** el Frontend espera `POST /paquetes` y `POST /documentos` hasta un tiempo máximo configurable (`TIEMPO_MAXIMO_SEGUNDOS`); las demás rutas, máximo 10 s, y `/salud`, 5 s. Si `/salud` falla, no se piden más datos en esa pantalla.
Si Backend elige otra forma de responder (por ejemplo, por etapas), solo cambia `cliente_api.py`.

## 6. Errores (lo que ve el usuario)

Reglas: nunca se muestra un error técnico en bruto (el detalle va en un desplegable "Ver detalle"); el formulario
conserva lo que escribió el usuario (`st.session_state`); los errores se traducen en `cliente_api.py`.

| Caso | Mensaje / comportamiento |
|---|---|
| Tema vacío | Al pulsar "Generar": "Escribe un tema para generar tu material." (el botón siempre está activo para no perder el primer clic) |
| La API no responde (`/salud`) | Aviso arriba: "El servicio no está disponible en este momento"; el formulario sigue visible |
| Se pasa el tiempo máximo | "La generación está tardando más de lo normal" + Reintentar |
| `codigo_error = sin_contexto` | "No encontré ese tema en los documentos cargados. Prueba con otras palabras." |
| Otro `status = error` | `mensaje_error` + Reintentar |
| Paquete con `requiere_revision_admin = true` | **Se muestra el material** con el aviso: "Este material no superó la revisión automática de calidad. Un administrador lo va a revisar." |
| El JSON no cumple el contrato | "Hubo un problema con el material generado" + detalle en el desplegable |
| Item incompleto en una vista interactiva | Ese paquete se muestra con la vista genérica |
| Admin: contraseña incorrecta | "Contraseña incorrecta"; puede reintentar |
| Admin: archivo que no es PDF, MD o TXT | El selector no permite elegirlo |
| Admin: archivo de más de 10 MB | "El archivo supera 10 MB" (cuida los 20 GB de Object Storage; ajustable) |
| Admin: documento con `estado = error` | Se muestra en rojo, con el motivo |
| Admin: la API responde 401 | "No tienes permiso. Revisa la configuración de la clave." |
| `MODO_API=mock` | Etiqueta visible: "Modo demostración: datos de ejemplo" |

## 7. Estilo visual

Objetivo: que no parezca una demo genérica de Streamlit ni una app genérica de IA.

- Se define **una sola vez, al inicio**, en `.streamlit/config.toml` (colores, tipografía, bordes) y en `app/estilo.py`
  (piezas reutilizables). Hay una sola persona a cargo; las vistas lo heredan y no definen colores propios.
- No se usa CSS pesado para forzar Streamlit, porque se rompe al actualizar.
- La identidad de NuevaMente (nombre, logo tipográfico, tono de los textos) es propia: no usa colores ni logos de Oracle ni de Alura.
- Pendiente: referencias visuales (3 a 5 capturas, cada una con qué gusta de ella), tres adjetivos de la sensación buscada,
  y la elección de modo claro, oscuro o ambos.

## 8. Pruebas

Con `unittest`, como el resto del repo. **Ninguna prueba necesita API key ni la API corriendo:** todas usan el modo mock,
así que se pueden sumar al CI del Hito 3.

| Prueba | Verifica |
|---|---|
| Contrato | Cada JSON de `app/mocks/` cumple `src/contrato.py` |
| Cliente | En modo mock, `cliente_api` devuelve paquetes válidos y traduce los errores (sin contexto, tiempo agotado, API caída) |
| Pantallas | Con `streamlit.testing.v1.AppTest`: la página del estudiante genera y muestra un paquete; la del admin pide contraseña antes de mostrar algo |
| Vistas | Cada vista dibuja su mock sin fallar; un item incompleto cae en la vista genérica |

## 9. Configuración y dependencias

- `requirements.txt` (compartido): se agregan `streamlit` y `requests`. `pydantic` ya está.
- `.env` (y `.env.example`, sin valores reales): `MODO_API` (`mock` | `http`), `URL_API`, `CLAVE_ADMIN_API`,
  `TIEMPO_MAXIMO_SEGUNDOS`.
- `.streamlit/secrets.toml` (no se sube; se agrega al `.gitignore`): `contrasena_admin`.

## 10. **PBIs propuestos**:
- PBI01-F07 (#20, ya existe): contrato, mocks, cliente, estilo, las dos páginas y la vista genérica.
- PBI02-F07 (nuevo): vistas interactivas por formato.

**Ramas:** `feature/F07-...` sale de `develop` (ya tiene F02, F03 y F04). El diseño entra como primer commit en
`docs/F07-diseno-interfaz.md`. Al cerrar el hito, un resumen pasa a la rama `documentacion`.
