from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol, cast

from app.radar.models import RadarFeed, RadarState
from app.radar.utils import json_bytes, sha256_bytes


class RadarPublisher(Protocol):
    def load_latest_feed(self) -> RadarFeed | None: ...
    def load_state(self) -> RadarState: ...
    def publish(self, *, feed: RadarFeed, state: RadarState, history_key: str, latest_key: str, state_key: str) -> dict[str, str]: ...


class LocalRadarPublisher:
    def __init__(self, *, base_dir: str, prefix: str, cache_control: str) -> None:
        self.base_path = Path(base_dir) / prefix.strip("/")
        self.cache_control = cache_control

    def load_latest_feed(self) -> RadarFeed | None:
        return cast(RadarFeed | None, _load_json_model(self.base_path / "latest.json", RadarFeed))

    def load_state(self) -> RadarState:
        return cast(RadarState | None, _load_json_model(self.base_path / "state.json", RadarState)) or RadarState()

    def publish(self, *, feed: RadarFeed, state: RadarState, history_key: str, latest_key: str, state_key: str) -> dict[str, str]:
        feed_content = json_bytes(feed.model_dump(mode="json"))
        checksum = sha256_bytes(feed_content)
        state_content = json_bytes(state.model_dump(mode="json"))

        self._write_atomic(history_key, feed_content)
        self._write_atomic(latest_key, feed_content)
        self._write_atomic(f"{latest_key}.sha256", f"{checksum}\n".encode())
        self._write_atomic(state_key, state_content)
        return {"checksum_sha256": checksum, "latest_key": latest_key, "history_key": history_key}

    def _write_atomic(self, key: str, content: bytes) -> None:
        path = self.base_path / _strip_prefix(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(content)
        os.replace(tmp_path, path)


class R2RadarPublisher:
    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        prefix: str,
        cache_control: str,
    ) -> None:
        import boto3

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.cache_control = cache_control
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    def load_latest_feed(self) -> RadarFeed | None:
        return cast(RadarFeed | None, self._load_model("latest.json", RadarFeed))

    def load_state(self) -> RadarState:
        return cast(RadarState | None, self._load_model("state.json", RadarState)) or RadarState()

    def publish(self, *, feed: RadarFeed, state: RadarState, history_key: str, latest_key: str, state_key: str) -> dict[str, str]:
        feed_content = json_bytes(feed.model_dump(mode="json"))
        checksum = sha256_bytes(feed_content)
        state_content = json_bytes(state.model_dump(mode="json"))
        self._put(history_key, feed_content, "application/json; charset=utf-8")
        self._put(latest_key, feed_content, "application/json; charset=utf-8")
        self._put(f"{latest_key}.sha256", f"{checksum}\n".encode(), "text/plain; charset=utf-8")
        self._put(state_key, state_content, "application/json; charset=utf-8")
        return {"checksum_sha256": checksum, "latest_key": latest_key, "history_key": history_key}

    def _put(self, key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            CacheControl=self.cache_control,
            Metadata={"sha256": sha256_bytes(content)},
        )

    def _load_model(self, key: str, model_type: type[RadarFeed] | type[RadarState]) -> RadarFeed | RadarState | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=f"{self.prefix}/{key}")
        except Exception:
            return None
        raw = response["Body"].read()
        return model_type.model_validate_json(raw)


def _strip_prefix(key: str) -> str:
    parts = key.split("/", 1)
    return parts[1] if len(parts) == 2 else key


def _load_json_model(path: Path, model_type: type[RadarFeed] | type[RadarState]) -> RadarFeed | RadarState | None:
    if not path.exists():
        return None
    return model_type.model_validate_json(path.read_bytes())
