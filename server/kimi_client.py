"""Minimal Kimi Code provider adapter using only the Python standard library."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_ENDPOINT = "https://api.kimi.com/coding/v1/chat/completions"
DEFAULT_MODEL = "kimi-for-coding"


@dataclass
class ProviderError(RuntimeError):
    kind: str
    message: str
    status: int | None = None

    def __str__(self) -> str:
        return self.message


class KimiCodeClient:
    """OpenAI-compatible Kimi Code client with bounded retry behavior."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        model: str = DEFAULT_MODEL,
        timeout: float = 45.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get("KIMI_API_KEY", "")).strip()
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise ProviderError("configuration", "生成服务尚未配置 Kimi API Key")

        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        for attempt in range(self.max_retries + 1):
            request = urllib.request.Request(
                self.endpoint,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "courseware-space-generator/0.1",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data: dict[str, Any] = json.load(response)
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ProviderError("invalid_response", "Kimi 返回内容为空或格式异常")
                return content.strip()
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", "replace")[:500]
                if error.code in {401, 403}:
                    raise ProviderError("authentication", f"Kimi 鉴权或权限失败（HTTP {error.code}）", error.code)
                if error.code == 429 or error.code >= 500:
                    if attempt < self.max_retries:
                        time.sleep(1.0 * (2**attempt))
                        continue
                    raise ProviderError("temporary", f"Kimi 暂时不可用（HTTP {error.code}）", error.code)
                raise ProviderError("request", f"Kimi 拒绝请求（HTTP {error.code}）：{body}", error.code)
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt < self.max_retries:
                    time.sleep(1.0 * (2**attempt))
                    continue
                raise ProviderError("network", f"无法连接 Kimi：{error}")

        raise ProviderError("temporary", "Kimi 请求重试次数已用尽")
