from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ProxyConfig:
    server: str
    username: str | None = None
    password: str | None = None


@runtime_checkable
class ProxyProvider(Protocol):
    def get_proxy(self, *, correlation_id: str) -> ProxyConfig | None: ...
