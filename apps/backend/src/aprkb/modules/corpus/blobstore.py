"""Local blob storage with opaque, traversal-safe keys."""

from pathlib import Path, PurePosixPath
from typing import Protocol


class BlobStore(Protocol):
    def put(self, key: str, content: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalBlobStore:
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    def _path_for(self, key: str) -> Path:
        relative = PurePosixPath(key)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise ValueError("Unsafe blob key")
        path = self._root.joinpath(*relative.parts).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("Unsafe blob key")
        return path

    def put(self, key: str, content: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def get(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        path.unlink(missing_ok=True)
