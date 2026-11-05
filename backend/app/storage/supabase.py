"""Supabase Storage implementation of StorageBackend protocol."""

import logging
import uuid
from collections.abc import Iterator
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)


class SupabaseStorage:
    def __init__(
        self,
        supabase_url: str,
        service_role_key: str,
        bucket: str = "PayFlow",
        cache_dir: Path | None = None,
    ) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.bucket = bucket
        self.cache_dir = cache_dir or Path("/tmp/payflow_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            headers={
                "apikey": self.service_role_key,
                "Authorization": f"Bearer {self.service_role_key}",
            },
            timeout=30.0,
        )

    @property
    def public_base_url(self) -> str:
        return f"{self.supabase_url}/storage/v1/object/public/{self.bucket}"

    def get_public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    def save(self, data: bytes) -> str:
        """Store bytes under a server-generated name in Supabase storage and local cache."""
        key = f"{uuid.uuid4().hex}.pdf"
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{key}"
        res = self.client.post(
            url,
            content=data,
            headers={
                "Content-Type": "application/pdf",
                "x-upsert": "true",
            },
        )
        if res.status_code not in (200, 201):
            logger.error("Failed to upload %s to Supabase: %s", key, res.text)
            raise RuntimeError(f"Supabase upload failed: {res.status_code} - {res.text}")

        # Also cache locally so immediate layout extraction has fast disk access
        cache_file = self.cache_dir / key
        try:
            cache_file.write_bytes(data)
        except Exception:
            logger.warning("Failed to write to local storage cache for key %s", key)

        return key

    def _validate_key(self, key: str) -> None:
        """Prevent path traversal attacks."""
        if not key or ".." in key or key.startswith("/") or "\\" in key:
            raise ValueError(f"Invalid storage key: {key}")

    def resolve_path(self, key: str) -> Path:
        """Ensure file is cached locally on disk (needed for pymupdf and tesseract) and return Path."""
        self._validate_key(key)
        cache_file = (self.cache_dir / key).resolve()
        if not cache_file.is_relative_to(self.cache_dir.resolve()):
            raise ValueError(f"Invalid storage key path: {key}")

        if cache_file.is_file() and cache_file.stat().st_size > 0:
            return cache_file

        data = self.read(key)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(data)
        return cache_file

    def read(self, key: str) -> bytes:
        """Read file bytes from local cache or fetch from Supabase."""
        self._validate_key(key)
        cache_file = (self.cache_dir / key).resolve()
        if not cache_file.is_relative_to(self.cache_dir.resolve()):
            raise ValueError(f"Invalid storage key path: {key}")

        if cache_file.is_file() and cache_file.stat().st_size > 0:
            return cache_file.read_bytes()

        # Try key directly
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{key}"
        res = self.client.get(url)
        if res.status_code == 200:
            return res.content

        # Fallback to public URL endpoint
        public_url = f"{self.public_base_url}/{key}"
        res = self.client.get(public_url)
        if res.status_code == 200:
            return res.content

        raise ValueError(f"Document not found in Supabase storage: {key} (status: {res.status_code})")

    def iter_chunks(self, key: str, size: int = 65536) -> Iterator[bytes]:
        data = self.read(key)
        for i in range(0, len(data), size):
            yield data[i : i + size]

