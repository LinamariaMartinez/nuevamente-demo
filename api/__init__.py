"""Backend HTTP. Compatibilidad con los módulos históricos importables desde src/."""

import sys
from pathlib import Path

_source_dir = str(Path(__file__).resolve().parents[1] / "src")
if _source_dir not in sys.path:
    sys.path.insert(0, _source_dir)
