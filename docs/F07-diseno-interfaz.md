# F07 — Diseño de la interfaz de NuevaMente (versión 2.2)

## 0. Cambios

### Versión 2.2 (respecto a la 2.1)

Ajustes tras recorrer la pieza 1 en la app. El contrato (§5) no cambia.

| Tema | Versión 2.1 | Versión 2.2 |
|---|---|---|
| Entrada sin sesión | Iniciar sesión | **Landing** para el jurado y visitantes; desde ahí, Iniciar sesión |
| Ancho de la app | Centrada | **Pantalla ancha** (`layout="wide"`) |
| Pantallas de acción | Formulario y resultado uno debajo del otro | **Dos columnas:** formulario o lista a la izquierda (1/3), resultado a la derecha (2/3) |
| Flashcards | Tarjeta plana con botones | **Tarjeta que se voltea** (animada), progreso, teclado y **Lo sé / Repasar** |
| Resumen y Guion | Vista genérica ("Titulo: … Contenido: …") | **Resumen en tarjetas** con "En pocas palabras"; **Guion en escenas** numeradas |
| Nombre, rol y Cerrar sesión | Justo debajo del menú | **Al fondo del menú** (única excepción de CSS, §9) |

### Versión 2.1 (respecto a la 2)

Ajuste visual y de navegación a partir de la imagen de referencia de la identidad visual. El contrato (§5) no cambia
en esta versión: se actualiza cuando Backend cierre el contrato común.

| Tema | Versión 2 | Versión 2.1 |
|---|---|---|
| Menú lateral | Colores por defecto de Streamlit | **Verde oscuro en los dos modos**, con el nombre, el rol y Cerrar sesión debajo |
| Menú del estudiante | Mis temas | **Mis temas · Evaluaciones** |
| Menú del admin | Lista de siete pantallas | **Agrupado:** Contenido · Personas · Ajustes |
| Página del tema | Selector Estudiar \| Evaluación | Solo **Estudiar**; la evaluación se presenta desde **Evaluaciones** |
| Mis temas | Métricas, filtro y tarjetas | Igual, con filtro en píldoras, etiqueta de estado por tema e ícono; sin barra de progreso |
| Logo | Hojas con tallo; texto casi negro; versión según el tema | **Hojas redondeadas sin tallo, texto verde**; el menú usa siempre la versión clara |
| Modo oscuro | Fondo verde azulado (`#102522`) | **Fondo neutro `#14201E`**, superficie `#1E2B28`, botón `#3A8277` |

### Versión 2 (respecto a la 1)

| Tema | Versión 1 | Versión 2 |
|---|---|---|
| Acceso | Portada con "Soy estudiante" / "Soy administrador"; el admin entra con una contraseña única | **Cuentas**: todos inician sesión con usuario y contraseña. Las crea el admin; nadie se registra |
| Qué estudia la persona | Escribe cualquier tema | Estudia los **temas que le asignaron** (cada tema agrupa uno o varios documentos) |
| Material en revisión | Se muestra con un aviso | **No se muestra** al estudiante; puede generar otra versión. El admin ve la lista |
| JSON | "Descargar JSON" para el estudiante | **"Exportar JSON"** en el panel del admin |
| Evaluación | Fuera de alcance | **Modo evaluación**: examen fijo por tema, revisado y publicado por el admin, con nota mínima e intentos |
| Admin | Una página con todo | Una página por tarea: Documentos, Temas, Exámenes, Usuarios, Progreso, Material en revisión, Configuración |
| Autenticación con la API | Cabecera `X-Clave-Admin` | `Authorization: Bearer <token>` para todas las rutas |
| Estilo | Pendiente | Identidad visual **"Bosque sereno"** (aprobada), tema claro y oscuro |

Se conserva todo lo demás: arquitectura, contrato del paquete, vistas por formato, manejo de errores y modo mock.

## 1. Objetivo

Construir la interfaz que pide el reto ("interfaz interactiva, ej. Streamlit o Gradio"). NuevaMente la usa **una
institución para capacitar a su gente** (empleados o contratistas): no es abierta al público ni multiempresa.

- **Estudiante:** inicia sesión y tiene dos entradas en el menú:
  - **Mis temas:** abre un tema para **estudiar**: elige nivel y formato y recibe su material (contenido, metadatos de
    aprendizaje, puntaje de calidad y fuentes);
  - **Evaluaciones:** presenta el examen oficial de cada tema y ve su nota.
- **Admin:** sube documentos, arma temas, genera y publica exámenes, crea usuarios, sigue el progreso, revisa el material
  que no pasó el control de calidad y define el **sector de la institución** (el nicho que pide el reto, uno para toda la institución).

F07 trabaja con **datos de ejemplo (mock)**. La conexión con el backend real es F08: se cambia una variable de entorno
y las pantallas quedan iguales.

## 2. Alcance

El flujo completo se diseña aquí y se construye en **tres piezas, en orden de prioridad**. Cada pieza funciona sola en
modo mock; si una no llega a tiempo, la app sigue completa con las anteriores.

| Pieza | Contenido |
|---|---|
| **1** | Landing · Inicio de sesión y cambio de contraseña temporal · Mis temas · Estudiar dentro del tema · Admin: Documentos, Temas, Material en revisión, Configuración |
| **2** | Evaluaciones del estudiante · Admin: Exámenes |
| **3** | Admin: Usuarios y Progreso |

Del diseño v1 se mantienen la vista genérica del paquete y las vistas interactivas por formato (flashcards, quiz, guía paso a paso), que corresponden al PBI01 y al PBI02.

**Fuera de alcance:** registro público, recuperar la contraseña por correo, editar a mano el texto de las preguntas del examen,
límite de tiempo en el examen, mantener la sesión al recargar la página (F5 pide iniciar sesión de nuevo), buscador de temas.

## 3. Arquitectura

**Streamlit (Frontend) + API FastAPI (Backend).** El Frontend nunca llama al grafo de agentes directamente:
le pide todo a la API.

```
 Navegador ──► Streamlit (app/) ──► cliente_api.py ──┬─ MODO_API=mock → app/mocks/*.json
                                                     └─ MODO_API=http → API FastAPI (api/) ──► grafo de agentes (src/)
                                                                                         └──► OCI Object Storage (F09)
```

**La costura es `app/cliente_api.py`:** es el único archivo del Frontend que sabe de dónde vienen los datos.
Si Backend cambia una ruta o un campo, se ajustan `src/contrato.py` y `cliente_api.py`; las pantallas no cambian.

**Entrada y menú.** `app/inicio.py` decide qué se ve:
- sin sesión → **Landing** (página inicial) e **Iniciar sesión**, sin menú lateral;
- con contraseña temporal → solo **Cambia tu contraseña**;
- con sesión → el menú del rol (`st.navigation`) y, debajo (`st.sidebar`), el nombre, el rol y **Cerrar sesión**.

El menú se arma desde una lista por rol: una pantalla que no esté lista simplemente no aparece. El del admin va en
secciones (`st.navigation` con un diccionario `{sección: [páginas]}`).

| Rol | Menú |
|---|---|
| Estudiante | Mis temas · Evaluaciones |
| Admin | **Contenido:** Documentos · Temas · Exámenes · Material en revisión — **Personas:** Usuarios · Progreso — **Ajustes:** Configuración |

**Páginas fuera del menú.** Se abren con `st.switch_page` y guardan en la sesión qué tema se eligió; si alguien llega
sin tema elegido, vuelve a la lista de donde salió:
- **Tema** (Estudiar): desde **Abrir tema** en Mis temas.
- **Evaluación** (presentar el examen o ver el resultado): desde **Comenzar evaluación** o **Ver resultado** en Evaluaciones.

## 4. Estructura de carpetas y dueños

| Ruta | Rol dueño | Qué es | Pieza |
|---|---|---|---|
| `src/contrato.py` | **Compartido** | Modelos Pydantic del contrato y listas fijas | 1–3 |
| `app/inicio.py` | Frontend | Punto de entrada: sesión y menú por rol | 1 |
| `app/sesion.py` | Frontend | Iniciar y cerrar sesión, usuario actual, exigir rol | 1 |
| `app/cliente_api.py` | Frontend | Una función por ruta; modo mock o http; token; traduce los errores | 1–3 |
| `app/marca.py`, `assets/`, `.streamlit/config.toml` | Frontend | Identidad visual: logo, ícono y tema (ajustados en la v2.1, §9) | 1 |
| `app/paginas/acceso.py` | Frontend | Iniciar sesión y cambiar contraseña (reemplaza la portada) | 1 |
| `app/paginas/estudiante/mis_temas.py` | Frontend | Lista de temas asignados | 1 |
| `app/paginas/estudiante/tema.py` | Frontend | Página del tema: Estudiar | 1 |
| `app/paginas/estudiante/evaluaciones.py` | Frontend | Lista de evaluaciones, una por tema | 2 |
| `app/paginas/estudiante/evaluacion.py` | Frontend | Presentar la evaluación de un tema y ver el resultado | 2 |
| `app/paginas/admin/documentos.py` | Frontend | Subir documentos y ver su estado | 1 |
| `app/paginas/admin/temas.py` | Frontend | Crear, editar y retirar temas | 1 |
| `app/paginas/admin/revision.py` | Frontend | Material que no pasó el control de calidad + Exportar JSON | 1 |
| `app/paginas/admin/configuracion.py` | Frontend | Sector de la institución | 1 |
| `app/paginas/admin/examenes.py` | Frontend | Generar, revisar y publicar el examen de cada tema | 2 |
| `app/paginas/admin/usuarios.py` | Frontend | Crear usuarios, asignar temas, restablecer contraseña, dar intentos | 3 |
| `app/paginas/admin/progreso.py` | Frontend | Notas e intentos por tema | 3 |
| `app/paginas/landing.py` | Frontend | Landing: qué es NuevaMente, cómo funciona y acceso a Iniciar sesión | 1 |
| `app/estilo.py` | Frontend | El único CSS de la app: bloque del usuario al fondo del menú (§9) | 1 |
| `app/vistas/` | Frontend | Vista genérica y vistas por formato + `examen.py` (formulario del examen, pieza 2) | 1–2 |
| `app/vistas/flashcards.py` | Frontend | Componente HTML: tarjeta que se voltea, progreso y Lo sé / Repasar (v2.2) | 1 |
| `app/vistas/resumen.py`, `app/vistas/guion.py` | Frontend | Resumen en tarjetas y Guion en escenas (v2.2) | 1 |
| `app/mocks/*.json` | Frontend | Paquetes, usuarios, temas y examen de ejemplo | 1–3 |
| `api/` | Backend | Rutas FastAPI y su lógica | — |
| `tests/test_interfaz_*.py` + `tests/apps_interfaz/` | Frontend | Pruebas de la interfaz (sección 10) | 1–3 |

**Reglas:**
- Cada rol trabaja solo en sus archivos.
- `src/contrato.py` se cambia **solo de común acuerdo**. Si se cambia, se actualizan los mocks en el mismo PR.
- Las páginas no saben de HTTP ni de mocks: solo llaman a `cliente_api`. Las vistas reciben datos ya validados.

## 5. El contrato

Lo que la interfaz necesita recibir. **Es una propuesta para Backend**, que decide cómo implementarlo.
Persistencia acordada con Backend: SQLite en la VM, con respaldos y exámenes aprobados en Object Storage.

### 5.1 El paquete

Sin cambios respecto a la versión 1: el JSON del Hito 4 más `id_paquete`, `creado_en`, `codigo_error`, `mensaje_error`,
`metadatos.tema`, `fuentes` y `evaluacion_calidad.requiere_revision_admin`. Los JSON de referencia están en `app/mocks/`.

### 5.2 Forma de `items` según el formato

| Formato | Campos de cada item |
|---|---|
| Flashcards | `frente`, `dorso`, `pista_didactica` |
| Quiz | `pregunta`, `opciones` (lista de textos), `respuesta_correcta` (posición en `opciones`, desde 0), `justificacion` |
| Tutorial (guía paso a paso) | `paso` (número), `titulo`, `explicacion`, `ejemplo` (opcional) |
| Resumen (TL;DR) y Guion | `titulo`, `contenido` |

### 5.3 Listas fijas

| Lista | Valores |
|---|---|
| Perfiles | Principiante · Intermedio · Avanzado |
| Formatos | Tutorial · Flashcards · Quiz · Resumen · Guion |
| Nichos (sector de la institución) | Fintech · Salud · E-commerce · General — lo elige el admin |
| Roles | `estudiante` · `admin` |

### 5.4 Modelos nuevos

| Modelo | Campos |
|---|---|
| `Usuario` | `id_usuario`, `nombre`, `usuario`, `rol`, `activo`, `debe_cambiar_contrasena`, `temas` (lista de `id_tema`) |
| `Sesion` | `token`, `usuario` (`Usuario`) |
| `Tema` | `id_tema`, `nombre`, `descripcion`, `documentos` (nombres de archivo, iguales al `metadata["source"]` de los chunks) |
| `PreguntaExamen` (admin) | `id_pregunta`, `pregunta`, `opciones`, `respuesta_correcta`, `justificacion`, `fuente` (`Fuente`) |
| `PreguntaEvaluacion` (estudiante) | `id_pregunta`, `pregunta`, `opciones` — **sin** respuesta ni justificación |
| `Examen` | `id_tema`, `estado` (`borrador` / `publicado`), `preguntas` (`PreguntaExamen`), `nota_minima` (0–100), `intentos_maximos` (≥ 1) |
| `EstadoEvaluacion` | `id_tema`, `hay_examen`, `nota_minima`, `intentos_maximos`, `intentos_usados`, `mejor_nota` (o vacío), `aprobado` |
| `ResultadoIntento` | `nota`, `aprobado`, `intentos_restantes`, `revision` (lista de `PreguntaExamen` con la respuesta elegida; **solo si aprobó**) |
| `FilaProgreso` | `id_usuario`, `nombre`, `id_tema`, `estado`, `mejor_nota`, `intentos_usados`, `intentos_maximos` |

**Regla de seguridad:** el estudiante nunca recibe `respuesta_correcta` ni `justificacion` antes de aprobar. Ocultarlas en
pantalla no basta (se verían en el navegador); Backend no las envía y `PreguntaEvaluacion` las rechaza si llegan.

### 5.5 Petición para generar material

```json
{ "id_tema": "t-redes", "tema": "", "perfil": "Principiante", "formato": "Flashcards" }
```
- `id_tema` (nuevo): Backend busca **solo en los documentos de ese tema** (por ejemplo, con el filtro de FAISS sobre
  `metadata["source"]`) y comprueba que el tema esté asignado a quien pide.
- `tema` pasa a ser **opcional**: es el campo "¿Algo en particular?". Vacío = todo el tema.
- Sigue sin nicho: Backend aplica el sector guardado en la configuración.

### 5.6 Reglas de la evaluación

1. **Nota** de 0 a 100: porcentaje de respuestas correctas, redondeado. Sin responder cuenta como incorrecta.
2. **Aprobar cierra la evaluación** de ese tema: no hay más intentos y la persona ve las respuestas y justificaciones de su intento aprobado.
3. **Un examen publicado no se edita.** Para cambiarlo, el admin genera una versión nueva; al publicarla reemplaza a la anterior.
   Los intentos y notas ya registrados se conservan y siguen contando para el tema.
4. **Estado del tema** para el estudiante: *Sin evaluación* (no hay examen publicado), *Pendiente*, *Aprobado* o *Sin intentos*.
5. El admin puede dar **intentos extra** a una persona en un tema; quedan registrados.

### 5.7 Rutas de la API (Backend)

Todas, salvo `GET /salud` y `POST /sesion`, reciben `Authorization: Bearer <token>`. Backend comprueba el rol en cada ruta
y, para el estudiante, que el tema esté asignado.

| Pieza | Ruta | Qué hace | Rol |
|---|---|---|---|
| — | `GET /salud` | Indica si la API está viva | — |
| 1 | `POST /sesion` | Recibe `usuario` y `contrasena`; devuelve `Sesion` | — |
| 1 | `DELETE /sesion` | Cierra la sesión (invalida el token) | Todos |
| 1 | `PUT /sesion/contrasena` | Recibe `actual` y `nueva`; quita `debe_cambiar_contrasena` | Todos |
| 1 | `GET /temas` | El admin recibe todos; el estudiante, solo los suyos | Todos |
| 1 | `POST /temas` · `PUT /temas/{id}` · `DELETE /temas/{id}` | Crear, editar y retirar temas | Admin |
| 1 | `POST /paquetes` | Recibe la petición (5.5) y devuelve un paquete (5.1) | Estudiante |
| 1 | `GET /paquetes/{id_paquete}` | Devuelve un paquete guardado | Admin |
| 1 | `GET /paquetes?requiere_revision=true` | Lista resumida del material en revisión | Admin |
| 1 | `POST /documentos` · `GET /documentos` | Subir e indexar; listar con su estado | Admin |
| 1 | `GET /configuracion` · `PUT /configuracion` | Leer (todos) y guardar (admin) el sector | Todos / Admin |
| 2 | `POST /temas/{id}/examen` | Genera un borrador (reemplaza el borrador anterior, si hay) | Admin |
| 2 | `GET /temas/{id}/examen` | Devuelve el examen con respuestas | Admin |
| 2 | `DELETE /temas/{id}/examen/preguntas/{id_pregunta}` | Quita una pregunta del borrador | Admin |
| 2 | `POST /temas/{id}/examen/preguntas/{id_pregunta}/regenerar` | Cambia una pregunta del borrador por otra | Admin |
| 2 | `PUT /temas/{id}/examen/publicacion` | Recibe `nota_minima` e `intentos_maximos` y publica | Admin |
| 2 | `GET /temas/{id}/evaluacion` | Devuelve `EstadoEvaluacion` | Estudiante |
| 2 | `GET /temas/{id}/evaluacion/preguntas` | Devuelve `PreguntaEvaluacion` (sin respuestas) | Estudiante |
| 2 | `POST /temas/{id}/evaluacion/intentos` | Recibe `{ "respuestas": { "<id_pregunta>": <posición> } }`; devuelve `ResultadoIntento` | Estudiante |
| 3 | `GET /usuarios` · `POST /usuarios` | Listar; crear (responde el usuario y una `contrasena_temporal`) | Admin |
| 3 | `PUT /usuarios/{id}` | Cambiar `nombre`, `temas` o `activo` | Admin |
| 3 | `POST /usuarios/{id}/contrasena-temporal` | Restablece; responde una `contrasena_temporal` nueva | Admin |
| 3 | `POST /usuarios/{id}/intentos-extra` | Recibe `id_tema` y `cantidad` | Admin |
| 3 | `GET /progreso?id_tema=` | Lista de `FilaProgreso` | Admin |

**Mínimo para la demo real (F08):** `POST /sesion`, `GET /temas` y `POST /paquetes` con `id_tema`. Con eso, la
generación de material funciona de verdad; lo demás puede mostrarse en modo mock si no alcanza el tiempo.

**Tiempo de respuesta:** el Frontend espera `POST /paquetes`, `POST /documentos` y `POST /temas/{id}/examen` hasta
`TIEMPO_MAXIMO_SEGUNDOS`; las demás rutas, máximo 10 s, y `/salud`, 5 s.

**Errores de Backend:** las respuestas 409 y 422 traen `{"mensaje": "..."}` en español y sin detalles técnicos.

## 6. Pantallas

Orden de los elementos y estados de cada pantalla. Los textos siguen el tono del documento de identidad visual.

### 6.0 Landing (pieza 1, v2.2)
Para el jurado y quien visite el proyecto. Ocupa el ancho completo; sin menú lateral.
- **Arriba, a la izquierda:** logo, "De documentación técnica a material de estudio, en minutos.", una frase de
  explicación ("Tu institución sube sus manuales; NuevaMente los convierte en material adaptado a cada nivel, con fuentes
  y control de calidad."), **Iniciar sesión** y **Ver cómo funciona** (baja a esa sección).
- **Arriba, a la derecha:** caja **Prueba la demo** con las cuentas de demostración (**solo en modo mock**) y los formatos.
- **Cómo funciona:** tres pasos en tres tarjetas: la institución sube documentos y arma temas → tres agentes
  (Investigador busca, Redactor adapta, Revisor verifica) → quien estudia aprende y presenta la evaluación.
- **Por dentro:** tres tarjetas: fiel a las fuentes (RAG, cada material cita sus fragmentos), calidad revisada
  (puntaje ≥ 0.8; si no, se corrige hasta 3 veces) y listo para integrar (JSON estructurado, OCI Object Storage).

### 6.1 Acceso (pieza 1)
- **Iniciar sesión:** logo, "Aprender hoy, construir mañana.", los tres pasos (consulta tus temas → estudia → presenta la
  evaluación), usuario, contraseña, **Iniciar sesión** (formulario: Enter también envía).
- **Cambia tu contraseña** (si es temporal): actual, nueva, confirmar. Mínimo 8 caracteres y que coincidan; se valida
  también en Backend.

### 6.2 Mis temas — estudiante (pieza 1)
- Título "Mis temas" y "Consulta tus temas asignados y continúa donde lo dejaste."
- Métricas (`st.metric` en contenedores con borde): **Asignados**, **Pendientes** (todo tema que no esté *Aprobado*) y
  **Aprobados**.
- Filtro en píldoras (`st.pills`): *Todos / Pendientes / Aprobados*, con ese mismo criterio.
- Una tarjeta por tema (`st.container(border=True)`): ícono, nombre, etiqueta de estado (`st.badge`: *Pendiente*,
  *Aprobado*, *Sin intentos* o *Sin evaluación*, según §5.6), "N documentos" más los intentos restantes o la nota, y **Abrir tema**.
- **Sin barra de progreso:** la app no mide cuánto ha estudiado cada persona; solo conoce la nota de la evaluación.
- Mientras no exista la pieza 2, todos los temas muestran *Sin evaluación*.
- Vacío: "Todavía no tienes temas asignados. Cuando la institución te asigne uno, aparecerá aquí."

### 6.3 Tema — estudiante (pieza 1)
Nombre, descripción y "Documentos de este tema: …". Solo tiene **Estudiar**; la evaluación se presenta desde Evaluaciones (§6.4).
**Dos columnas (v2.2):** a la izquierda, en una caja, nivel, formato, "¿Algo en particular?" y **Generar material**; a la
derecha, el material (o sus estados). Antes de generar, la derecha muestra un recuadro: "Elige tu nivel y formato y pulsa
Generar material. Aquí aparecerá tu material."

**Vistas por formato (v2.2):**
- **Flashcards:** componente HTML con la tarjeta grande que se voltea (clic o espacio), Anterior/Siguiente (botones o
  flechas), barra de progreso, **Lo sé** y **Repasar** (cuentas arriba y un punto por tarjeta abajo, en verde o ámbar).
  Colores de la paleta según el modo claro u oscuro. Las marcas viven en el componente; no se guardan.
- **Resumen:** recuadro "En pocas palabras" con la introducción; cada sección como tarjeta (hasta 3 por fila); los
  conceptos clave al final.
- **Guion:** escenas numeradas en una columna ("Escena 1 · <título>" y su contenido).
- Quiz y Guía paso a paso siguen como en el PBI02.

**Estudiar:** nivel, formato, "¿Algo en particular? (opcional)" y **Generar material**. Estados: preparando,
error con Reintentar, material en revisión ("Este material necesita una revisión adicional antes de estar disponible." +
Generar otra versión), material con sus fuentes. Si cambian el nivel o el formato, se quita el material anterior.
En el quiz de estudio: "Práctica: no cuenta para tu nota."

### 6.4 Evaluaciones — estudiante (pieza 2)
**Lista (`evaluaciones.py`):** título "Evaluaciones" y "Presenta la evaluación de cada tema cuando te sientas listo.
Necesitas la nota mínima para aprobar." Una tarjeta por tema asignado, con nombre, etiqueta de estado y:

| Estado | Detalle | Botón |
|---|---|---|
| Pendiente | Nota mínima · mejor nota (si hay) · intentos restantes | **Comenzar evaluación** |
| Aprobado | Nota · en qué intento aprobó | **Ver resultado** |
| Sin intentos | Mejor nota · "Habla con quien administra la plataforma para pedir un intento nuevo." | — |
| Sin evaluación | "Este tema todavía no tiene evaluación." | — |

**Presentar (`evaluacion.py`):**

| Estado | Lo que se ve |
|---|---|
| Sin evaluación | "Este tema todavía no tiene evaluación." |
| Pendiente | Nota mínima, intentos restantes, mejor nota (si hay) y **Comenzar evaluación** |
| Respondiendo | Todas las preguntas en una página, "Respondidas: 6 de 10", **Entregar evaluación**; si faltan: "Te faltan 4 preguntas. ¿Entregar igual?" |
| No aprobó | Su nota y "Aún no alcanzaste la nota mínima. Revisa los temas y consulta cuántos intentos te quedan." |
| Sin intentos | "Ya usaste tus intentos. Habla con quien administra la plataforma para pedir uno nuevo." |
| Aprobó | "Aprobaste la evaluación. Puedes consultar tu resultado y las explicaciones disponibles.", su nota y un desplegable con respuestas y justificaciones |

### 6.5 Admin
- **Documentos (pieza 1):** caja **Subir documento** (PDF, Markdown o TXT, máximo 10 MB) con **Subir e indexar**, y
  caja **Documentos subidos** con una tabla: nombre, estado (etiqueta *Indexado* o *Con error*), fragmentos, temas que
  lo usan y el error, si lo hay. Vacío: "Todavía no hay documentos. Sube el primero en la sección de arriba."
- **Temas (pieza 1):** dos columnas (v2.2): a la izquierda el formulario (nombre, descripción, documentos indexados) con **Crear tema**; a la derecha la lista de temas con sus
  documentos, **Editar** y **Retirar** (con confirmación). Sin documentos: enlace a Documentos. Ante un error, el formulario conserva lo escrito.
- **Material en revisión (pieza 1):** dos columnas (v2.2): a la izquierda la lista del material que no superó la revisión; **Abrir** muestra a la derecha el paquete con
  **Exportar JSON**.
- **Configuración (pieza 1):** sector de la institución, con la explicación de cómo se usa, y **Guardar cambios**.
- **Exámenes (pieza 2):**

| Estado | Lo que se ve |
|---|---|
| Sin examen | Elegir tema y **Generar borrador** |
| Generando | "Estamos preparando el examen a partir de los documentos del tema." |
| Fuentes insuficientes | Explicación; no se crea el borrador |
| Borrador | Cada pregunta con respuesta correcta, justificación y fuente; **Quitar** y **Pedir otra**; nota mínima, intentos y **Publicar evaluación** (con confirmación) |
| Publicado | Solo lectura y **Generar nueva versión** |

- **Usuarios (pieza 3):** tabla (nombre, usuario, rol, estado, temas) y **Crear usuario**. La contraseña temporal se
  muestra **una sola vez**: "Cópiala ahora; no se volverá a mostrar." Por usuario: editar temas, activar o desactivar,
  **Restablecer contraseña** y **Dar intento extra** (con confirmación).
- **Progreso (pieza 3):** filtro por tema, métricas y tabla (persona, estado, mejor nota, intentos).

### 6.6 Común
- **Regla de dos columnas (v2.2):** donde se hace algo y se ve el resultado, el formulario o la lista va a la izquierda
  (1/3) y el resultado a la derecha (2/3): Estudiar, Crear tema, Material en revisión y, cuando se construyan, Exámenes
  (pieza 2) y Usuarios (pieza 3). No aplica a Documentos (su tabla necesita el ancho), Presentar evaluación, Mis temas,
  Evaluaciones, Progreso ni Configuración. En pantallas angostas las columnas se apilan solas.
- Las acciones sensibles se confirman con un segundo botón en la misma pantalla (sin ventanas emergentes).
- `MODO_API=mock`: etiqueta visible "Modo demostración: datos de ejemplo".

## 7. Errores (lo que ve el usuario)

Reglas: nunca se muestra un error técnico en bruto; el detalle ("Ver detalle") **solo lo ve el admin**; los formularios
conservan lo escrito; los errores se traducen en `cliente_api.py`.

| Caso | Mensaje / comportamiento |
|---|---|
| 401 en `POST /sesion` | "No pudimos validar tus datos. Revisa tu usuario y contraseña e inténtalo de nuevo." (igual si la cuenta no existe o está desactivada) |
| 401 en otra ruta | Vuelve a Iniciar sesión: "Tu sesión terminó. Inicia sesión de nuevo." |
| 403 | "No tienes permiso para esta acción." |
| 404 | "No encontramos lo que buscabas. Es posible que se haya retirado." |
| 409 / 422 | El `mensaje` de Backend; si no viene, un texto genérico |
| La API no responde | "El servicio no está disponible en este momento. Inténtalo de nuevo más tarde." |
| Tiempo máximo | "La generación está tardando más de lo normal. Inténtalo de nuevo en unos minutos." + Reintentar |
| `codigo_error = sin_contexto` | "No encontramos ese tema en los documentos cargados. Prueba con otras palabras." |
| Material con `requiere_revision_admin = true` | No se muestra al estudiante (6.3) |
| Archivo no permitido / de más de 10 MB | "Solo se aceptan archivos PDF, Markdown o TXT." / "El archivo supera 10 MB." |

## 8. Seguridad

**Frontend:**
- Ocultar el menú es comodidad, no protección. Cada página del admin vuelve a comprobar el rol al cargar.
- El token vive solo en `st.session_state`: nunca en la URL ni en logs; se borra al cerrar sesión.
- La interfaz no guarda contraseñas; la temporal se muestra una vez y se borra de la sesión.
- Sale `contrasena_admin` de `.streamlit/secrets.toml`.

**Propuesta para Backend:**
- Contraseñas con hash fuerte (bcrypt o argon2).
- El primer admin se crea desde la configuración del servidor (variables de entorno). Sin registro público.
- Límite de intentos fallidos de inicio de sesión.
- Token con vencimiento (por ejemplo, 8 horas).
- Registro de quién da intentos extra, restablece contraseñas o publica exámenes.

**Modo mock:** `app/mocks/usuarios.json` trae un estudiante (con dos temas) y un admin, con contraseñas de demostración
anotadas en el README. Solo existen en modo mock.

## 9. Estilo visual

Identidad **"Bosque sereno"** (documento de identidad visual, aprobado por el equipo): tema claro y oscuro en
`.streamlit/config.toml`, logo e ícono en `assets/`, íconos de línea en el menú, componentes nativos de Streamlit y
CSS mínimo. Contrastes según WCAG 2.2 AA, que se verifican con pruebas automáticas.

**Ajustes de la versión 2.1.** Solo componentes nativos y `config.toml`, **sin CSS a mano**: el CSS depende de nombres
internos de Streamlit que cambian entre versiones.

**Logo** (`assets/`): dos hojas redondeadas, sin tallo, y el texto "NuevaMente" convertido a trazos.

| Archivo | Colores | Dónde va |
|---|---|---|
| `logo_nuevamente.svg` | Hojas `#7DC1B0` y `#205E58`; texto `#205E58` | Pantalla de inicio de sesión (fondo claro) |
| `logo_nuevamente_menu.svg` | Hojas `#A9CDBD` y `#F5F7F5`; texto `#EAF2EF` | Menú lateral, en los dos modos (`st.logo`) |
| `icono_nuevamente.svg` | Cuadro `#205E58` con las hojas claras | Pestaña del navegador y menú plegado |

Como el menú es oscuro en los dos modos, el logo ya no depende del tema: `app/marca.py` deja de elegirlo y desaparece el
límite conocido (el logo anterior quedaba hasta el siguiente clic). `logo_nuevamente_oscuro.svg` se borra.

**Menú lateral** (`[theme.light.sidebar]` y `[theme.dark.sidebar]`):

| Modo | Fondo | Texto | Opción activa |
|---|---|---|---|
| Claro | `#205E58` | `#EAF2EF` (6.58:1) | `#2E6F66` (texto 5.15:1) |
| Oscuro | `#0E1715` | `#EAF2EF` (16.01:1) | `#2E6F66` (texto 5.15:1) |

**Modo oscuro** (`[theme.dark]`): el modo claro no cambia.

| Elemento | v2 | v2.1 | Contraste |
|---|---|---|---|
| Fondo | `#102522` | `#14201E` | — |
| Superficie | `#1A3530` | `#1E2B28` | Texto `#EAF2EF`: 12.89:1 |
| Botón principal | `#2F7A70` | `#3A8277` | Texto blanco: 4.53:1 |
| Bordes | `#6B8A81` | `#6B8A81` | 3.9:1 sobre la superficie |
| Enlaces, etiquetas y acentos | `#A9CDBD` | `#7DC1B0` | 7.07:1 sobre la superficie |

El verde claro de la referencia (`#7DC1B0`) **no** se usa en botones: Streamlit pone siempre blanco su texto y quedaría en 2.07:1.

**Maquetas aprobadas:** Mis temas (claro y oscuro), Documentos del admin con el menú agrupado y Evaluaciones del estudiante.

**Ajustes de la versión 2.2.**
- **Pantalla ancha:** `st.set_page_config(layout="wide")`. El texto largo del material queda en la columna derecha
  (unos 65–75 caracteres por línea en un portátil).
- **Única excepción de CSS:** `app/estilo.py` pega al fondo del menú lateral el bloque del usuario (nombre, rol y
  Cerrar sesión). Son unas pocas reglas y solo para ese bloque. Si una versión futura de Streamlit cambia su estructura
  interna, el bloque vuelve a quedar debajo del menú; nada más se rompe.
- **Componente de flashcards:** HTML y CSS propios dentro de `st.components.v1.html`. Animación de 0.5 s; con
  `prefers-reduced-motion` la tarjeta cambia sin girar. Botones con texto (no solo íconos) y manejables con teclado.
- **Maquetas aprobadas (v2.2):** landing ancha, dos columnas en Estudiar, flashcards con Lo sé / Repasar y resumen en tarjetas.

## 10. Pruebas

Con `unittest` y `streamlit.testing.v1.AppTest`. **Ninguna prueba necesita API key ni la API corriendo.**

| Prueba | Verifica |
|---|---|
| Contrato | Mocks válidos; `PreguntaEvaluacion` rechaza respuestas |
| Cliente | Token en cada ruta; 401/403/404/409 traducidos; el token nunca va en la URL; en mock, cada estudiante ve solo sus temas y la nota sigue la regla 5.6 |
| Acceso | Inicio correcto, incorrecto y vencido; cambio obligatorio de contraseña; cerrar sesión borra el token |
| Menú | El estudiante ve Mis temas (y Evaluaciones desde la pieza 2); el admin ve las tres secciones, cada una solo con las pantallas listas; debajo, nombre, rol y Cerrar sesión |
| Estudiante | Mis temas: las tres métricas, el filtro en píldoras, la etiqueta de cada uno de los cuatro estados y que no haya barra de progreso; abrir un tema; Estudiar |
| Evaluaciones | Una tarjeta por tema con el botón según su estado; los seis estados de `evaluacion.py` |
| Admin | Una prueba por pantalla |
| Permisos | Un estudiante no puede abrir pantallas del admin, ni por menú ni por URL; sin sesión solo se ven la Landing e Iniciar sesión |
| Landing | Es la página inicial sin sesión; **Iniciar sesión** lleva a la pantalla de acceso; las cuentas de demostración aparecen solo en modo mock |
| Vistas v2.2 | Flashcards: el HTML del componente lleva todas las tarjetas, escapa el texto y usa los colores del modo; Resumen y Guion no caen en la vista genérica |
| Dos columnas | Estudiar, Crear tema y Material en revisión dibujan dos columnas; Estudiar muestra el recuadro reservado antes de generar |
| Tema visual | Claves válidas de `config.toml` (incluidas `[theme.light.sidebar]` y `[theme.dark.sidebar]`); contrastes mínimos de §9 (botón oscuro ≥ 4.5:1, bordes ≥ 3:1, texto del menú en los dos modos); los tres SVG existen y `st.logo` usa el del menú |

Cada pieza se revisa también en la app corriendo, en tema claro y oscuro, comparándola con las maquetas aprobadas (§9).

## 11. Configuración y dependencias

- `requirements.txt`: sin dependencias nuevas.
- `.env` (y `.env.example`): `MODO_API` (`mock` | `http`), `URL_API`, `TIEMPO_MAXIMO_SEGUNDOS`. Sale `CLAVE_ADMIN_API`.
- La app se ejecuta desde la raíz del repo (`streamlit run app/inicio.py`) para que lea `.streamlit/`.

## 12. PBIs y ramas

- PBI01-F07: contrato, mocks, cliente, páginas y vista genérica.
- PBI02-F07: vistas interactivas por formato.
- **PBI03-F07 (nuevo): flujo v2 de este documento**, con las piezas 1, 2 y 3 como tareas.

La metodología permite hasta 3 PBIs por feature, así que el flujo v2 completo entra en el PBI03.
**Ramas:** `pbi/PBI0X-F07-...` salen de `feature/F07-...`, que sale de `develop`. Al cerrar el hito, un resumen pasa a la rama `documentacion`.
