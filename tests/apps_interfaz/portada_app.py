"""Mini-app para probar la portada con AppTest (sin navegación: los destinos van en None)."""

from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
for ruta in (RAIZ / "src", RAIZ / "app"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

from paginas import portada

portada.mostrar(destino_estudiante=None, destino_admin=None)
