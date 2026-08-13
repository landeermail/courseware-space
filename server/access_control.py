"""Shared access-code gate for cost-bearing and feedback APIs."""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import os
import re


ACCESS_HEADER = "X-Courseware-Access-Code"
ACCESS_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{48}$")


def validate_access_code(value: str) -> None:
    """Require the existing 48-character alphanumeric long-link format."""

    if value != value.strip() or "\n" in value or "\r" in value:
        raise RuntimeError("COURSEWARE_ACCESS_CODE 不能包含首尾空白或换行")
    if value and not ACCESS_CODE_PATTERN.fullmatch(value):
        raise RuntimeError(
            "COURSEWARE_ACCESS_CODE 必须是 48 位大小写字母或数字"
        )


@dataclass(frozen=True)
class AccessCodeGate:
    """Compare a request code without exposing the configured value."""

    expected: str = ""

    def __post_init__(self) -> None:
        validate_access_code(self.expected)

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
        validate_access_code(expected)
        if os.environ.get("COURSEWARE_CLOUD_MODE") == "1" and not expected:
            raise RuntimeError("云端运行必须设置 COURSEWARE_ACCESS_CODE")
        return cls(expected)
