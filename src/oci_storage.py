"""Integración con Oracle Cloud Infrastructure (OCI) Object Storage — Capa Always Free (Hito 9 / F09).

Cumple con los requisitos de la consigna oficial de NuevaMente:
1. Autenticación mediante OCI Python SDK (soporta ~/.oci/config y variables de entorno en .env).
2. Creación y verificación de Bucket estrictamente en la capa Always Free (Standard Tier, sin costos)
   y con acceso privado estricto (NoPublicAccess).
3. Persistencia de documentos técnicos originales (.pdf, .md, .txt) y paquetes educativos JSON.
4. Generación del bloque estructurado `almacenamiento_oci` con `bucket`, `objeto_id` y `status_upload`.
"""

from __future__ import annotations

import io
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

import the_keys

# --- Constantes de protección de la capa Always Free (20 GiB límite gratuito) ---
DEFAULT_BUCKET_NAME = "nuevamente-contenidos-educativos"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB por archivo para proteger la cuota Always Free
SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".md", ".txt"}

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}

STOPWORDS_ES = {
    "de", "la", "el", "en", "y", "a", "los", "las", "del", "un", "una",
    "para", "con", "por", "que", "es", "son", "sus", "como", "sobre", "al",
    "cuales", "cual", "principales", "introduccion", "arquitectura",
}


class OCIStorageError(Exception):
    """Error base para operaciones de almacenamiento en OCI."""


class OCIConfigurationError(OCIStorageError):
    """Credenciales o configuración de OCI ausentes o inválidas."""


class AlmacenamientoOCI(BaseModel):
    """Esquema oficial exigido por la consigna para el bloque `almacenamiento_oci`."""

    bucket: str = Field(..., min_length=1, description="Nombre del bucket en OCI Object Storage.")
    objeto_id: str = Field(..., min_length=1, description="Identificador del objeto en el bucket.")
    status_upload: Literal["completado", "error", "omitido"] = Field(
        ..., description="Estado de la subida a OCI Object Storage."
    )


def slugify(text: str, max_words: int = 3) -> str:
    """Convierte un texto en un identificador limpio en minúsculas separado por guiones."""
    normalized = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    tokens = re.findall(r"[a-z0-9]+", normalized.lower())
    filtered = [t for t in tokens if t not in STOPWORDS_ES and len(t) > 1]
    chosen = filtered[:max_words] if filtered else (tokens[:max_words] or ["documento"])
    return "-".join(chosen)


def build_content_object_id(
    topic: str,
    profile: str,
    output_format: str,
    sequence: int = 1,
) -> str:
    """Genera el `objeto_id` siguiendo el formato de la consigna.

    Ejemplo: `contenido-vcn-principiante-flashcards-001.json`
    """
    topic_slug = slugify(topic, max_words=2)
    profile_slug = slugify(profile, max_words=1)
    format_slug = slugify(output_format, max_words=1)
    seq_number = max(1, int(sequence))
    return f"contenido-{topic_slug}-{profile_slug}-{format_slug}-{seq_number:03d}.json"


def build_document_object_id(filename: str, prefix: str = "documentos") -> str:
    """Genera el `objeto_id` normalizado para un documento técnico original."""
    path = Path(filename)
    ext = path.suffix.lower()
    stem_slug = slugify(path.stem, max_words=5)
    clean_name = f"{stem_slug}{ext}" if ext else stem_slug
    return f"{prefix}/{clean_name}" if prefix else clean_name


def load_oci_config(
    config_file: str | Path | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Carga y valida la configuración de OCI desde variables de entorno o `~/.oci/config`."""
    try:
        import oci
    except ImportError as exc:
        raise OCIConfigurationError("El paquete 'oci' no está instalado en el entorno.") from exc

    user = os.getenv("OCI_USER_OCID") or the_keys.OCI_USER_OCID
    tenancy = os.getenv("OCI_TENANCY_OCID") or the_keys.OCI_TENANCY_OCID
    fingerprint = os.getenv("OCI_FINGERPRINT") or the_keys.OCI_FINGERPRINT
    key_file = os.getenv("OCI_KEY_FILE") or the_keys.OCI_KEY_FILE
    region = os.getenv("OCI_REGION") or the_keys.OCI_REGION or "us-ashburn-1"

    if user and tenancy and fingerprint and key_file:
        expanded_key = str(Path(key_file).expanduser().resolve())
        config = {
            "user": user.strip(),
            "tenancy": tenancy.strip(),
            "fingerprint": fingerprint.strip(),
            "key_file": expanded_key,
            "region": region.strip(),
        }
        pass_phrase = os.getenv("OCI_KEY_PASS_PHRASE")
        if pass_phrase:
            config["pass_phrase"] = pass_phrase
        try:
            oci.config.validate_config(config)
        except Exception as exc:
            raise OCIConfigurationError(f"Configuración OCI por variables de entorno inválida: {exc}") from exc
        return config

    resolved_file = Path(
        config_file or os.getenv("OCI_CONFIG_FILE") or the_keys.OCI_CONFIG_FILE
    ).expanduser()
    resolved_profile = profile or os.getenv("OCI_CONFIG_PROFILE") or the_keys.OCI_CONFIG_PROFILE or "DEFAULT"

    if not resolved_file.is_file():
        raise OCIConfigurationError(
            f"No se encontró configuración OCI en {resolved_file} ni variables OCI_* completas en .env."
        )

    try:
        config = oci.config.from_file(file_location=str(resolved_file), profile_name=resolved_profile)
        oci.config.validate_config(config)
        return dict(config)
    except Exception as exc:
        raise OCIConfigurationError(f"Error al leer el archivo de configuración OCI ({resolved_file}): {exc}") from exc


class OCIStorageManager:
    """Gestor de persistencia en OCI Object Storage (Always Free)."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        config: dict[str, Any] | None = None,
        bucket_name: str | None = None,
        namespace: str | None = None,
        compartment_id: str | None = None,
    ) -> None:
        self.bucket_name = (
            bucket_name
            or os.getenv("OCI_BUCKET_NAME")
            or the_keys.OCI_BUCKET_NAME
            or DEFAULT_BUCKET_NAME
        )
        self._config = config
        self._client = client
        self._namespace = namespace or os.getenv("OCI_NAMESPACE") or the_keys.OCI_NAMESPACE
        self._compartment_id = (
            compartment_id
            or os.getenv("OCI_COMPARTMENT_OCID")
            or the_keys.OCI_COMPARTMENT_OCID
        )
        self._bucket_verified: bool = False

    @property
    def config(self) -> dict[str, Any]:
        if self._config is None:
            self._config = load_oci_config()
        return self._config

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import oci
            except ImportError as exc:
                raise OCIConfigurationError("El paquete 'oci' no está instalado.") from exc
            self._client = oci.object_storage.ObjectStorageClient(self.config)
        return self._client

    @property
    def namespace(self) -> str:
        if not self._namespace:
            response = self.client.get_namespace()
            self._namespace = response.data
        return self._namespace

    @property
    def compartment_id(self) -> str:
        if not self._compartment_id:
            tenancy = self.config.get("tenancy")
            if not tenancy:
                raise OCIConfigurationError(
                    "No se especificó OCI_COMPARTMENT_OCID ni 'tenancy' en la configuración."
                )
            self._compartment_id = tenancy
        return self._compartment_id

    def ensure_bucket_exists(self, force_refresh: bool = False) -> dict[str, Any]:
        """Verifica que el bucket exista o lo crea garantizando parámetros Always Free y acceso privado."""
        if self._bucket_verified and not force_refresh:
            return {
                "bucket": self.bucket_name,
                "namespace": self.namespace,
                "created": False,
                "storage_tier": "Standard",
                "public_access_type": "NoPublicAccess",
            }

        namespace = self.namespace
        try:
            response = self.client.get_bucket(
                namespace_name=namespace,
                bucket_name=self.bucket_name,
            )
            bucket = response.data
            storage_tier = getattr(bucket, "storage_tier", "Standard")
            if storage_tier and storage_tier != "Standard":
                raise OCIStorageError(
                    f"El bucket '{self.bucket_name}' tiene storage_tier='{storage_tier}'. "
                    "Solo se permite 'Standard' para cumplir con la capa Always Free."
                )
            public_access_type = getattr(bucket, "public_access_type", "NoPublicAccess")
            if public_access_type and public_access_type != "NoPublicAccess":
                raise OCIStorageError(
                    f"El bucket '{self.bucket_name}' tiene public_access_type='{public_access_type}'. "
                    "Solo se permite 'NoPublicAccess' para evitar la exposición pública de documentos."
                )
            self._bucket_verified = True
            return {
                "bucket": self.bucket_name,
                "namespace": namespace,
                "created": False,
                "storage_tier": storage_tier,
                "public_access_type": public_access_type,
            }
        except OCIStorageError:
            raise
        except Exception as exc:
            status = getattr(exc, "status", None)
            if status != 404:
                raise OCIStorageError(f"Error al verificar el bucket '{self.bucket_name}': {exc}") from exc

        # Creación del bucket con restricciones estrictas de la capa Always Free (0 costo)
        try:
            from oci.object_storage.models import CreateBucketDetails

            details = CreateBucketDetails(
                name=self.bucket_name,
                compartment_id=self.compartment_id,
                storage_tier=CreateBucketDetails.STORAGE_TIER_STANDARD,
                public_access_type=CreateBucketDetails.PUBLIC_ACCESS_TYPE_NO_PUBLIC_ACCESS,
                auto_tiering="Disabled",
                object_events_enabled=False,
                versioning="Disabled",
                freeform_tags={
                    "project": "NuevaMente",
                    "hackathon": "ONE-G10-Equipo30",
                    "tier": "AlwaysFree",
                },
            )
        except ImportError:
            # Permite pruebas unitarias sin importar modelos del SDK si se inyecta un cliente mock
            details = {
                "name": self.bucket_name,
                "compartment_id": self.compartment_id,
                "storage_tier": "Standard",
                "public_access_type": "NoPublicAccess",
                "auto_tiering": "Disabled",
                "object_events_enabled": False,
                "versioning": "Disabled",
            }

        try:
            response = self.client.create_bucket(
                namespace_name=namespace,
                create_bucket_details=details,
            )
            bucket = getattr(response, "data", None)
            self._bucket_verified = True
            return {
                "bucket": self.bucket_name,
                "namespace": namespace,
                "created": True,
                "storage_tier": getattr(bucket, "storage_tier", "Standard"),
                "public_access_type": getattr(bucket, "public_access_type", "NoPublicAccess"),
            }
        except Exception as exc:
            raise OCIStorageError(f"No se pudo crear el bucket '{self.bucket_name}': {exc}") from exc

    def upload_document(
        self,
        source: str | Path | bytes,
        *,
        filename: str | None = None,
        object_id: str | None = None,
        prefix: str = "documentos",
        raise_on_error: bool = False,
    ) -> AlmacenamientoOCI:
        """Sube un documento técnico original (.pdf, .md, .txt) al bucket de OCI."""
        if isinstance(source, (str, Path)):
            file_path = Path(source)
            if not file_path.is_file():
                if raise_on_error:
                    raise FileNotFoundError(f"No existe el archivo: {file_path}")
                return AlmacenamientoOCI(
                    bucket=self.bucket_name,
                    objeto_id=object_id or file_path.name,
                    status_upload="error",
                )
            raw_bytes = file_path.read_bytes()
            inferred_name = filename or file_path.name
        elif isinstance(source, (bytes, bytearray)):
            raw_bytes = bytes(source)
            inferred_name = filename or "documento.txt"
        else:
            raise TypeError("source debe ser una ruta (str/Path) o bytes.")

        ext = Path(inferred_name).suffix.lower()
        target_object_id = object_id or build_document_object_id(inferred_name, prefix=prefix)

        if ext not in SUPPORTED_DOCUMENT_EXTENSIONS:
            if raise_on_error:
                raise ValueError(f"Extensión no soportada para OCI: {ext}")
            return AlmacenamientoOCI(
                bucket=self.bucket_name,
                objeto_id=target_object_id,
                status_upload="error",
            )

        if not raw_bytes or len(raw_bytes) > MAX_UPLOAD_BYTES:
            if raise_on_error:
                raise ValueError(
                    f"Tamaño inválido ({len(raw_bytes)} bytes). "
                    f"Debe estar entre 1 byte y {MAX_UPLOAD_BYTES} bytes."
                )
            return AlmacenamientoOCI(
                bucket=self.bucket_name,
                objeto_id=target_object_id,
                status_upload="error",
            )

        # Validación del bucket antes de subir:
        # Asegura que el bucket existe, es Standard y tiene NoPublicAccess ANTES de llamar a put_object
        try:
            self.ensure_bucket_exists()
        except Exception as exc:
            if raise_on_error:
                raise OCIStorageError(f"Validación de bucket fallida para '{self.bucket_name}': {exc}") from exc
            return AlmacenamientoOCI(
                bucket=self.bucket_name,
                objeto_id=target_object_id,
                status_upload="error",
            )

        content_type = MIME_TYPES.get(ext, "application/octet-stream")
        try:
            self.client.put_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=target_object_id,
                put_object_body=io.BytesIO(raw_bytes),
                content_length=len(raw_bytes),
                content_type=content_type,
            )
            return AlmacenamientoOCI(
                bucket=self.bucket_name,
                objeto_id=target_object_id,
                status_upload="completado",
            )
        except Exception as exc:
            if raise_on_error:
                raise OCIStorageError(f"Fallo al subir documento '{target_object_id}': {exc}") from exc
            return AlmacenamientoOCI(
                bucket=self.bucket_name,
                objeto_id=target_object_id,
                status_upload="error",
            )

    def upload_educational_json(
        self,
        payload: dict[str, Any] | BaseModel | str,
        *,
        object_id: str | None = None,
        topic: str | None = None,
        profile: str | None = None,
        output_format: str | None = None,
        sequence: int = 1,
        raise_on_error: bool = False,
    ) -> tuple[dict[str, Any], AlmacenamientoOCI]:
        """Persiste el paquete educativo JSON en OCI y le inyecta `almacenamiento_oci`."""
        if isinstance(payload, BaseModel):
            data = payload.model_dump(mode="json")
        elif isinstance(payload, str):
            data = json.loads(payload)
        elif isinstance(payload, dict):
            data = dict(payload)
        else:
            raise TypeError("payload debe ser dict, BaseModel o JSON string.")

        metadatos = data.get("metadatos") if isinstance(data.get("metadatos"), dict) else {}
        contenido = data.get("contenido_adaptado") if isinstance(data.get("contenido_adaptado"), dict) else {}

        resolved_topic = (
            topic
            or metadatos.get("tema")
            or (metadatos.get("conceptos_clave") or [None])[0]
            or contenido.get("titulo")
            or "contenido"
        )
        resolved_profile = profile or metadatos.get("perfil_aplicado") or "principiante"
        resolved_format = output_format or metadatos.get("formato_generado") or "flashcards"

        target_object_id = object_id or build_content_object_id(
            topic=str(resolved_topic),
            profile=str(resolved_profile),
            output_format=str(resolved_format),
            sequence=sequence,
        )

        # Preparamos el bloque almacenamiento_oci con estado 'completado' antes de serializar
        # para que el archivo JSON almacenado en el bucket contenga el registro exacto.
        oci_record = AlmacenamientoOCI(
            bucket=self.bucket_name,
            objeto_id=target_object_id,
            status_upload="completado",
        )
        data["almacenamiento_oci"] = oci_record.model_dump()

        raw_bytes = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            oci_record = AlmacenamientoOCI(
                bucket=self.bucket_name,
                objeto_id=target_object_id,
                status_upload="error",
            )
            data["almacenamiento_oci"] = oci_record.model_dump()
            if raise_on_error:
                raise ValueError(f"El JSON excede el tamaño máximo permitido ({MAX_UPLOAD_BYTES} bytes).")
            return data, oci_record

        # Validación del bucket antes de subir:
        # Asegura que el bucket existe, es Standard y tiene NoPublicAccess ANTES de llamar a put_object
        try:
            self.ensure_bucket_exists()
        except Exception as exc:
            oci_record = AlmacenamientoOCI(
                bucket=self.bucket_name,
                objeto_id=target_object_id,
                status_upload="error",
            )
            data["almacenamiento_oci"] = oci_record.model_dump()
            if raise_on_error:
                raise OCIStorageError(f"Validación de bucket fallida para '{self.bucket_name}': {exc}") from exc
            return data, oci_record

        try:
            self.client.put_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=target_object_id,
                put_object_body=io.BytesIO(raw_bytes),
                content_length=len(raw_bytes),
                content_type=MIME_TYPES[".json"],
            )
            return data, oci_record
        except Exception as exc:
            oci_record = AlmacenamientoOCI(
                bucket=self.bucket_name,
                objeto_id=target_object_id,
                status_upload="error",
            )
            data["almacenamiento_oci"] = oci_record.model_dump()
            if raise_on_error:
                raise OCIStorageError(f"Fallo al subir JSON '{target_object_id}': {exc}") from exc
            return data, oci_record

    def download_object(self, object_id: str) -> bytes:
        """Descarga los bytes de un objeto almacenado en el bucket de OCI."""
        try:
            response = self.client.get_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=object_id,
            )
            return response.data.content
        except Exception as exc:
            raise OCIStorageError(f"No se pudo descargar el objeto '{object_id}': {exc}") from exc

    def list_objects(self, prefix: str = "") -> list[str]:
        """Lista los nombres de los objetos almacenados en el bucket."""
        try:
            response = self.client.list_objects(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                prefix=prefix or None,
            )
            objects = getattr(response.data, "objects", []) or []
            return [obj.name for obj in objects]
        except Exception as exc:
            raise OCIStorageError(f"Error al listar objetos del bucket '{self.bucket_name}': {exc}") from exc
