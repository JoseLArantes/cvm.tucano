import hashlib
import logging
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

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            self.client.set(key, value, ex=ttl_seconds)
        except Exception as exc:
            logger.warning("Falha ao salvar dados no cache Redis (chave: %s): %s", key, exc)


cache = RedisCache()


def build_cache_key(endpoint: str, codigo_cvm: int, params: dict[str, Any]) -> str:
    """Gera uma chave única e determinística para o cache Redis baseada nos filtros da query."""
    # Filtra valores None e ordena para manter a chave consistente
    sorted_params = sorted((k, str(v)) for k, v in params.items() if v is not None)
    params_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    params_hash = hashlib.sha256(params_str.encode("utf-8")).hexdigest()[:16]
    return f"public:analise:{endpoint}:{codigo_cvm}:{params_hash}"
