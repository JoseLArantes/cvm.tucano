from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


class LocalArtifactStore:
    def __init__(self, base_dir: str | None = None) -> None:
        root = base_dir or get_settings().storage_dir
        self._root = Path(root) / "artifacts"

    @property
    def root(self) -> Path:
        return self._root

    def member_artifact_path(self, *, execution_id: str, member_name: str) -> Path:
        return self.root / "member_payloads" / execution_id / member_name

    def put_member_bytes(self, *, execution_id: str, member_name: str, payload: bytes) -> str:
        artifact_path = self.member_artifact_path(execution_id=execution_id, member_name=member_name)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(payload)
        return str(artifact_path)

    def read_member_bytes(self, *, execution_id: str, member_name: str) -> bytes:
        return self.member_artifact_path(execution_id=execution_id, member_name=member_name).read_bytes()

    def member_exists(self, *, execution_id: str, member_name: str) -> bool:
        return self.member_artifact_path(execution_id=execution_id, member_name=member_name).exists()

    def delete_member(self, *, execution_id: str, member_name: str) -> None:
        artifact_path = self.member_artifact_path(execution_id=execution_id, member_name=member_name)
        if artifact_path.exists():
            artifact_path.unlink()
        current_dir = artifact_path.parent
        while current_dir != self.root and current_dir.exists():
            try:
                current_dir.rmdir()
            except OSError:
                break
            current_dir = current_dir.parent

def _artifact_store() -> LocalArtifactStore:
    return LocalArtifactStore()


def save_member_artifact(*, execution_id: str, member_name: str, payload: bytes) -> str:
    return _artifact_store().put_member_bytes(
        execution_id=execution_id,
        member_name=member_name,
        payload=payload,
    )


def read_member_artifact(*, execution_id: str, member_name: str) -> bytes:
    return _artifact_store().read_member_bytes(execution_id=execution_id, member_name=member_name)


def member_artifact_exists(*, execution_id: str, member_name: str) -> bool:
    return _artifact_store().member_exists(execution_id=execution_id, member_name=member_name)


def delete_member_artifact(*, execution_id: str, member_name: str) -> None:
    _artifact_store().delete_member(execution_id=execution_id, member_name=member_name)
