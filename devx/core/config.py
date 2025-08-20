from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
ENV = dotenv_values(ROOT / ".env") if (ROOT / ".env").exists() else {}

def get(key: str, default=None):
    return ENV.get(key, default)
