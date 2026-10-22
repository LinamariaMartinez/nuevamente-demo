# Hito 9 (F09): Integración con OCI Object Storage — Capa Always Free

Base: `feature/backend-integracion-f06-f08` (Hitos 1 al 8 consolidados). Implementa la persistencia en **Oracle Cloud Infrastructure (OCI) Object Storage** requerida por la consigna del Hackathon ONE G10.

## 1. Cumplimiento de la Capa Always Free y Protección de Costos

El módulo [`src/oci_storage.py`](../src/oci_storage.py) aplica salvaguardas estrictas para garantizar costo cero en la cuenta de OCI:

- **Storage Tier (`Standard`)**: `ensure_bucket_exists()` aprovisiona el bucket exclusivamente en `Standard` (20 GiB gratuitos en Always Free) y rechaza buckets configurados en otros niveles como `Archive`.
- **Privacidad (`NoPublicAccess`)**: El bucket se crea y valida sin acceso público (`NoPublicAccess`) antes de cada subida para proteger la propiedad intelectual y evitar tráfico de salida no autorizado.
- **Revalidación periódica (TTL = 5 min)**: Para ejecuciones continuas en el servidor FastAPI, la verificación del bucket expira automáticamente tras `DEFAULT_BUCKET_VERIFY_TTL_SECONDS` (300 s), detectando cambios de políticas en caliente.
- **Sin servicios adicionales de pago**: Se deshabilitan explícitamente `auto_tiering="Disabled"`, `object_events_enabled=False` y `versioning="Disabled"`.
- **Límite por objeto (`MAX_UPLOAD_BYTES = 10 MiB`)**: Cada documento o paquete JSON se valida antes de la subida para evitar agotar accidentalmente la cuota de 20 GiB.

## 2. Arquitectura y Contrato de Salida (`almacenamiento_oci`)

El modelo Pydantic `AlmacenamientoOCI` genera exactamente el bloque especificado en la consigna oficial dentro del artefacto JSON persistido en la nube:

```json
"almacenamiento_oci": {
  "bucket": "nuevamente-contenidos-educativos",
  "objeto_id": "contenido-vcn-principiante-flashcards-001.json",
  "status_upload": "completado"
}
```

### Componentes principales en `src/oci_storage.py`

1. **`load_oci_config()`**:
   - Soporta credenciales por variables de entorno en `.env` (`OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_FINGERPRINT`, `OCI_KEY_FILE`, `OCI_REGION`) o mediante el archivo estándar `~/.oci/config`.
2. **`OCIStorageManager.ensure_bucket_exists()`**:
   - Verifica la existencia y políticas de privacidad/tier del bucket (`nuevamente-contenidos-educativos` por defecto) con caché TTL o lo crea automáticamente en la capa Always Free.
3. **`OCIStorageManager.upload_document()`**:
   - Sube los documentos técnicos originales (`.pdf`, `.md`, `.txt`) bajo el prefijo `documentos/` y devuelve su `AlmacenamientoOCI` (`completado`, `error` u `omitido` si se ejecuta en local sin credenciales).
4. **`OCIStorageManager.upload_educational_json()`**:
   - Genera un `objeto_id` semántico único (`contenido-{tema}-{perfil}-{formato}-{id|secuencia}.json`), inyecta el bloque `almacenamiento_oci` en el paquete educativo y persiste el JSON en UTF-8 dentro del bucket.
5. **`OCIStorageManager.download_object()` y `list_objects()`**:
   - Permiten recuperar y auditar los artefactos almacenados en el bucket.

## 3. Integración con el Backend FastAPI (`api/`) e Ingesta (`src/main.py`)

- **Rutas de Documentos (`api/routes/documentos.py`)**:
  - `POST /api/v1/documentos` y `POST /api/v1/documentos/texto`: tras indexar y guardar el documento en SQLite, respalda el archivo original en OCI Object Storage bajo `documentos/`.
- **Rutas de Contenidos (`api/routes/contenidos.py`)**:
  - `POST /api/v1/contenidos`: cuando el material generado supera el umbral de calidad (`status == "exito"`), persiste el paquete JSON validado en OCI Object Storage. Si queda en `requiere_revision`, espera a la revisión del administrador.
  - `POST /api/v1/contenidos/{id}/aprobar`: cuando el administrador aprueba un material pendiente de revisión, el paquete JSON aprobado se respalda en OCI Object Storage.
- **Degradación elegante en entorno local**:
  - Si el backend corre localmente sin credenciales de OCI configuradas (`OCIConfigurationError`), las rutas devuelven `status_upload="omitido"` internamente y la API opera con normalidad sobre SQLite sin interrumpir al usuario.
- **Ingesta por CLI (`src/main.py`)**: Al procesar los archivos de `data/`, respalda automáticamente los documentos originales en OCI Object Storage.

## 4. Ejecución y Pruebas

### Pruebas unitarias y de integración offline (CI / sin credenciales ni red)

```bash
python -m unittest discover -s tests -p test_oci_storage.py -v
python -m pytest tests/test_api_integracion.py -v
```

### Validación en vivo contra OCI Object Storage (`us-ashburn-1`)

Con `~/.oci/config` o variables `OCI_*` configuradas en `.env`:

```bash
python tests/validate_live_oci.py
```

### Validación realizada el 17 de octubre de 2026

- **Región**: `us-ashburn-1` (US East - Ashburn)
- **Namespace**: `idekzk1r5rzu`
- **Bucket**: `nuevamente-contenidos-educativos` (`Standard`, `NoPublicAccess`)
- **Objetos verificados en la nube**:
  - `documentos/redes-vcn-oci.md` (`completado`)
  - `documentos/politica-reembolsos-viajes-gastos.pdf` (`completado`)
  - `contenido-vcn-principiante-flashcards-001.json` (`completado`)
