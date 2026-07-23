from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol, cast

from pydantic import BaseModel, ValidationError

from app.radar.models import RadarFeed, RadarFeedV2, RadarState
from app.radar.utils import json_bytes, sha256_bytes


class RadarPublisher(Protocol):
    def load_latest_feed(self) -> RadarFeed | None: ...
    def load_latest_feed_v2(self) -> RadarFeedV2 | None: ...
    def load_state(self) -> RadarState: ...
    def load_history_feeds(self, *, limit: int = 1000) -> list[RadarFeed]: ...
    def publish(
        self,
        *,
        feed: RadarFeed,
        state: RadarState,
        history_key: str,
        latest_key: str,
        state_key: str,
    ) -> dict[str, str]: ...
    def publish_v2(
        self,
        *,
        feed_v2: RadarFeedV2,
        feed_v1: RadarFeed,
        state: RadarState,
        history_key_v2: str,
    ) -> dict[str, str]: ...


class LocalRadarPublisher:
    def __init__(self, *, base_dir: str, prefix: str, cache_control: str) -> None:
        self.base_path = Path(base_dir) / prefix.strip("/")
        self.cache_control = cache_control

    def load_latest_feed(self) -> RadarFeed | None:
        return _load_json_model(self.base_path / "latest.json", RadarFeed)

    def load_latest_feed_v2(self) -> RadarFeedV2 | None:
        return _load_json_model(self.base_path / "v2/latest.json", RadarFeedV2)

    def load_state(self) -> RadarState:
        return _load_json_model(self.base_path / "v2/state.json", RadarState) or RadarState()

    def load_history_feeds(self, *, limit: int = 1000) -> list[RadarFeed]:
        paths = sorted((self.base_path / "history").glob("**/*.json"))[-limit:]
        return [feed for path in paths if (feed := _load_json_model(path, RadarFeed)) is not None]

    def publish(
        self,
        *,
        feed: RadarFeed,
        state: RadarState,
        history_key: str,
        latest_key: str,
        state_key: str,
    ) -> dict[str, str]:
        feed_content = json_bytes(feed.model_dump(mode="json"))
        checksum = sha256_bytes(feed_content)
        state_content = json_bytes(state.model_dump(mode="json"))
        self._write_atomic(history_key, feed_content)
        self._write_atomic(state_key, state_content)
        self._write_atomic(f"{latest_key}.sha256", f"{checksum}\n".encode())
        self._write_atomic(latest_key, feed_content)
        return {"checksum_sha256": checksum, "latest_key": latest_key, "history_key": history_key}

    def publish_v2(
        self,
        *,
        feed_v2: RadarFeedV2,
        feed_v1: RadarFeed,
        state: RadarState,
        history_key_v2: str,
    ) -> dict[str, str]:
        v2_content = json_bytes(feed_v2.model_dump(mode="json"))
        v1_content = json_bytes(feed_v1.model_dump(mode="json"))
        v2_checksum = sha256_bytes(v2_content)
        v1_checksum = sha256_bytes(v1_content)
        self._write_atomic(history_key_v2, v2_content)
        self._write_atomic("v2/state.json", json_bytes(state.model_dump(mode="json")))
        self._write_atomic("latest.json.sha256", f"{v1_checksum}\n".encode())
        self._write_atomic("v2/latest.json.sha256", f"{v2_checksum}\n".encode())
        self._write_atomic("latest.json", v1_content)
        self._write_atomic("v2/latest.json", v2_content)
        return {
            "checksum_sha256": v2_checksum,
            "latest_key": "v2/latest.json",
            "compatibility_latest_key": "latest.json",
            "history_key": history_key_v2,
        }

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
        return self._load_model("latest.json", RadarFeed)

    def load_latest_feed_v2(self) -> RadarFeedV2 | None:
        return self._load_model("v2/latest.json", RadarFeedV2)

    def load_state(self) -> RadarState:
        return self._load_model("v2/state.json", RadarState) or RadarState()

    def load_history_feeds(self, *, limit: int = 1000) -> list[RadarFeed]:
        keys: list[str] = []
        continuation: str | None = None
        while True:
            kwargs: dict[str, object] = {
                "Bucket": self.bucket,
                "Prefix": f"{self.prefix}/history/",
                "MaxKeys": 1000,
            }
            if continuation:
                kwargs["ContinuationToken"] = continuation
            response = self.client.list_objects_v2(**kwargs)
            keys.extend(str(item["Key"]) for item in response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            continuation = cast(str | None, response.get("NextContinuationToken"))
        feeds: list[RadarFeed] = []
        for key in sorted(keys)[-limit:]:
            relative = key.removeprefix(f"{self.prefix}/")
            feed = self._load_model(relative, RadarFeed)
            if feed is not None:
                feeds.append(feed)
        return feeds

    def publish(
        self,
        *,
        feed: RadarFeed,
        state: RadarState,
        history_key: str,
        latest_key: str,
        state_key: str,
    ) -> dict[str, str]:
        feed_content = json_bytes(feed.model_dump(mode="json"))
        checksum = sha256_bytes(feed_content)
        self._put(history_key, feed_content, "application/json; charset=utf-8")
        self._put(state_key, json_bytes(state.model_dump(mode="json")), "application/json; charset=utf-8")
        self._put(f"{latest_key}.sha256", f"{checksum}\n".encode(), "text/plain; charset=utf-8")
        self._put(latest_key, feed_content, "application/json; charset=utf-8")
        return {"checksum_sha256": checksum, "latest_key": latest_key, "history_key": history_key}

    def publish_v2(
        self,
        *,
        feed_v2: RadarFeedV2,
        feed_v1: RadarFeed,
        state: RadarState,
        history_key_v2: str,
    ) -> dict[str, str]:
        v2_content = json_bytes(feed_v2.model_dump(mode="json"))
        v1_content = json_bytes(feed_v1.model_dump(mode="json"))
        v2_checksum = sha256_bytes(v2_content)
        v1_checksum = sha256_bytes(v1_content)
        self._put(history_key_v2, v2_content, "application/json; charset=utf-8")
        self._put(
            f"{self.prefix}/v2/state.json",
            json_bytes(state.model_dump(mode="json")),
            "application/json; charset=utf-8",
        )
        self._put(f"{self.prefix}/latest.json.sha256", f"{v1_checksum}\n".encode(), "text/plain; charset=utf-8")
        self._put(f"{self.prefix}/v2/latest.json.sha256", f"{v2_checksum}\n".encode(), "text/plain; charset=utf-8")
        self._put(f"{self.prefix}/latest.json", v1_content, "application/json; charset=utf-8")
        self._put(f"{self.prefix}/v2/latest.json", v2_content, "application/json; charset=utf-8")
        return {
            "checksum_sha256": v2_checksum,
            "latest_key": f"{self.prefix}/v2/latest.json",
            "compatibility_latest_key": f"{self.prefix}/latest.json",
            "history_key": history_key_v2,
        }

    def _put(self, key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            CacheControl=self.cache_control,
            Metadata={"sha256": sha256_bytes(content)},
        )

    def _load_model[ModelT: BaseModel](self, key: str, model_type: type[ModelT]) -> ModelT | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=f"{self.prefix}/{key}")
            raw = response["Body"].read()
            return model_type.model_validate_json(raw)
        except Exception:
            return None


def _strip_prefix(key: str) -> str:
    normalized = key.strip("/")
    if normalized.startswith("radar-cvm/"):
        return normalized.split("/", 1)[1]
    return normalized


def _load_json_model[ModelT: BaseModel](path: Path, model_type: type[ModelT]) -> ModelT | None:
    if not path.exists():
        return None
    try:
        return model_type.model_validate_json(path.read_bytes())
    except ValidationError:
        return None
