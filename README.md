# G-10-Latam-equipo30
Hackathon ONE G10 - LATAM Equipo 30

## Hito 3

El flujo Researcher → Writer → Reviewer y el ciclo de corrección están en `src/graph.py`.
Instalación, ejecución, contrato de estado y pruebas: [documentación de Hito 3](docs/hito_3_multiagente.md).

## Interfaz (F07)

```bash
.venv/bin/streamlit run app/inicio.py
```

Se corre desde la raíz del repo para que Streamlit lea `.streamlit/` (tema y límite de subida).
Con `MODO_API=mock` (por defecto, en `.env`) usa datos de ejemplo y no necesita la API. Cuentas de demostración,
**solo en modo mock**:

| Usuario | Contraseña | Rol |
|---|---|---|
| `laura` | `demo-estudiante` | Estudiante con dos temas |
| `mateo` | `temporal-123` | Estudiante con contraseña temporal (pide cambiarla) |
| `admin` | `demo-admin` | Administración |

Con `MODO_API=http`, la interfaz usa la API de `URL_API` y las cuentas reales.

Pruebas de la interfaz: `.venv/bin/python -m unittest discover -s tests -p "test_interfaz*.py"`
