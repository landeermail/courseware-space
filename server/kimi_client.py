"""Minimal Kimi Code provider adapter using only the Python standard library."""

from __future__ import annotations

import base64
import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_ENDPOINT = "https://api.kimi.com/coding/v1/chat/completions"
DEFAULT_MODEL = "k3-256k"
DEFAULT_REASONING_EFFORT = "high"
ALLOWED_MODELS = frozenset({DEFAULT_MODEL})
PHASE_MAX_COMPLETION_TOKENS = {
    "text_parse": 16_384,
    "vision_parse": 16_384,
    "physics_model": 32_768,
    "teaching_view": 65_536,
}


@dataclass
class ProviderError(RuntimeError):
    kind: str
    message: str
    status: int | None = None
    metadata: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class CompletionResult:
    content: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _SSECompletion:
    content: str
    response_id: str | None
    model: str | None
    finish_reason: str | None
    usage: dict[str, Any]


class KimiCodeClient:
    """OpenAI-compatible Kimi Code client with explicit, bounded request policy."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
        stream_timeout: float = 300.0,
        max_retries: int = 1,
    ) -> None:
        model = model.strip()
        if model not in ALLOWED_MODELS:
            raise ValueError(f"本项目只允许常规速度模型 {DEFAULT_MODEL}，不允许 fallback 或 HighSpeed")
        if timeout <= 0 or stream_timeout <= 0:
            raise ValueError("Kimi timeout 必须为正数")
        if not 0 <= max_retries <= 1:
            raise ValueError("Kimi 临时故障最多重试一次")
        self.api_key = (api_key if api_key is not None else os.environ.get("KIMI_API_KEY", "")).strip()
        self.endpoint = endpoint
        self.model = model
        self.reasoning_effort = DEFAULT_REASONING_EFFORT
        self.timeout = timeout
        self.stream_timeout = stream_timeout
        self.max_retries = max_retries

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        phase: str = "text_parse",
        prompt_cache_key: str | None = None,
    ) -> str:
        return self.complete_result(
            system_prompt,
            user_prompt,
            phase=phase,
            prompt_cache_key=prompt_cache_key,
        ).content

    def complete_result(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        phase: str,
        prompt_cache_key: str | None = None,
        stream: bool = False,
    ) -> CompletionResult:
        return self.complete_messages_result(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            phase=phase,
            prompt_cache_key=prompt_cache_key,
            stream=stream,
        )

    def complete_vision(
        self,
        system_prompt: str,
        user_prompt: str,
        mime_type: str,
        image: bytes,
        *,
        prompt_cache_key: str | None = None,
    ) -> str:
        """Send one in-memory image without persisting it or exposing it in logs."""

        encoded = base64.b64encode(image).decode("ascii")
        return self.complete_messages(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
            phase="vision_parse",
            prompt_cache_key=prompt_cache_key,
        )

    def complete_streaming(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        phase: str = "teaching_view",
        prompt_cache_key: str | None = None,
    ) -> str:
        """Stream long code generations with a generous socket inactivity timeout."""

        return self.complete_result(
            system_prompt,
            user_prompt,
            phase=phase,
            prompt_cache_key=prompt_cache_key,
            stream=True,
        ).content

    def complete_messages_streaming(
        self,
        messages: list[dict[str, Any]],
        *,
        phase: str = "teaching_view",
        prompt_cache_key: str | None = None,
    ) -> str:
        return self.complete_messages_result(
            messages,
            phase=phase,
            prompt_cache_key=prompt_cache_key,
            stream=True,
        ).content

    def complete_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        phase: str = "text_parse",
        prompt_cache_key: str | None = None,
    ) -> str:
        return self.complete_messages_result(
            messages,
            phase=phase,
            prompt_cache_key=prompt_cache_key,
            stream=False,
        ).content

    def complete_messages_result(
        self,
        messages: list[dict[str, Any]],
        *,
        phase: str,
        prompt_cache_key: str | None,
        stream: bool,
    ) -> CompletionResult:
        if not self.api_key:
            raise ProviderError("configuration", "生成服务尚未配置 Kimi API Key")
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages 必须是非空数组")
        if phase not in PHASE_MAX_COMPLETION_TOKENS:
            raise ValueError(f"未知 Kimi 调用阶段：{phase}")
        if prompt_cache_key is not None and (
            not isinstance(prompt_cache_key, str) or not 8 <= len(prompt_cache_key) <= 128
        ):
            raise ValueError("prompt_cache_key 必须为 8～128 字符")

        max_completion_tokens = PHASE_MAX_COMPLETION_TOKENS[phase]
        request_payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "reasoning_effort": self.reasoning_effort,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": max_completion_tokens,
        }
        if prompt_cache_key is not None:
            request_payload["prompt_cache_key"] = prompt_cache_key
        if stream:
            request_payload["stream_options"] = {"include_usage": True}
        encoded_payload = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")

        base_metadata: dict[str, Any] = {
            "phase": phase,
            "requested_model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "max_completion_tokens": max_completion_tokens,
            "response_format": "json_object",
            "temperature": "provider_default",
            "top_p": "provider_default",
            "stream": stream,
            "prompt_cache_key": prompt_cache_key,
        }
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            request = urllib.request.Request(
                self.endpoint,
                data=encoded_payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream" if stream else "application/json",
                    "User-Agent": "courseware-space-generator/0.1",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.stream_timeout if stream else self.timeout,
                ) as response:
                    if stream:
                        parsed = _read_sse_completion(response)
                        content = parsed.content
                        response_metadata = {
                            "response_id": parsed.response_id,
                            "actual_model": parsed.model,
                            "finish_reason": parsed.finish_reason,
                            "usage": parsed.usage,
                        }
                    else:
                        data: dict[str, Any] = json.load(response)
                        content, response_metadata = _parse_completion_response(data)
                metadata = {
                    **base_metadata,
                    **response_metadata,
                    "attempt": attempt + 1,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                }
                if metadata.get("finish_reason") == "length":
                    raise ProviderError("length_limit", "Kimi 输出达到长度上限，拒绝自动重试", metadata=metadata)
                if not content.strip():
                    raise ProviderError("invalid_response", "Kimi 返回内容为空或格式异常", metadata=metadata)
                return CompletionResult(content.strip(), metadata)
            except ProviderError:
                raise
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", "replace")[:2000]
                classified = _classify_access_error(error.code, body)
                if classified is not None:
                    raise classified
                if error.code >= 500 or error.code == 429:
                    if attempt < self.max_retries:
                        time.sleep(1.0 * (2**attempt))
                        continue
                    raise ProviderError("temporary", f"Kimi 暂时不可用（HTTP {error.code}）", error.code)
                raise ProviderError("request", f"Kimi 拒绝请求（HTTP {error.code}）", error.code)
            except (TimeoutError, socket.timeout) as error:
                raise ProviderError("read_timeout", "Kimi 请求已发出但读取超时，不自动重试") from error
            except urllib.error.URLError as error:
                if isinstance(error.reason, (TimeoutError, socket.timeout)):
                    raise ProviderError("read_timeout", "Kimi 请求已发出但读取超时，不自动重试") from error
                if attempt < self.max_retries:
                    time.sleep(1.0 * (2**attempt))
                    continue
                raise ProviderError("network", f"无法连接 Kimi：{error}") from error

        raise ProviderError("temporary", "Kimi 请求重试次数已用尽")


def _parse_completion_response(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderError("invalid_response", "Kimi 返回 choices 格式异常")
    choice = choices[0]
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ProviderError("invalid_response", "Kimi 返回 content 格式异常")
    return content, {
        "response_id": data.get("id") if isinstance(data.get("id"), str) else None,
        "actual_model": data.get("model") if isinstance(data.get("model"), str) else None,
        "finish_reason": choice.get("finish_reason") if isinstance(choice.get("finish_reason"), str) else None,
        "usage": _numeric_usage(data.get("usage")),
    }


def _classify_access_error(status: int, body: str) -> ProviderError | None:
    """Classify access failures without returning provider response details to callers."""

    if status == 401:
        return ProviderError("authentication", "Kimi API Key 无效或已失效（HTTP 401）", status)
    normalized = body.casefold()
    quota_markers = (
        "usage limit",
        "usage_limit",
        "monthly usage",
        "rate limit",
        "rate_limit",
        "quota",
        "frequency",
        "resource exhausted",
        "resource_exhausted",
        "limit reached",
        "insufficient",
        "频限",
        "限额",
        "额度",
    )
    if status in {403, 429} and any(marker in normalized for marker in quota_markers):
        return ProviderError("quota", f"Kimi 使用额度或频率暂不可用（HTTP {status}）", status)
    if status == 403:
        return ProviderError("permission", "Kimi 当前账号无权执行该请求（HTTP 403）", status)
    return None


def _numeric_usage(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(item, bool):
            continue
        if isinstance(item, (int, float)):
            safe[key] = item
        elif isinstance(item, dict):
            nested = _numeric_usage(item)
            if nested:
                safe[key] = nested
    return safe


def _read_sse_completion(response: Any) -> _SSECompletion:
    """Parse OpenAI-compatible SSE content and non-sensitive response metadata."""

    parts: list[str] = []
    response_id: str | None = None
    model: str | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] = {}
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="strict").strip()
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            break
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as error:
            raise ProviderError("invalid_response", "Kimi 流式响应包含无效 JSON") from error
        if not isinstance(payload, dict):
            continue
        if isinstance(payload.get("id"), str):
            response_id = payload["id"]
        if isinstance(payload.get("model"), str):
            model = payload["model"]
        parsed_usage = _numeric_usage(payload.get("usage"))
        if parsed_usage:
            usage = parsed_usage
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            continue
        choice = choices[0]
        if isinstance(choice.get("finish_reason"), str):
            finish_reason = choice["finish_reason"]
        delta = choice.get("delta", {})
        content = delta.get("content") if isinstance(delta, dict) else None
        if isinstance(content, str):
            parts.append(content)
    return _SSECompletion("".join(parts), response_id, model, finish_reason, usage)


def _read_sse_content(response: Any) -> str:
    """Backward-compatible content-only SSE parser used by focused unit tests."""

    return _read_sse_completion(response).content
