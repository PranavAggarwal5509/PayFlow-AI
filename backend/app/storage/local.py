"""File storage abstraction. `LocalStorage` today; an S3 implementation can replace it later."""

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def save(self, data: bytes) -> str: ...
    def read(self, key: str) -> bytes: ...
    def resolve_path(self, key: str) -> Path: ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes) -> str:
        """Store bytes under a server-generated name; the user-supplied name is never used."""
        key = f"{uuid.uuid4().hex}.pdf"
        (self.root / key).write_bytes(data)
        return key

    def resolve_path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):  # path traversal guard
            raise ValueError("Invalid storage key")
        return path

    def read(self, key: str) -> bytes:
        return self.resolve_path(key).read_bytes()

    def iter_chunks(self, key: str, size: int = 65536) -> Iterator[bytes]:
        with self.resolve_path(key).open("rb") as handle:
            while chunk := handle.read(size):
                yield chunk

