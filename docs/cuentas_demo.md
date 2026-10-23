# Cuentas de prueba para backend y frontend

El proyecto maneja dos roles de acceso: `admin` y `estudiante`. Principiante,
Intermedio y Avanzado son perfiles de aprendizaje, no roles ni cuentas distintas.

El script crea usuarios **reales en SQLite**, compatibles con las sesiones Bearer
del backend y el cliente HTTP del frontend. No modifica los usuarios del modo mock.

| Usuario | Rol | Cambio de contraseña al entrar |
| --- | --- | --- |
| `admin_demo` | `admin` | No |
| `estudiante_demo` | `estudiante` | No; permite probar directamente el estudio |
| `temporal_demo` | `estudiante` | Sí; permite probar el primer acceso |

Las tres cuentas se crean activas. Cada una recibe una contraseña aleatoria de 24
caracteres, mostrada en la terminal únicamente al crearla. Guarda esas claves.
SQLite almacena solo su hash Argon2, mediante `api.auth.hash_password`.
Estas cuentas son para desarrollo y demostraciones.

## 1. Instalar y crear cuentas

Desde la raíz de la copia que contiene el backend, en PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.crear_cuentas_demo --con-tema-demo
```

Si aún no tienes entorno virtual, primero ejecuta `python -m venv .venv`.
En Linux/macOS sustituye `.\.venv\Scripts\python.exe` por `.venv/bin/python`.
También se admite ejecutar directamente `scripts/crear_cuentas_demo.py`.

`--con-tema-demo` carga `data/arquitectura_redes_vcn_oci.md` con el extractor del
backend, crea el tema `demo-redes-oci` y lo asigna a ambos estudiantes. Así, **Mis
temas** tiene un tema con fuentes reales para generar material. La carga no llama
a Gemini ni sube archivos a OCI; los embeddings se calculan al generar, como en
el resto de la API. Tampoco crea material educativo ficticio en el historial.

Sin esa opción, solo crea las cuentas. Para asignar temas ya existentes:

```powershell
.\.venv\Scripts\python.exe -m scripts.crear_cuentas_demo --tema redes-oci --tema otro-tema
```

Puedes combinar `--tema` con `--con-tema-demo`. Un tema inexistente hace fallar la
carga sin crear cuentas ni documentos parciales. El script usa las migraciones
existentes del backend y una transacción para insertar los datos.

## 2. Usar la misma base en el script y en la API

Por defecto, ambos leen `NUEVAMENTE_DB_PATH` de `.env`; si no está configurada,
usan `storage/nuevamente.sqlite3`. Las rutas relativas se resuelven desde la raíz
del repositorio. El script imprime la ruta absoluta utilizada.

Para una demo aislada, puedes escoger otra base. En la **misma terminal**:

```powershell
$env:NUEVAMENTE_DB_PATH = "storage/demo.sqlite3"
.\.venv\Scripts\python.exe -m scripts.crear_cuentas_demo --con-tema-demo
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

En una terminal nueva debes volver a definir esa variable, o guardarla en `.env`.
El argumento `--db storage/demo.sqlite3` también selecciona la base del script,
pero **no configura la API**. No ejecutes dos servidores en el mismo puerto.

La API queda disponible en <http://127.0.0.1:8000/docs> y su comprobación de salud
en <http://127.0.0.1:8000/health>.

## 3. Probar el backend sin frontend

Con la API corriendo, abre otra terminal y ejecuta:

```powershell
$apiDemo = "http://127.0.0.1:8000"
Invoke-RestMethod "$apiDemo/health"

$claveAdminDemo = Read-Host "Pega la contraseña de admin_demo que imprimió el script"
$sesionAdminDemo = Invoke-RestMethod -Method Post -Uri "$apiDemo/api/v1/sesion" `
    -ContentType "application/json" `
    -Body (@{ usuario = "admin_demo"; contrasena = $claveAdminDemo } | ConvertTo-Json)
$cabecerasAdminDemo = @{ Authorization = "Bearer $($sesionAdminDemo.token)" }
Invoke-RestMethod "$apiDemo/api/v1/usuarios" -Headers $cabecerasAdminDemo

$claveEstudianteDemo = Read-Host "Pega la contraseña de estudiante_demo"
$sesionEstudianteDemo = Invoke-RestMethod -Method Post -Uri "$apiDemo/api/v1/sesion" `
    -ContentType "application/json" `
    -Body (@{ usuario = "estudiante_demo"; contrasena = $claveEstudianteDemo } | ConvertTo-Json)
$cabecerasEstudianteDemo = @{ Authorization = "Bearer $($sesionEstudianteDemo.token)" }
Invoke-RestMethod "$apiDemo/api/v1/temas" -Headers $cabecerasEstudianteDemo
Invoke-RestMethod "$apiDemo/api/v1/temas/demo-redes-oci/documentos" -Headers $cabecerasEstudianteDemo
```

Resultados esperados: salud `ok`, el admin lista las cuentas y el estudiante ve
`demo-redes-oci` con su documento. La siguiente petición debe fallar con **403**:

```powershell
Invoke-RestMethod "$apiDemo/api/v1/usuarios" -Headers $cabecerasEstudianteDemo
```

Para probar generación real, configura `GEMINI_API_KEY` en el `.env` del backend
y reinicia la API. Después:

```powershell
$solicitudDemo = @{
    id_tema = "demo-redes-oci"
    perfil_destinatario = "Principiante"
    formato_salida = "Flashcards"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$apiDemo/api/v1/contenidos" `
    -Headers $cabecerasEstudianteDemo -ContentType "application/json" `
    -Body $solicitudDemo -TimeoutSec 300
```

La respuesta puede ser **201** con el material o **202** si necesita revisión del
admin. Autenticación, permisos, temas y cambio de contraseña funcionan sin Gemini.
La integración con OCI conserva la configuración y comportamiento del backend;
el script no configura credenciales de nube.

## 4. Probar desde Streamlit

Esta rama contiene el backend. Usa **otra copia del repositorio** con el frontend
F07 (`app/inicio.py`); mantén la API corriendo en la copia del backend.
No hace falta compartir el archivo SQLite con Streamlit: se comunica por HTTP.

Desde la raíz de esa copia del frontend, instala sus dependencias y ejecuta:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:MODO_API = "http"
$env:URL_API = "http://127.0.0.1:8000"
$env:TIEMPO_MAXIMO_SEGUNDOS = "300"
.\.venv\Scripts\python.exe -m streamlit run app/inicio.py
```

Abre <http://localhost:8501>. Si tenías una sesión previa en mock, recarga la página
después de reiniciar Streamlit. Las cuentas `admin`, `laura` y `mateo` del mock son
distintas de las creadas aquí.

| Prueba | Resultado esperado |
| --- | --- |
| Entrar con `admin_demo` | Menú de administración; documento, tema y estudiantes visibles |
| Entrar con `estudiante_demo` | Mis temas contiene el tema demo; no hay menú de administración |
| Abrir el tema y generar | Material o aviso de revisión; requiere Gemini configurado |
| Abrir Mi material | Solo material propio aprobado o generado con éxito |
| Entrar con `temporal_demo` | Pantalla obligatoria para cambiar contraseña |
| Cambiarla por una diferente, de al menos 12 caracteres | Se cierran los tokens anteriores; el frontend vuelve a iniciar sesión y permite estudiar |
| Admin aprueba material pendiente | El material aparece en Mi material de quien lo solicitó |
| Cerrar sesión | Las rutas protegidas vuelven a exigir inicio de sesión |

## 5. Pruebas automatizadas

Desde la raíz de la copia del backend, después de instalar `requirements.txt`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cuentas_demo.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_api_f08.py tests/test_api_integracion.py -q
```

Las pruebas nuevas usan bases temporales y las rutas reales de FastAPI. Verifican
roles, Argon2, repetición sin duplicados, preservación de claves/estados/sesiones,
rollback ante fallos, asignaciones, login, permisos, cambio obligatorio,
revocación de sesión, generación, historial y aprobación de material pendiente.
Gemini y la subida a OCI se sustituyen por dobles de prueba: no requieren claves
ni hacen llamadas externas. Las pruebas no ejercitan visualmente Streamlit;
para eso sigue la tabla anterior.

## Repetición y contraseñas

Repetir el script no cambia contraseñas, roles, nombres, activación ni el estado
de cambio obligatorio de cuentas existentes. Tampoco borra sesiones, historial
ni asignaciones anteriores. Solo añade las asignaciones solicitadas que falten.
Si un nombre existe con otro rol, aborta sin promoverlo. Los conflictos de nombre
del tema demo o de contenido del documento también se rechazan.

Opcionalmente puedes elegir claves mediante `DEMO_ADMIN_PASSWORD`,
`DEMO_ESTUDIANTE_PASSWORD` y `DEMO_TEMPORAL_PASSWORD` en el entorno o `.env`.
Deben tener al menos 12 caracteres; no se aceptan claves vacías. Solo se aplican
al crear cuentas nuevas. No las incluyas en archivos versionados.

Si pierdes una clave de estudiante, el admin puede restablecerla desde Usuarios.
Si pierdes la del admin, puedes crear otro administrador con `python -m api.crear_admin`
usando un nombre distinto, o iniciar otra demo en una base nueva. Reejecutar el
script no recupera ni reemplaza claves existentes.
