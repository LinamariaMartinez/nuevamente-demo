"""Errores esperados del pipeline de generación."""


class NoContextError(ValueError):
    """La búsqueda no recuperó texto con el que fundamentar el contenido."""


class ConfigurationError(ValueError):
    """Falta una configuración necesaria para llamar al proveedor."""
