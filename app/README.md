# Interfaz de NuevaMente (Streamlit)

La interfaz con la que la institución usa NuevaMente: administración sube documentos, arma temas y revisa material; cada estudiante estudia sus temas con material generado a su nivel. Habla con la API de FastAPI del backend por HTTP y no importa el grafo de agentes.

Demo en línea: https://nuevamente-ia.streamlit.app

## Qué hace cada rol

| Rol | Pantallas | Qué puede hacer |
|---|---|---|
| Sin sesión | Landing · Iniciar sesión | Conocer la plataforma, ver las cuentas de demostración y entrar |
| Estudiante | Mis temas · Tema | Elegir un tema asignado, su nivel (Principiante, Intermedio, Avanzado) y un formato (Flashcards, Quiz, Tutorial, Resumen, Guion), y estudiar el material con sus fuentes |
| Administración | Documentos · Temas · Material en revisión · Usuarios | Subir PDF, Markdown o TXT; armar temas con sus documentos y su sector; aprobar o rechazar el material que el revisor no aprobó; crear cuentas, asignar temas y restablecer contraseñas |

La primera vez que alguien entra con una contraseña temporal, la interfaz le pide una nueva antes de seguir.

Lo que no ve el estudiante: el material que quedó en revisión, los puntajes del revisor y los intentos. Sí ve el tiempo estimado, los conceptos clave, los prerrequisitos y las fuentes.

## Cómo está organizada

```text
app/
├── inicio.py          Punto de entrada: arma el menú según el rol
├── arranque.py        Solo en Streamlit Cloud: prende el backend en el mismo proceso
├── cliente_api.py     El único archivo que sabe de dónde vienen los datos (mock o http)
├── sesion.py          Sesión, rol y cierre de sesión
├── menu.py            Menú por rol
├── estilo.py, marca.py  Identidad visual "Bosque sereno" y logo
├── paginas/           Landing, acceso, páginas del estudiante y de administración
├── vistas/            Cómo se muestra cada formato (flashcards, quiz, guía, resumen, guion)
├── plantillas/        HTML de la landing y del acceso (con st.html, sin JavaScript)
└── mocks/             Respuestas y cuentas de ejemplo para el modo mock
```

El contrato con el backend está en `src/contrato.py`, compartido con la API. El tema de colores está en `.streamlit/config.toml`.

## Correrla en local

Desde la **raíz del repositorio**, con Python 3.11 o superior y las dependencias de `requirements.txt` instaladas. Hay que lanzarla desde la raíz: Streamlit busca `.streamlit/` en la carpeta desde donde se corre, y sin eso la app abre sin su identidad visual.

### Modo mock (sin backend)

Responde con los JSON de `app/mocks/`. Sirve para trabajar en la interfaz sin API ni clave de Gemini.

```bash
.venv/bin/streamlit run app/inicio.py
```

Cuentas del modo mock:

| Rol | Usuario | Contraseña |
|---|---|---|
| Estudiante | `laura` | `demo-estudiante` |
| Estudiante con contraseña temporal | `mateo` | `temporal-123` |
| Administración | `admin` | `demo-admin` |

### Modo http (con la API)

1. Inicia la API como explica el README del backend (`python -m uvicorn api.main:app --port 8000`).
2. Carga las cuentas y los temas de demostración:
   ```bash
   .venv/bin/python -m scripts.crear_cuentas_demo --con-tema-demo
   ```
   Detalle en [docs/cuentas_demo.md](../docs/cuentas_demo.md).
3. Lanza la interfaz apuntando a la API:
   ```bash
   MODO_API=http URL_API=http://127.0.0.1:8000 .venv/bin/streamlit run app/inicio.py
   ```

En Windows, usa `.venv\Scripts\` en lugar de `.venv/bin/` y define las variables en `.env`.

### Variables

| Variable | Valor por defecto | Para qué |
|---|---|---|
| `MODO_API` | `mock` | `mock` o `http` |
| `URL_API` | `http://localhost:8000` | Dirección de la API en modo http |
| `TIEMPO_MAXIMO_SEGUNDOS` | `300` | Cuánto espera la interfaz una generación |

## Despliegue en Streamlit Community Cloud

Streamlit Cloud corre un solo proceso, el de Streamlit. Con `ARRANCAR_BACKEND=1`, `app/arranque.py` prende la API de FastAPI dentro de ese mismo proceso, una sola vez, y carga las cuentas y los 4 temas de demostración con `scripts/crear_cuentas_demo.py`. En local, sin esa variable, `arranque.py` no hace nada.

**Configuración.** Además de `ARRANCAR_BACKEND=1` y `MODO_API=http`, la app necesita la clave de Gemini, las credenciales de OCI y las claves de las cuentas de demostración. Se configuran en Settings → Secrets de Streamlit Cloud, nunca en el repositorio; los nombres de las variables están en `.env.example`. Si cambias un secreto, reinicia la app: el arranque corre una vez por proceso.

**Cuentas en la landing.** Con la API real, la landing y el acceso muestran las cuentas `estudiante_demo` y `admin_demo`. Si no están configuradas, muestran "Pide tu usuario a quien administra la plataforma.".

**Cada reinicio empieza de cero.** Streamlit Cloud borra el disco al reiniciar la app: se pierde el material generado y el arranque vuelve a crear las cuentas y los temas. Los documentos y los paquetes aprobados se guardan en OCI Object Storage.

## Pruebas

Las pruebas de la interfaz no necesitan API, Gemini ni OCI:

```bash
.venv/bin/python -m pytest tests -k interfaz
```

Si cambias un color del tema, corre `tests/test_interfaz_tema.py`: comprueba los contrastes.

## Más detalle

- Diseño de la interfaz (pantallas, flujo y decisiones): [docs/F07-diseno-interfaz.md](../docs/F07-diseno-interfaz.md)
- Contrato y endpoints de la API: [docs/uso_api.md](../docs/uso_api.md)
- Cuentas y temas de demostración: [docs/cuentas_demo.md](../docs/cuentas_demo.md)
