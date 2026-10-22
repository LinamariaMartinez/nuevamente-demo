import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from oci_storage import (
    DEFAULT_BUCKET_NAME,
    MAX_UPLOAD_BYTES,
    AlmacenamientoOCI,
    OCIStorageError,
    OCIStorageManager,
    build_content_object_id,
    build_document_object_id,
)


class FakeNotFoundError(Exception):
    def __init__(self):
        super().__init__("BucketNotFound")
        self.status = 404


class FakeOCIClient:
    def __init__(
        self,
        *,
        bucket_exists: bool = True,
        storage_tier: str | None = "Standard",
        public_access_type: str | None = "NoPublicAccess",
        auto_tiering: str | None = "Disabled",
        object_events_enabled: bool = False,
        versioning: str | None = "Disabled",
        fail_put: bool = False,
    ):
        self.bucket_exists = bucket_exists
        self.storage_tier = storage_tier
        self.public_access_type = public_access_type
        self.auto_tiering = auto_tiering
        self.object_events_enabled = object_events_enabled
        self.versioning = versioning
        self.fail_put = fail_put
        self.created_buckets = []
        self.uploaded_objects = {}

    def get_namespace(self):
        return SimpleNamespace(data="test_namespace")

    def get_bucket(self, namespace_name, bucket_name):
        if not self.bucket_exists:
            raise FakeNotFoundError()
        return SimpleNamespace(
            data=SimpleNamespace(
                name=bucket_name,
                storage_tier=self.storage_tier,
                public_access_type=self.public_access_type,
                auto_tiering=self.auto_tiering,
                object_events_enabled=self.object_events_enabled,
                versioning=self.versioning,
            )
        )

    def create_bucket(self, namespace_name, create_bucket_details):
        self.created_buckets.append((namespace_name, create_bucket_details))
        self.bucket_exists = True
        return SimpleNamespace(
            data=SimpleNamespace(
                name=getattr(create_bucket_details, "name", DEFAULT_BUCKET_NAME),
                storage_tier="Standard",
                public_access_type="NoPublicAccess",
                auto_tiering="Disabled",
                object_events_enabled=False,
                versioning="Disabled",
            )
        )

    def put_object(
        self,
        namespace_name,
        bucket_name,
        object_name,
        put_object_body,
        content_length=None,
        content_type=None,
    ):
        if self.fail_put:
            raise RuntimeError("Simulated OCI network error")
        raw = put_object_body.read()
        self.uploaded_objects[object_name] = {
            "namespace": namespace_name,
            "bucket": bucket_name,
            "content": raw,
            "content_length": content_length,
            "content_type": content_type,
        }
        return SimpleNamespace(status=200)

    def get_object(self, namespace_name, bucket_name, object_name):
        if object_name not in self.uploaded_objects:
            raise FakeNotFoundError()
        raw = self.uploaded_objects[object_name]["content"]
        return SimpleNamespace(data=SimpleNamespace(content=raw))

    def list_objects(self, namespace_name, bucket_name, prefix=None):
        names = [
            SimpleNamespace(name=k)
            for k in sorted(self.uploaded_objects)
            if not prefix or k.startswith(prefix)
        ]
        return SimpleNamespace(data=SimpleNamespace(objects=names))


class OCIStorageTests(unittest.TestCase):
    def test_object_id_generation(self):
        obj_id = build_content_object_id("VCN", "Principiante", "Flashcards", sequence=1)
        self.assertEqual(obj_id, "contenido-vcn-principiante-flashcards-001.json")

        doc_id = build_document_object_id("arquitectura_redes_vcn_oci.md")
        self.assertEqual(doc_id, "documentos/redes-vcn-oci.md")

    def test_create_always_free_bucket(self):
        client = FakeOCIClient(bucket_exists=False)
        manager = OCIStorageManager(
            client=client,
            config={"tenancy": "ocid1.tenancy.oc1..test"},
            bucket_name=DEFAULT_BUCKET_NAME,
        )
        info = manager.ensure_bucket_exists()
        self.assertTrue(info["created"])
        self.assertEqual(info["bucket"], DEFAULT_BUCKET_NAME)
        self.assertEqual(info["storage_tier"], "Standard")
        self.assertEqual(len(client.created_buckets), 1)

        _, details = client.created_buckets[0]
        tier = details.get("storage_tier") if isinstance(details, dict) else details.storage_tier
        access = (
            details.get("public_access_type")
            if isinstance(details, dict)
            else details.public_access_type
        )
        auto_tiering = (
            details.get("auto_tiering") if isinstance(details, dict) else details.auto_tiering
        )
        events = (
            details.get("object_events_enabled")
            if isinstance(details, dict)
            else details.object_events_enabled
        )
        versioning = (
            details.get("versioning") if isinstance(details, dict) else details.versioning
        )
        self.assertEqual(tier, "Standard")
        self.assertEqual(access, "NoPublicAccess")
        self.assertEqual(auto_tiering, "Disabled")
        self.assertFalse(events)
        self.assertEqual(versioning, "Disabled")

    def test_reject_invalid_bucket_policy(self):
        casos = [
            ({"storage_tier": "Archive"}, "storage_tier='Archive'"),
            ({"storage_tier": None}, "storage_tier='None'"),
            ({"public_access_type": "ObjectRead"}, "public_access_type='ObjectRead'"),
            ({"public_access_type": "ObjectReadWithoutList"}, "public_access_type='ObjectReadWithoutList'"),
            ({"public_access_type": None}, "public_access_type='None'"),
            ({"auto_tiering": "InfrequentAccess"}, "auto_tiering='InfrequentAccess'"),
            ({"object_events_enabled": True}, "eventos de objetos"),
            ({"versioning": "Enabled"}, "versioning='Enabled'"),
        ]
        for kwargs, fragmento in casos:
            with self.subTest(**kwargs):
                client = FakeOCIClient(bucket_exists=True, **kwargs)
                manager = OCIStorageManager(
                    client=client,
                    config={"tenancy": "ocid1.tenancy.oc1..test"},
                )
                with self.assertRaises(OCIStorageError) as ctx:
                    manager.ensure_bucket_exists()
                self.assertIn(fragmento, str(ctx.exception))

    def test_block_upload_to_public_bucket(self):
        for public_type in ("ObjectRead", "ObjectReadWithoutList"):
            with self.subTest(public_type=public_type):
                client = FakeOCIClient(bucket_exists=True, public_access_type=public_type)
                manager = OCIStorageManager(
                    client=client,
                    config={"tenancy": "ocid1.tenancy.oc1..test"},
                )
                res_doc = manager.upload_document(b"# Titulo", filename="doc.md", raise_on_error=False)
                self.assertEqual(res_doc.status_upload, "error")

                sample = {"status": "exito", "metadatos": {"conceptos_clave": ["VCN"]}}
                _, res_json = manager.upload_educational_json(sample, raise_on_error=False)
                self.assertEqual(res_json.status_upload, "error")

                with self.assertRaises(OCIStorageError):
                    manager.upload_document(b"# Titulo", filename="doc.md", raise_on_error=True)
                with self.assertRaises(OCIStorageError):
                    manager.upload_educational_json(sample, raise_on_error=True)

                self.assertEqual(len(client.uploaded_objects), 0)

    def test_upload_document_validation(self):
        client = FakeOCIClient()
        manager = OCIStorageManager(
            client=client,
            config={"tenancy": "ocid1.tenancy.oc1..test"},
            bucket_name=DEFAULT_BUCKET_NAME,
        )

        with tempfile.TemporaryDirectory() as tmp:
            md_file = Path(tmp) / "manual_vcn.md"
            md_file.write_text("# Redes VCN\nContenido técnico.", encoding="utf-8")

            res = manager.upload_document(md_file)
            self.assertEqual(res.status_upload, "completado")
            self.assertEqual(res.bucket, DEFAULT_BUCKET_NAME)
            self.assertEqual(res.objeto_id, "documentos/manual-vcn.md")
            self.assertIn("documentos/manual-vcn.md", client.uploaded_objects)

        bad_ext = manager.upload_document(b"contenido", filename="script.exe")
        self.assertEqual(bad_ext.status_upload, "error")

        empty_res = manager.upload_document(b"", filename="vacio.txt")
        self.assertEqual(empty_res.status_upload, "error")

        oversized = b"a" * (MAX_UPLOAD_BYTES + 1)
        over_res = manager.upload_document(oversized, filename="grande.pdf")
        self.assertEqual(over_res.status_upload, "error")

        bad_path = manager.upload_document(b"contenido", filename="doc.md", object_id="../escape.md")
        self.assertEqual(bad_path.status_upload, "error")

    def test_upload_educational_json(self):
        client = FakeOCIClient()
        manager = OCIStorageManager(
            client=client,
            config={"tenancy": "ocid1.tenancy.oc1..test"},
            bucket_name="nuevamente-contenidos-educativos",
        )
        sample_response = {
            "status": "exito",
            "metadatos": {
                "perfil_aplicado": "Principiante",
                "formato_generado": "Flashcards",
                "tiempo_estimado_estudio_minutos": 5,
                "conceptos_clave": ["VCN", "Subredes"],
            },
            "contenido_adaptado": {
                "titulo": "Dominando Redes en la Nube (VCN) desde Cero",
                "introduccion_contextualizada": "Imagina la VCN como tu propio barrio privado.",
                "items": [
                    {
                        "frente": "¿Qué es una VCN?",
                        "dorso": "Red virtual privada en OCI.",
                        "pista_didactica": "Terreno cercado.",
                    }
                ],
            },
            "evaluacion_calidad": {
                "anclaje_fuente_score": 0.98,
                "claridad_pedagogica": "Alta",
                "observaciones": "Lenguaje ajustado.",
            },
        }

        enriched, oci_info = manager.upload_educational_json(sample_response, sequence=1)
        self.assertIsInstance(oci_info, AlmacenamientoOCI)
        self.assertEqual(
            enriched["almacenamiento_oci"],
            {
                "bucket": "nuevamente-contenidos-educativos",
                "objeto_id": "contenido-vcn-principiante-flashcards-001.json",
                "status_upload": "completado",
            },
        )

        stored_bytes = manager.download_object("contenido-vcn-principiante-flashcards-001.json")
        stored_json = json.loads(stored_bytes.decode("utf-8"))
        self.assertEqual(
            stored_json["almacenamiento_oci"]["status_upload"],
            "completado",
        )
        self.assertEqual(
            manager.list_objects(prefix="contenido-"),
            ["contenido-vcn-principiante-flashcards-001.json"],
        )

    def test_upload_network_error(self):
        client = FakeOCIClient(fail_put=True)
        manager = OCIStorageManager(
            client=client,
            config={"tenancy": "ocid1.tenancy.oc1..test"},
        )
        enriched, oci_info = manager.upload_educational_json(
            {"status": "exito", "metadatos": {"conceptos_clave": ["VCN"]}},
            raise_on_error=False,
        )
        self.assertEqual(oci_info.status_upload, "error")
        self.assertEqual(enriched["almacenamiento_oci"]["status_upload"], "error")

        with self.assertRaises(OCIStorageError):
            manager.upload_educational_json(
                {"status": "exito", "metadatos": {"conceptos_clave": ["VCN"]}},
                raise_on_error=True,
            )


if __name__ == "__main__":
    unittest.main()
