from __future__ import annotations

import os
from typing import Final

from crawler.src.proxy.proxy_provider import ProxyConfig
from shared.structured_logger import get_logger

_logger = get_logger(__name__)
_SERVICE_NAME: Final[str] = os.environ.get("SERVICE_NAME", "crawler")


class ProxyBroker:
    """MVP 단계 ProxyProvider 구현. PROXY_BROKER_HOST 환경변수 미설정 시 None 반환.

    Story 2.5/2.6에서 실제 ProxyBroker SDK 호출로 확장. 본 스토리는 인터페이스
    안정성과 NodeMaven 교체 비용 0(NFR15)을 단위 테스트로 증명하는 것이 목표.
    """

    def __init__(
        self,
        *,
        host_env: str = "PROXY_BROKER_HOST",
        user_env: str = "PROXY_BROKER_USER",
        password_env: str = "PROXY_BROKER_PASS",
    ) -> None:
        self._host_env = host_env
        self._user_env = user_env
        self._password_env = password_env

    def get_proxy(self, *, correlation_id: str) -> ProxyConfig | None:
        extra = {"correlation_id": correlation_id, "service": _SERVICE_NAME}
        host = os.environ.get(self._host_env, "").strip() or None
        if not host:
            _logger.debug("proxy_broker.disabled reason=host_env_unset", extra=extra)
            return None
        username = os.environ.get(self._user_env) or None
        password = os.environ.get(self._password_env) or None
        _logger.debug(f"proxy_broker.enabled host={host}", extra=extra)
        return ProxyConfig(server=host, username=username, password=password)
