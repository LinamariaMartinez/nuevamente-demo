# F07 — Diseño de la interfaz de NuevaMente (versión 2)

## 0. Cambios respecto a la versión 1

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

- **Estudiante:** inicia sesión, ve sus temas y, dentro de cada uno, elige entre
  - **Estudiar:** elige nivel y formato y recibe su material (contenido, metadatos de aprendizaje, puntaje de calidad y fuentes);
  - **Evaluación:** presenta el examen oficial del tema y ve su nota.
- **Admin:** sube documentos, arma temas, genera y publica exámenes, crea usuarios, sigue el progreso, revisa el material
  que no pasó el control de calidad y define el **sector de la institución** (el nicho que pide el reto, uno para toda la institución).

F07 trabaja con **datos de ejemplo (mock)**. La conexión con el backend real es F08: se cambia una variable de entorno
y las pantallas quedan iguales.

## 2. Alcance

El flujo completo se diseña aquí y se construye en **tres piezas, en orden de prioridad**. Cada pieza funciona sola en
modo mock; si una no llega a tiempo, la app sigue completa con las anteriores.

| Pieza | Contenido |
|---|---|
| **1** | Inicio de sesión y cambio de contraseña temporal · Mis temas · Estudiar dentro del tema · Admin: Documentos, Temas, Material en revisión, Configuración |
| **2** | Evaluación del estudiante · Admin: Exámenes |
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
- sin sesión → solo **Iniciar sesión**;
- con contraseña temporal → solo **Cambia tu contraseña**;
- con sesión → el menú del rol (`st.navigation`) y **Cerrar sesión**.

El menú se arma desde una lista por rol: una pantalla que no esté lista simplemente no aparece.

| Rol | Menú |
|---|---|
| Estudiante | Mis temas |
| Admin | Documentos · Temas · Exámenes · Usuarios · Progreso · Material en revisión · Configuración |

**Abrir un tema.** Mis temas guarda el tema elegido en la sesión y lleva a la página del tema (`st.switch_page`),
que no aparece en el menú. Si alguien llega a ella sin tema elegido, vuelve a Mis temas.

## 4. Estructura de carpetas y dueños

| Ruta | Rol dueño | Qué es | Pieza |
|---|---|---|---|
| `src/contrato.py` | **Compartido** | Modelos Pydantic del contrato y listas fijas | 1–3 |
| `app/inicio.py` | Frontend | Punto de entrada: sesión y menú por rol | 1 |
| `app/sesion.py` | Frontend | Iniciar y cerrar sesión, usuario actual, exigir rol | 1 |
| `app/cliente_api.py` | Frontend | Una función por ruta; modo mock o http; token; traduce los errores | 1–3 |
| `app/marca.py`, `assets/`, `.streamlit/config.toml` | Frontend | Identidad visual: logo, ícono y tema | PBI01 |
| `app/paginas/acceso.py` | Frontend | Iniciar sesión y cambiar contraseña (reemplaza la portada) | 1 |
| `app/paginas/estudiante/mis_temas.py` | Frontend | Lista de temas asignados | 1 |
| `app/paginas/estudiante/tema.py` | Frontend | Página del tema: Estudiar (pieza 1) y Evaluación (pieza 2) | 1–2 |
| `app/paginas/admin/documentos.py` | Frontend | Subir documentos y ver su estado | 1 |
| `app/paginas/admin/temas.py` | Frontend | Crear, editar y retirar temas | 1 |
| `app/paginas/admin/revision.py` | Frontend | Material que no pasó el control de calidad + Exportar JSON | 1 |
| `app/paginas/admin/configuracion.py` | Frontend | Sector de la institución | 1 |
| `app/paginas/admin/examenes.py` | Frontend | Generar, revisar y publicar el examen de cada tema | 2 |
| `app/paginas/admin/usuarios.py` | Frontend | Crear usuarios, asignar temas, restablecer contraseña, dar intentos | 3 |
| `app/paginas/admin/progreso.py` | Frontend | Notas e intentos por tema | 3 |
| `app/vistas/` | Frontend | Vista genérica y vistas por formato (diseño v1) + `examen.py` (formulario del examen) | 2 |
| `app/mocks/*.json` | Frontend | Paquetes, usuarios, temas y examen de ejemplo | 1–3 |
| `api/` | Backend | Rutas FastAPI y su lógica | — |
| `tests/test_interfaz_*.py` + `tests/apps_interfaz/` | Frontend | Pruebas de la interfaz (sección 8) | 1–3 |

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

### 6.1 Acceso (pieza 1)
- **Iniciar sesión:** logo, "Aprender hoy, construir mañana.", los tres pasos (consulta tus temas → estudia → presenta la
  evaluación), usuario, contraseña, **Iniciar sesión** (formulario: Enter también envía).
- **Cambia tu contraseña** (si es temporal): actual, nueva, confirmar. Mínimo 8 caracteres y que coincidan; se valida
  también en Backend.

### 6.2 Mis temas — estudiante (pieza 1)
- Título y orientación breve; métricas: asignados, aprobados y pendientes (todo tema que no esté *Aprobado*);
  filtro *Todos / Pendientes / Aprobados* con ese mismo criterio.
- Una tarjeta por tema: nombre, descripción, número de documentos, estado (texto + ícono) y **Abrir tema**.
- Vacío: "Todavía no tienes temas asignados. Cuando la institución te asigne uno, aparecerá aquí."

### 6.3 Tema — estudiante
Nombre, descripción, "Documentos de este tema: …" y el selector **Estudiar | Evaluación**.

**Estudiar (pieza 1):** nivel, formato, "¿Algo en particular? (opcional)" y **Generar material**. Estados: preparando,
error con Reintentar, material en revisión ("Este material necesita una revisión adicional antes de estar disponible." +
Generar otra versión), material con sus fuentes. Si cambian el nivel o el formato, se quita el material anterior.
En el quiz de estudio: "Práctica: no cuenta para tu nota."

**Evaluación (pieza 2):**

| Estado | Lo que se ve |
|---|---|
| Sin evaluación | "Este tema todavía no tiene evaluación." |
| Pendiente | Nota mínima, intentos restantes, mejor nota (si hay) y **Comenzar evaluación** |
| Respondiendo | Todas las preguntas en una página, "Respondidas: 6 de 10", **Entregar evaluación**; si faltan: "Te faltan 4 preguntas. ¿Entregar igual?" |
| No aprobó | Su nota y "Aún no alcanzaste la nota mínima. Revisa los temas y consulta cuántos intentos te quedan." |
| Sin intentos | "Ya usaste tus intentos. Habla con quien administra la plataforma para pedir uno nuevo." |
| Aprobó | "Aprobaste la evaluación. Puedes consultar tu resultado y las explicaciones disponibles.", su nota y un desplegable con respuestas y justificaciones |

### 6.4 Admin
- **Documentos (pieza 1):** subir (PDF, Markdown o TXT, máximo 10 MB) y lista con nombre, estado, fragmentos y error.
  Vacío: "Todavía no hay documentos. Sube el primero en la sección de arriba."
- **Temas (pieza 1):** formulario (nombre, descripción, documentos indexados) con **Crear tema**; lista de temas con sus
  documentos, **Editar** y **Retirar** (con confirmación). Sin documentos: enlace a Documentos. Ante un error, el formulario conserva lo escrito.
- **Material en revisión (pieza 1):** lista del material que no superó la revisión; **Abrir** muestra el paquete con
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

### 6.5 Común
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

## 10. Pruebas

Con `unittest` y `streamlit.testing.v1.AppTest`. **Ninguna prueba necesita API key ni la API corriendo.**

| Prueba | Verifica |
|---|---|
| Contrato | Mocks válidos; `PreguntaEvaluacion` rechaza respuestas |
| Cliente | Token en cada ruta; 401/403/404/409 traducidos; el token nunca va en la URL; en mock, cada estudiante ve solo sus temas y la nota sigue la regla 5.6 |
| Acceso | Inicio correcto, incorrecto y vencido; cambio obligatorio de contraseña; cerrar sesión borra el token |
| Estudiante | Estados de Mis temas, abrir un tema, Estudiar dentro del tema, los seis estados de la Evaluación |
| Admin | Una prueba por pantalla |
| Permisos | Un estudiante no puede abrir pantallas del admin, ni por menú ni por URL; sin sesión solo se ve Iniciar sesión |
| Tema visual | Claves válidas de `config.toml` y contrastes mínimos |

Cada pieza se revisa también en la app corriendo, en tema claro y oscuro.

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
