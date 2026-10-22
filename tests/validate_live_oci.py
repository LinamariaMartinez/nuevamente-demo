"""Validación en vivo de OCI Object Storage (Hito 9 / F09).

Conecta con la tenencia real de OCI (us-ashburn-1), aprovisiona el Bucket Always Free
`nuevamente-contenidos-educativos` si no existe, sube los documentos originales de `data/`,
persiste un paquete educativo JSON con la estructura oficial de la consigna y verifica
su descarga e integridad.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from oci_storage import OCIStorageManager


def main() -> None:
    print("☁️  [Hito 9 / F09] Iniciando validación en vivo con OCI Object Storage...\n")

    manager = OCIStorageManager()
    bucket_info = manager.ensure_bucket_exists()

    estado_bucket = "Creado exitosamente" if bucket_info["created"] else "Verificado (ya existía)"
    print(f"✅ Bucket: {bucket_info['bucket']}")
    print(f"   Namespace: {bucket_info['namespace']}")
    print(f"   Estado: {estado_bucket}")
    print(f"   Storage Tier: {bucket_info['storage_tier']} (Capa Always Free)")
    print(f"   Acceso Público: {bucket_info['public_access_type']}\n")

    assert bucket_info["storage_tier"] == "Standard", "El bucket debe ser Standard Tier (Always Free)."
    assert bucket_info["public_access_type"] == "NoPublicAccess", "El bucket no debe ser público."

    # 1. Subir documentos originales de la carpeta data/
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "data"
    documentos = sorted(
        p for p in data_dir.iterdir() if p.suffix.lower() in {".pdf", ".md", ".txt"}
    )

    print("📄 Subiendo documentos técnicos originales a OCI Object Storage...")
    for doc_path in documentos:
        res_doc = manager.upload_document(doc_path, raise_on_error=True)
        assert res_doc.status_upload == "completado"
        print(f"   ✔ {doc_path.name} -> {res_doc.objeto_id} [{res_doc.status_upload}]")

    # 2. Subir un paquete educativo JSON completo según la consigna oficial
    print("\n📦 Persistiendo paquete educativo JSON adaptado en OCI Object Storage...")
    paquete_educativo = {
        "status": "exito",
        "metadatos": {
            "perfil_aplicado": "Principiante",
            "formato_generado": "Flashcards",
            "tiempo_estimado_estudio_minutos": 5,
            "conceptos_clave": ["VCN", "Subredes", "Internet Gateway", "Security Lists"],
        },
        "contenido_adaptado": {
            "titulo": "Dominando Redes en la Nube (VCN) desde Cero",
            "introduccion_contextualizada": (
                "Imagina la VCN como tu propio barrio privado y seguro dentro de la nube "
                "de Oracle, donde tú decides quién entra y quién sale."
            ),
            "items": [
                {
                    "frente": "¿Qué es una VCN en Oracle Cloud?",
                    "dorso": (
                        "Es tu red virtual privada y personalizada dentro de la nube de Oracle, "
                        "funcionando como la infraestructura de red de tu empresa."
                    ),
                    "pista_didactica": "Piensa en ella como el terreno cercado donde residen tus servidores.",
                },
                {
                    "frente": "¿Para qué sirven las Security Lists (Listas de Seguridad)?",
                    "dorso": (
                        "Son como guardias virtuales con listas de reglas que definen exactamente "
                        "qué tipo de tráfico de datos puede entrar o salir de tu red."
                    ),
                    "pista_didactica": "Reglas de entrada (ingress) y reglas de salida (egress).",
                },
            ],
        },
        "evaluacion_calidad": {
            "anclaje_fuente_score": 0.98,
            "claridad_pedagogica": "Alta",
            "observaciones": (
                "Lenguaje ajustado con analogías para público principiante, "
                "sin tecnicismos excesivos."
            ),
        },
    }

    paquete_final, oci_meta = manager.upload_educational_json(
        paquete_educativo,
        topic="VCN",
        profile="Principiante",
        output_format="Flashcards",
        sequence=1,
        raise_on_error=True,
    )

    assert oci_meta.status_upload == "completado"
    assert oci_meta.objeto_id == "contenido-vcn-principiante-flashcards-001.json"

    # 3. Verificar descarga e integridad desde OCI Object Storage
    raw_downloaded = manager.download_object(oci_meta.objeto_id)
    downloaded_json = json.loads(raw_downloaded.decode("utf-8"))
    assert downloaded_json["almacenamiento_oci"] == oci_meta.model_dump()

    objetos_en_bucket = manager.list_objects()
    print(f"\n📋 Objetos verificados en el bucket '{manager.bucket_name}' ({len(objetos_en_bucket)} total):")
    for nombre in objetos_en_bucket:
        print(f"   • {nombre}")

    print("\n✨ Respuesta JSON final con bloque `almacenamiento_oci` validado en la nube:")
    print(json.dumps(paquete_final, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
