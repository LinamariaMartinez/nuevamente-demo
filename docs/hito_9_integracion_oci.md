# Hito 9 (F09): Integración con OCI Object Storage — Capa Always Free

Base: `develop` (Hitos 1, 2 y 3 consolidados). Implementa la persistencia en **Oracle Cloud Infrastructure (OCI) Object Storage** requerida por la consigna del Hackathon ONE G10.

## 1. Cumplimiento de la Capa Always Free y Protección de Costos

El módulo [`src/oci_storage.py`](../src/oci_storage.py) aplica salvaguardas estrictas para garantizar costo cero en la cuenta de OCI:

- **Storage Tier (`Standard`)**: `ensure_bucket_exists()` aprovisiona el bucket exclusivamente en `Standard` (20 GiB gratuitos en Always Free) y rechaza buckets configurados en otros niveles como `Archive`.
- **Privacidad (`NoPublicAccess`)**: El bucket se crea sin acceso público para proteger la propiedad intelectual y evitar tráfico de salida no autorizado.
- **Sin servicios adicionales de pago**: Se deshabilitan explícitamente `auto_tiering="Disabled"`, `object_events_enabled=False` y `versioning="Disabled"`.
- **Límite por objeto (`MAX_UPLOAD_BYTES = 10 MiB`)**: Cada documento o paquete JSON se valida antes de la subida para evitar agotar accidentalmente la cuota de 20 GiB.

## 2. Arquitectura y Contrato de Salida (`almacenamiento_oci`)

El modelo Pydantic `AlmacenamientoOCI` genera exactamente el bloque especificado en la consigna oficial:

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
   - Verifica la existencia del bucket (`nuevamente-contenidos-educativos` por defecto) en el namespace de la tenencia o lo crea automáticamente en la capa Always Free.
3. **`OCIStorageManager.upload_document()`**:
   - Sube los documentos técnicos originales (`.pdf`, `.md`, `.txt`) bajo el prefijo `documentos/` y devuelve su `AlmacenamientoOCI`.
4. **`OCIStorageManager.upload_educational_json()`**:
   - Genera un `objeto_id` semántico (`contenido-{tema}-{perfil}-{formato}-{secuencia}.json`), inyecta el bloque `almacenamiento_oci` en el paquete educativo y persiste el JSON en UTF-8 dentro del bucket.
5. **`OCIStorageManager.download_object()` y `list_objects()`**:
   - Permiten recuperar y auditar los artefactos almacenados en el bucket.

## 3. Integración con los demás módulos del proyecto

- **Ingesta (`src/main.py`)**: Al procesar los archivos de `data/`, respalda automáticamente los documentos originales en OCI Object Storage si las credenciales están configuradas (o informa su omisión sin interrumpir el flujo local).
- **Estado del Grafo (`src/state.py`)**: `AgentState` incorpora el campo `almacenamiento_oci: dict`.
- ** Integración con Backend FastAPI (F06 / F08)**:
  - En `POST /api/v1/documentos`: llamar a `OCIStorageManager().upload_document(raw, filename=name)`.
  - En `POST /api/v1/contenidos` (o en `finalize_node` de `src/output.py`): llamar a `OCIStorageManager().upload_educational_json(response_dict)` para adjuntar `almacenamiento_oci` a `EducationalResponse`.

## 4. Ejecución y Pruebas

### Pruebas unitarias offline (CI / sin credenciales ni red)

```bash
python -m unittest discover -s tests -p test_oci_storage.py -v
```

Verifica generación de identificadores según consigna, aprovisionamiento del bucket con parámetros Always Free, rechazo de tiers no gratuitos, validación de extensiones y tamaños (10 MiB), inyección del bloque `almacenamiento_oci` y manejo resiliente de fallos de red.

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
