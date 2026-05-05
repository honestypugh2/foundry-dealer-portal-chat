"""Application configuration loaded from .env via os.getenv()."""

import os
from dotenv import load_dotenv

load_dotenv()


def env(key: str, default: str = "") -> str:
    """Read an environment variable."""
    return os.getenv(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


def env_int(key: str, default: int = 0) -> int:
    """Read an integer environment variable."""
    return int(os.getenv(key, str(default)))
