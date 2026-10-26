"""CLI: JSON por stdout, mensajes de progreso por stderr."""

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

from pydantic import ValidationError
from langchain_core.exceptions import OutputParserException

from errors import NoContextError
from schemas import DRAFT_SCHEMAS, PROFILE_GUIDANCE, EducationalResponse, ErrorDetail, ErrorResponse, GenerationRequest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generar contenido educativo con salida JSON.")
    parser.add_argument("--tema")
    parser.add_argument("--perfil", choices=list(PROFILE_GUIDANCE), default="Principiante")
    parser.add_argument("--formato", choices=list(DRAFT_SCHEMAS), default="Flashcards")
    parser.add_argument("--nicho", default="General")
    parser.add_argument("--detalle", default="Didáctico")
    parser.add_argument("--salida", type=Path, help="Guardar también el JSON en este archivo UTF-8.")
    parser.add_argument("--schema", action="store_true", help="Mostrar JSON Schema sin llamar a Gemini.")
    args = parser.parse_args(argv)

    if args.schema:
        print(json.dumps(EducationalResponse.model_json_schema(), ensure_ascii=False, indent=2))
        return 0
    if args.tema is None:
        parser.error("--tema es obligatorio para generar contenido")

    exit_code = 1
    try:
        request = GenerationRequest(
            tema=args.tema, perfil_destinatario=args.perfil, formato_salida=args.formato,
            nicho_sector=args.nicho, nivel_detalle=args.detalle,
        )
    except ValidationError:
        payload = error_json("ENTRADA_INVALIDA", "El tema y el perfil deben contener texto válido.")
    else:
        try:
            with redirect_stdout(sys.stderr):
                from generation import generate_content

                response = generate_content(request)
            payload = response.model_dump_json(indent=2)
            exit_code = 0 if response.status == "exito" else 2
        except NoContextError:
            payload = error_json("SIN_CONTEXTO", "No se encontró texto relevante en el índice para este tema.")
        except FileNotFoundError:
            payload = error_json("INDICE_NO_DISPONIBLE", "Genera el índice con python src/main.py antes de consultar.")
        except (ValidationError, OutputParserException):
            payload = error_json("SALIDA_INVALIDA", "La respuesta no cumple el esquema esperado. Intenta generar de nuevo.")
        except Exception:
            # No se publica el error crudo del proveedor: podría incluir credenciales o documentos.
            payload = error_json("GENERACION_FALLIDA", "Revisa GEMINI_API_KEY, los modelos de src/the_models.py, la conexión y la cuota de Gemini.")

    if args.salida:
        try:
            args.salida.parent.mkdir(parents=True, exist_ok=True)
            args.salida.write_text(payload + "\n", encoding="utf-8")
        except OSError:
            payload = error_json("ESCRITURA_FALLIDA", "No se pudo escribir el archivo de salida solicitado.")
            exit_code = 1
    print(payload)
    return exit_code


def error_json(code: str, message: str) -> str:
    return ErrorResponse(error=ErrorDetail(codigo=code, mensaje=message)).model_dump_json(indent=2)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
