import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configuración de Oracle Cloud Infrastructure (OCI Object Storage - Always Free)
OCI_CONFIG_FILE = os.getenv("OCI_CONFIG_FILE", str(Path.home() / ".oci" / "config"))
OCI_CONFIG_PROFILE = os.getenv("OCI_CONFIG_PROFILE", "DEFAULT")
OCI_USER_OCID = os.getenv("OCI_USER_OCID")
OCI_TENANCY_OCID = os.getenv("OCI_TENANCY_OCID")
OCI_FINGERPRINT = os.getenv("OCI_FINGERPRINT")
OCI_KEY_FILE = os.getenv("OCI_KEY_FILE")
OCI_REGION = os.getenv("OCI_REGION", "us-ashburn-1")
OCI_NAMESPACE = os.getenv("OCI_NAMESPACE")
OCI_COMPARTMENT_OCID = os.getenv("OCI_COMPARTMENT_OCID")
OCI_BUCKET_NAME = os.getenv("OCI_BUCKET_NAME", "nuevamente-contenidos-educativos")
