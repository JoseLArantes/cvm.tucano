import hashlib
import logging
import secrets
import time
from typing import Any, cast

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            settings = get_settings()
            # O timeout padrão é curto para não bloquear a API caso o Redis esteja lento/indisponível
            self._client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
        return self._client

    def get(self, key: str) -> str | None:
        try:
            return cast(str | None, self.client.get(key))
        except Exception as exc:
            logger.warning("Falha ao recuperar dados do cache Redis (chave: %s): %s", key, exc)
            return None

    def set(self, key: str, value: str, ttl_seconds: int) -> bool:
        try:
            self.client.set(key, value, ex=ttl_seconds)
            return True
        except Exception as exc:
            logger.warning("Falha ao salvar dados no cache Redis (chave: %s): %s", key, exc)
            return False

    def acquire_lock(self, key: str, ttl_seconds: int) -> str | None:
        token = secrets.token_urlsafe(24)
        try:
            acquired = self.client.set(key, token, ex=ttl_seconds, nx=True)
        except Exception as exc:
            logger.warning("Falha ao adquirir lock no cache Redis (chave: %s): %s", key, exc)
            return None
        return token if acquired else ""

    def release_lock(self, key: str, token: str) -> None:
        if not token:
            return
        script = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
        try:
            self.client.eval(script, 1, key, token)
        except Exception as exc:
            logger.warning("Falha ao liberar lock no cache Redis (chave: %s): %s", key, exc)

    def wait_for(self, key: str, timeout_seconds: float, *, interval_seconds: float = 0.1) -> str | None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            value = self.get(key)
            if value is not None:
                return value
            time.sleep(interval_seconds)
        return self.get(key)


cache = RedisCache()


def build_cache_key(endpoint: str, codigo_cvm: int, params: dict[str, Any], *, namespace: str = "public:analise") -> str:
    """Gera uma chave única e determinística para o cache Redis baseada nos filtros da query."""
    # Filtra valores None e ordena para manter a chave consistente
    sorted_params = sorted((k, str(v)) for k, v in params.items() if v is not None)
    params_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    params_hash = hashlib.sha256(params_str.encode("utf-8")).hexdigest()[:16]
    return f"{namespace}:{endpoint}:{codigo_cvm}:{params_hash}"
