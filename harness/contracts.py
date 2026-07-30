"""Strict contract for model-generated code artifacts."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any


REQUIRED_HTML_MARKERS = {
    "<!--HARNESS_PRIMITIVES-->",
    "<!--HARNESS_MODEL-->",
    "<!--HARNESS_INPUT-->",
    "data-physical-time",
    "data-demo-time",
    "data-control",
    "data-readout",
    "data-replay",
    "CoursewarePrimitives",
    "coursewareModel",
    ".createTimeline",
    ".formatPhysicalTime",
    ".formatDemoRate",
    ".sample(",
    "durationPhysicalS",
    "onChange",
}
FORBIDDEN_CODE = re.compile(
    r"\b(require|process|fetch|XMLHttpRequest|WebSocket|eval|import|Deno|Bun|child_process)\b|"
    r"\b(?-i:Function)\s*\(|\bnew\s+(?-i:Function)\b|\bMath\.random\b|\bDate(?:\s*\(|\.)|"
    r"\b(performance|setTimeout|setInterval|queueMicrotask)\b|__proto__|\.constructor|</script",
    re.IGNORECASE,
)
FORBIDDEN_HTML = re.compile(
    r"https?://|<script[^>]+src\s*=|<\s*(iframe|object|embed|base|form)\b|"
    r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|Worker|SharedWorker|sendBeacon|eval)\b|"
    r"\b(?-i:Function)\s*\(|\bnew\s+(?-i:Function)\b|"
    r"\b(requestAnimationFrame|cancelAnimationFrame)\b|"
    r"document\.cookie|localStorage|sessionStorage",
    re.IGNORECASE,
)
CSP_META = (
    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
    "script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; "
    "connect-src 'none'; object-src 'none'; frame-src 'none'; worker-src 'none'; "
    "media-src 'none'; font-src 'none'; form-action 'none'; base-uri 'none'\">"
)


class ContractError(ValueError):
    pass


class _CoursewareHTMLAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parameter_controls = 0
        self.attributes: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        names = {name.casefold() for name, _ in attrs}
        self.attributes.update(names)
        if "data-control" in names and tag.casefold() in {"input", "select"}:
            self.parameter_controls += 1


class _InlineScriptAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self._current: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "script":
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._current is not None:
            self.scripts.append("".join(self._current))
            self._current = None


def _html_has_forbidden_capability(html: str) -> bool:
    without_svg_namespace = html.replace("http://www.w3.org/2000/svg", "")
    return FORBIDDEN_HTML.search(without_svg_namespace) is not None


def _require_html_head(html: str) -> None:
    if re.search(r"<head\b[^>]*>", html, re.IGNORECASE) is None:
        raise ContractError("HTML 缺少可注入安全策略的 head")


def _audit_html_controls(html: str) -> None:
    audit = _CoursewareHTMLAudit()
    audit.feed(html)
    audit.close()
    required = {"data-physical-time", "data-demo-time", "data-readout", "data-replay"}
    missing = sorted(required - audit.attributes)
    if missing:
        raise ContractError(f"HTML 缺少真实交互元素：{', '.join(missing)}")
    if audit.parameter_controls < 2:
        raise ContractError("HTML 至少需要两个真实 input/select 参数控件")


def _audit_inline_script_syntax(html: str) -> None:
    audit = _InlineScriptAudit()
    audit.feed(html)
    audit.close()
    for script in audit.scripts:
        if "<!--HARNESS_" in script:
            raise ContractError("harness 占位符必须位于 script 元素之外")
        if not script.strip():
            continue
        try:
            checked = subprocess.run(
                ["node", "--check"],
                input=script,
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ContractError("无法执行 HTML 内联脚本语法校验") from error
        if checked.returncode != 0:
            raise ContractError("HTML 内联脚本语法无效")


def _escape_quoted_script_newlines(script: str) -> tuple[str, bool]:
    output: list[str] = []
    index = 0
    state = "normal"
    changed = False
    while index < len(script):
        char = script[index]
        following = script[index + 1] if index + 1 < len(script) else ""
        if state == "normal":
            if char == "'":
                state = "single"
            elif char == '"':
                state = "double"
            elif char == "`":
                state = "template"
            elif char == "/" and following == "/":
                output.extend((char, following))
                index += 2
                state = "line_comment"
                continue
            elif char == "/" and following == "*":
                output.extend((char, following))
                index += 2
                state = "block_comment"
                continue
        elif state in {"single", "double"}:
            quote = "'" if state == "single" else '"'
            if char == "\\":
                output.append(char)
                if following:
                    output.append(following)
                    index += 2
                    continue
            elif char == quote:
                state = "normal"
            elif char in {"\n", "\r"}:
                output.extend(("\\", "n"))
                changed = True
                if char == "\r" and following == "\n":
                    index += 2
                else:
                    index += 1
                continue
        elif state == "template":
            if char == "\\":
                output.append(char)
                if following:
                    output.append(following)
                    index += 2
                    continue
            elif char == "`":
                state = "normal"
        elif state == "line_comment":
            if char in {"\n", "\r"}:
                state = "normal"
        elif state == "block_comment" and char == "*" and following == "/":
            output.extend((char, following))
            index += 2
            state = "normal"
            continue
        output.append(char)
        index += 1
    return "".join(output), changed


def _normalize_inline_script_newlines(html: str) -> tuple[str, tuple[str, ...]]:
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        fixed, script_changed = _escape_quoted_script_newlines(match.group(2))
        changed = changed or script_changed
        return match.group(1) + fixed + match.group(3)

    normalized = re.sub(
        r"(<script\b[^>]*>)(.*?)(</script\s*>)",
        replace,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return normalized, (("escaped_quoted_script_newlines",) if changed else ())


@dataclass(frozen=True)
class GeneratedArtifact:
    title: str
    domain: str
    teaching_intent: str
    model_js: str
    html: str

    @classmethod
    def parse(cls, raw: str, expected_domain: str) -> "GeneratedArtifact":
        if not isinstance(raw, str) or not raw.strip() or "```" in raw:
            raise ContractError("模型必须返回单一 JSON 对象，不能使用 Markdown 代码围栏")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ContractError("模型输出不是有效 JSON") from error
        required = {"title", "domain", "teaching_intent", "model_js", "html"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise ContractError("生成物字段不符合严格白名单")
        for key in ("title", "domain", "teaching_intent", "model_js", "html"):
            if not isinstance(payload[key], str) or not payload[key].strip():
                raise ContractError(f"{key} 必须是非空文本")
        if payload["domain"] != expected_domain:
            raise ContractError("生成物 domain 与老师确认场景不一致")
        if not 4 <= len(payload["title"].strip()) <= 100:
            raise ContractError("title 长度无效")
        if not 10 <= len(payload["teaching_intent"].strip()) <= 400:
            raise ContractError("teaching_intent 长度无效")
        if not 100 <= len(payload["model_js"]) <= 30000:
            raise ContractError("model_js 长度无效")
        normalized_html, _ = _normalize_inline_script_newlines(payload["html"])
        if not 500 <= len(normalized_html) <= 96000:
            raise ContractError("html 长度无效")
        if FORBIDDEN_CODE.search(payload["model_js"]):
            raise ContractError("model_js 包含沙箱禁止能力")
        if _html_has_forbidden_capability(normalized_html):
            raise ContractError("HTML 包含外部资源、网络或动态执行能力")
        _require_html_head(normalized_html)
        _audit_html_controls(normalized_html)
        _audit_inline_script_syntax(normalized_html)
        missing = sorted(marker for marker in REQUIRED_HTML_MARKERS if marker not in normalized_html)
        if missing:
            raise ContractError(f"HTML 缺少 harness 原语标记：{', '.join(missing)}")
        if "globalThis.coursewareModel" not in payload["model_js"] or "sample" not in payload["model_js"]:
            raise ContractError("model_js 必须设置 globalThis.coursewareModel.sample")
        payload["html"] = normalized_html
        return cls(**{key: payload[key].strip() for key in required})

    def render(self, primitive_js: str, model_input: dict[str, Any]) -> str:
        touch_style = "<style>[data-control],[data-replay],button,select,input{min-height:44px}</style>"
        primitive = f"{touch_style}<script>\n{primitive_js}\n</script>"
        model = f"<script>\n{self.model_js}\n</script>"
        locked_input = json.dumps(model_input, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        input_script = f"<script>globalThis.__HARNESS_INPUT__=Object.freeze({locked_input});</script>"
        runtime_guard = """<script>
(()=>{
  const root=document.documentElement;
  const short=value=>String(value&&value.message||value||'unknown runtime error').slice(0,500);
  addEventListener('error',event=>root.setAttribute('data-harness-runtime-error',short(event.error||event.message)),true);
  addEventListener('unhandledrejection',event=>root.setAttribute('data-harness-runtime-error',short(event.reason)),true);
  const expected=globalThis.__HARNESS_INPUT__.scenario;
  const original=globalThis.coursewareModel;
  let calls=0;
  const same=(left,right)=>{
    if(left===right)return true;
    if(!left||!right||typeof left!=='object'||typeof right!=='object')return false;
    const leftKeys=Object.keys(left).sort(),rightKeys=Object.keys(right).sort();
    return leftKeys.length===rightKeys.length&&leftKeys.every((key,index)=>key===rightKeys[index]&&same(left[key],right[key]));
  };
  const guarded=Object.freeze({sample(input){
    calls+=1;
    root.setAttribute('data-harness-sample-count',String(calls));
    if(calls===1){
      const matched=Boolean(input&&same(input.scenario,expected));
      root.setAttribute('data-harness-initial-scenario',matched?'matched':'mismatched');
      if(!matched)throw new Error('首次采样场景与老师确认题设不一致');
    }
    return original.sample(input);
  }});
  Object.defineProperty(globalThis,'coursewareModel',{value:guarded,writable:false,configurable:false});
})();
</script>"""
        rendered = self.html.replace("<!--HARNESS_PRIMITIVES-->", primitive, 1)
        rendered = rendered.replace("<!--HARNESS_MODEL-->", model, 1)
        rendered = rendered.replace("<!--HARNESS_INPUT-->", input_script + runtime_guard, 1)
        if "<!--HARNESS_" in rendered:
            raise ContractError("HTML 存在未解析的 harness 占位符")
        rendered, substitutions = re.subn(r"(<head\b[^>]*>)", r"\1" + CSP_META, rendered, count=1, flags=re.IGNORECASE)
        if substitutions != 1:
            raise ContractError("HTML 缺少可注入安全策略的 head")
        return rendered

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "domain": self.domain,
            "teaching_intent": self.teaching_intent,
            "model_js": self.model_js,
            "html": self.html,
        }


@dataclass(frozen=True)
class GeneratedModel:
    title: str
    domain: str
    model_js: str

    @classmethod
    def parse(cls, raw: str, expected_domain: str) -> "GeneratedModel":
        payload = _strict_json(raw, {"title", "domain", "model_js"})
        if payload["domain"] != expected_domain:
            raise ContractError("模型 domain 与老师确认场景不一致")
        if not 4 <= len(payload["title"].strip()) <= 100:
            raise ContractError("title 长度无效")
        if not 100 <= len(payload["model_js"]) <= 30000:
            raise ContractError("model_js 长度无效")
        if FORBIDDEN_CODE.search(payload["model_js"]):
            raise ContractError("model_js 包含沙箱禁止能力")
        if "globalThis.coursewareModel" not in payload["model_js"] or "sample" not in payload["model_js"]:
            raise ContractError("model_js 必须设置 globalThis.coursewareModel.sample")
        return cls(payload["title"].strip(), payload["domain"], payload["model_js"].strip())


@dataclass(frozen=True)
class GeneratedView:
    teaching_intent: str
    html: str
    normalizations: tuple[str, ...] = ()

    @classmethod
    def parse(cls, raw: str) -> "GeneratedView":
        payload = _strict_json(raw, {"teaching_intent", "html"})
        if not 10 <= len(payload["teaching_intent"].strip()) <= 400:
            raise ContractError("teaching_intent 长度无效")
        normalized_html, normalizations = _normalize_inline_script_newlines(payload["html"])
        if not 500 <= len(normalized_html) <= 96000:
            raise ContractError("html 长度无效")
        if _html_has_forbidden_capability(normalized_html):
            raise ContractError("HTML 包含外部资源、网络或动态执行能力")
        _require_html_head(normalized_html)
        _audit_html_controls(normalized_html)
        _audit_inline_script_syntax(normalized_html)
        missing = sorted(marker for marker in REQUIRED_HTML_MARKERS if marker not in normalized_html)
        if missing:
            raise ContractError(f"HTML 缺少 harness 原语标记：{', '.join(missing)}")
        return cls(payload["teaching_intent"].strip(), normalized_html.strip(), normalizations)


def _strict_json(raw: str, fields: set[str]) -> dict[str, str]:
    if not isinstance(raw, str) or not raw.strip() or "```" in raw:
        raise ContractError("模型必须返回单一 JSON 对象，不能使用 Markdown 代码围栏")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ContractError("模型输出不是有效 JSON") from error
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ContractError("生成物字段不符合严格白名单")
    if any(not isinstance(payload[key], str) or not payload[key].strip() for key in fields):
        raise ContractError("生成物字段必须是非空文本")
    return payload
