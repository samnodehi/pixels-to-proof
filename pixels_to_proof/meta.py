"""Meta Model API access: key loading and clients. The key is never logged."""
from __future__ import annotations

import os
from pathlib import Path

from openai import AsyncOpenAI, OpenAI

BASE_URL = os.environ.get("MODEL_BASE_URL", "https://api.meta.ai/v1")
SPARK = os.environ.get("P2P_SPARK_MODEL", "muse-spark-1.3")
SAM = "sam-3.1"


def api_key() -> str:
    """MODEL_API_KEY from the environment, else from the file named by P2P_SECRETS (line MODEL_API_KEY=...)."""
    key = os.environ.get("MODEL_API_KEY", "").strip()
    if key:
        return key
    secrets = os.environ.get("P2P_SECRETS")
    if secrets and Path(secrets).is_file():
        for line in Path(secrets).read_text(encoding="utf-8-sig").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "MODEL_API_KEY" and value.strip():
                return value.strip()
    raise RuntimeError("No Meta API key: set MODEL_API_KEY or P2P_SECRETS.")


def client() -> OpenAI:
    return OpenAI(base_url=BASE_URL, api_key=api_key(), max_retries=3, timeout=600)


def async_client() -> AsyncOpenAI:
    return AsyncOpenAI(base_url=BASE_URL, api_key=api_key(), max_retries=3, timeout=1800)


def upload(path: Path, media_type: str) -> str:
    with path.open("rb") as fh:
        uploaded = client().files.create(file=(path.name, fh.read(), media_type), purpose="user_data")
    if not str(uploaded.id).startswith("file-"):
        raise RuntimeError(f"Unexpected file id from the Files API: {uploaded.id!r}")
    return uploaded.id
