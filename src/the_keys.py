import os
from dotenv import load_dotenv

from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")