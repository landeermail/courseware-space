"""Server-side hard gate for teacher-confirmed harness scenarios."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from typing import Any, Callable


class ConfirmationError(ValueError):
    pass


class TeacherConfirmationGate:
    def __init__(self, ttl_seconds: float = 900.0, clock: Callable[[], float] = time.monotonic) -> None:
        if ttl_seconds <= 0:
            raise ValueError("确认令牌有效期必须为正数")
        self._tokens: dict[str, tuple[str, str, float]] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    @staticmethod
    def _digest(scenario: dict[str, Any]) -> str:
        encoded = json.dumps(scenario, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def confirm(self, domain: str, scenario: dict[str, Any], teacher_confirmed: bool) -> str:
        if teacher_confirmed is not True:
            raise ConfirmationError("必须由老师显式确认关键参数后才能生成")
        if domain not in {"projectile", "circular"} or not isinstance(scenario, dict):
            raise ConfirmationError("确认场景无效")
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._tokens[token] = (domain, self._digest(scenario), self._clock() + self._ttl_seconds)
        return token

    def consume(self, token: str, domain: str, scenario: dict[str, Any]) -> None:
        if not isinstance(token, str) or not token:
            raise ConfirmationError("老师确认令牌缺失")
        with self._lock:
            expected = self._tokens.pop(token, None)
        if expected is None:
            raise ConfirmationError("老师确认令牌不存在、已使用或已失效")
        expected_domain, expected_digest, expires_at = expected
        if self._clock() >= expires_at:
            raise ConfirmationError("老师确认令牌已过期，请重新核对参数")
        if (expected_domain, expected_digest) != (domain, self._digest(scenario)):
            raise ConfirmationError("确认令牌与题型或参数不匹配")
