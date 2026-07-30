"""Shared access-code gate for cost-bearing and feedback APIs."""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import os


ACCESS_HEADER = "X-Courseware-Access-Code"


@dataclass(frozen=True)
class AccessCodeGate:
    """Compare a request code without exposing the configured value."""

    expected: str = ""

    @property
    def required(self) -> bool:
        return bool(self.expected)

    def allows(self, supplied: str | None) -> bool:
        if not self.required:
            return True
        candidate = supplied or ""
        return hmac.compare_digest(
            candidate.encode("utf-8", errors="strict"),
            self.expected.encode("utf-8", errors="strict"),
        )

    @classmethod
    def from_environment(cls) -> "AccessCodeGate":
        expected = os.environ.get("COURSEWARE_ACCESS_CODE", "")
        if expected != expected.strip() or "\n" in expected or "\r" in expected:
            raise RuntimeError("COURSEWARE_ACCESS_CODE 不能包含首尾空白或换行")
        if os.environ.get("COURSEWARE_CLOUD_MODE") == "1" and not expected:
            raise RuntimeError("云端运行必须设置 COURSEWARE_ACCESS_CODE")
        return cls(expected)
