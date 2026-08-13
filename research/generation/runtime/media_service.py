"""Image/PDF parsing and a server-enforced teacher confirmation workflow."""

from __future__ import annotations

import base64
import binascii
import io
import json
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

from research.generation.runtime.generator_service import (
    EXPECTED_PARAMETER_KEYS,
    GenerationManager,
    build_template_config,
    normalize_question,
)
from research.generation.runtime.kimi_client import KimiCodeClient, ProviderError
from physics import derive_physics


MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 6
LOW_CONFIDENCE_THRESHOLD = 0.75
CURRENT_DIRECTIONS = {"d_to_c", "c_to_d"}
IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}

VISION_SYSTEM_PROMPT = """你是高中物理题目图片的严格结构化读取器，不负责解题，也不生成代码。

当前自动课件只支持：闭合平行导轨上的直导体杆在垂直导轨平面的匀强磁场中做匀速平动，题目明确给出 B、L、v、回路总电阻 R。
一张图可能有多道题，必须逐题输出。看不清、数值缺失、方向不明确或超出模板时不要猜。

只输出一个 JSON 对象，不要 Markdown、代码围栏、解释或额外字段。结构必须恰好为：
{"questions":[{"question_text":"完整题意","confidence":0.95,"supported":true,"reason":"","parameters":{"magnetic_field_t":0.5,"rod_length_m":1.0,"rod_speed_m_s":2.0,"resistance_ohm":0.4,"field_direction":"into_page","motion_direction":"right"},"current_direction":"d_to_c","asks":["求感应电动势","判断电流方向"]}]}

规则：
- confidence 是 0～1；只反映题意和关键参数读取把握。
- supported 只能是 true 或 false。超出模板时 parameters 仍保留能确定的值，不能确定的值填 null，并给出简短 reason。
- 所有数值换算为 SI 制纯数字，不计算题目未给出的 B、L、v、R。
- field_direction 只能是 into_page、out_of_page 或 null；motion_direction 只能是 left、right 或 null。
- current_direction 只描述模板中竖直杆：d_to_c（沿棒向上）或 c_to_d（沿棒向下）。当 B 与运动方向均明确时，应按电磁感应规律给出候选方向；任一方向不明确时填 null。后端会独立复核，不以你的判断作为物理真值。
- asks 按题目小问列出，至少一项；不要填写答案。
"""


class MediaError(ValueError):
    pass


def _safe_filename(value: object) -> str:
    if not isinstance(value, str):
        raise MediaError("文件名无效")
    value = value.strip()
    if not value or len(value) > 160 or Path(value).name != value or any(ord(char) < 32 for char in value):
        raise MediaError("文件名无效")
    return value


def decode_upload(filename: object, mime_type: object, encoded: object) -> tuple[str, str, bytes]:
    name = _safe_filename(filename)
    if not isinstance(mime_type, str):
        raise MediaError("文件类型无效")
    mime = mime_type.lower().strip()
    if mime not in IMAGE_MIME_TYPES | {"application/pdf"}:
        raise MediaError("只支持 PNG、JPEG、WebP 图片或 PDF")
    if not isinstance(encoded, str) or not encoded:
        raise MediaError("文件内容为空")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise MediaError("文件内容不是有效 Base64") from error
    limit = MAX_PDF_BYTES if mime == "application/pdf" else MAX_IMAGE_BYTES
    if not content or len(content) > limit:
        raise MediaError(f"文件大小必须在 1 B～{limit // (1024 * 1024)} MB 之间")
    signatures = {
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
        "application/pdf": content.startswith(b"%PDF-"),
    }
    if not signatures[mime]:
        raise MediaError("文件内容与声明类型不一致")
    return name, mime, content


def _parse_vision_response(raw: str, page: int) -> list[dict[str, Any]]:
    if not isinstance(raw, str) or not raw.strip() or "```" in raw:
        raise MediaError("视觉模型返回格式异常")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise MediaError("视觉模型返回的不是单一 JSON 对象") from error
    if not isinstance(data, dict) or set(data) != {"questions"} or not isinstance(data["questions"], list):
        raise MediaError("视觉模型返回字段不符合白名单")
    if not 1 <= len(data["questions"]) <= 12:
        raise MediaError("当前页面未识别到题目或题目数量异常")

    parsed: list[dict[str, Any]] = []
    required = {"question_text", "confidence", "supported", "reason", "parameters", "current_direction", "asks"}
    for index, question in enumerate(data["questions"], 1):
        if not isinstance(question, dict) or set(question) != required:
            raise MediaError("视觉模型的题目字段不符合白名单")
        try:
            question_text = normalize_question(question["question_text"])
        except ValueError as error:
            raise MediaError(str(error)) from error
        confidence = question["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise MediaError("confidence 必须在 0～1")
        if not isinstance(question["supported"], bool):
            raise MediaError("supported 必须是布尔值")
        reason = question["reason"]
        if not isinstance(reason, str) or len(reason) > 200:
            raise MediaError("reason 必须是 200 字以内文本")
        parameters = question["parameters"]
        if not isinstance(parameters, dict) or set(parameters) != EXPECTED_PARAMETER_KEYS:
            raise MediaError("视觉参数字段不符合白名单")
        for key in ("magnetic_field_t", "rod_length_m", "rod_speed_m_s", "resistance_ohm"):
            value = parameters[key]
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise MediaError(f"{key} 必须是数值或 null")
        if parameters["field_direction"] not in {"into_page", "out_of_page", None}:
            raise MediaError("field_direction 取值无效")
        if parameters["motion_direction"] not in {"left", "right", None}:
            raise MediaError("motion_direction 取值无效")
        if question["current_direction"] not in CURRENT_DIRECTIONS | {None}:
            raise MediaError("current_direction 取值无效")
        asks = question["asks"]
        if not isinstance(asks, list) or not 1 <= len(asks) <= 12 or any(
            not isinstance(item, str) or not item.strip() or len(item.strip()) > 160 for item in asks
        ):
            raise MediaError("asks 必须是非空文本数组")
        complete = all(value is not None for value in parameters.values()) and question["current_direction"] is not None
        ready = bool(question["supported"] and confidence >= LOW_CONFIDENCE_THRESHOLD and complete)
        parsed.append(
            {
                "id": f"p{page}-q{index}",
                "page": page,
                "question_text": question_text,
                "confidence": round(float(confidence), 3),
                "supported": question["supported"],
                "reason": reason.strip(),
                "parameters": parameters,
                "current_direction": question["current_direction"],
                "asks": [item.strip() for item in asks],
                "ready_for_confirmation": ready,
            }
        )
    return parsed


class MediaParser:
    def __init__(self, client: KimiCodeClient) -> None:
        self.client = client

    def parse(self, filename: object, mime_type: object, data_base64: object) -> dict[str, Any]:
        name, mime, content = decode_upload(filename, mime_type, data_base64)
        images = [(1, mime, content)] if mime != "application/pdf" else self._render_pdf(content)
        questions: list[dict[str, Any]] = []
        for page, image_mime, image in images:
            raw = self.client.complete_vision(
                VISION_SYSTEM_PROMPT,
                f"请读取文件 {name} 的第 {page} 页，若一页有多题请分别输出。",
                image_mime,
                image,
            )
            try:
                questions.extend(_parse_vision_response(raw, page))
            except MediaError as error:
                questions.append(
                    {
                        "id": f"p{page}-q1",
                        "page": page,
                        "question_text": "图片内容无法可靠识别，请老师补述完整题意后再试。",
                        "confidence": 0.0,
                        "supported": False,
                        "reason": str(error),
                        "parameters": {key: None for key in EXPECTED_PARAMETER_KEYS},
                        "current_direction": None,
                        "asks": ["请补述题目所求量"],
                        "ready_for_confirmation": False,
                    }
                )
        ready_count = sum(bool(item["ready_for_confirmation"]) for item in questions)
        return {
            "source_input_type": "pdf" if mime == "application/pdf" else "image",
            "filename": name,
            "page_count": len(images),
            "confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
            "status": "awaiting_confirmation" if ready_count else "needs_input",
            "message": (
                "请选择一道题，核对并确认全部参数。"
                if ready_count
                else "识别置信不足或关键参数不完整，请补述题意或转人工处理。"
            ),
            "questions": questions,
        }

    def _render_pdf(self, content: bytes) -> list[tuple[int, str, bytes]]:
        try:
            import pypdfium2 as pdfium
        except ImportError:
            pdfium = None
        if pdfium is not None:
            try:
                document = pdfium.PdfDocument(content)
                page_count = len(document)
                if not 1 <= page_count <= MAX_PDF_PAGES:
                    raise MediaError(f"PDF 目前支持 1～{MAX_PDF_PAGES} 页")
                rendered: list[tuple[int, str, bytes]] = []
                for index in range(page_count):
                    page = document[index]
                    bitmap = page.render(scale=2.0)
                    image = bitmap.to_pil()
                    output = io.BytesIO()
                    image.save(output, format="PNG")
                    rendered.append((index + 1, "image/png", output.getvalue()))
                    image.close()
                    bitmap.close()
                    page.close()
                document.close()
                return rendered
            except MediaError:
                raise
            except Exception as error:
                raise MediaError("PDF 文件损坏、加密或无法读取") from error

        pdftoppm = shutil.which("pdftoppm")
        pdfinfo = shutil.which("pdfinfo")
        if not pdftoppm or not pdfinfo:
            raise MediaError("服务器缺少 PDF 转图组件，请上传题目截图")
        with tempfile.TemporaryDirectory(prefix="courseware-pdf-") as temp_dir:
            root = Path(temp_dir)
            source = root / "source.pdf"
            source.write_bytes(content)
            try:
                info = subprocess.run(
                    [pdfinfo, str(source)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=15,
                )
                match = re.search(r"^Pages:\s+(\d+)\s*$", info.stdout, re.MULTILINE)
                if not match:
                    raise MediaError("无法读取 PDF 页数")
                page_count = int(match.group(1))
                if not 1 <= page_count <= MAX_PDF_PAGES:
                    raise MediaError(f"PDF 目前支持 1～{MAX_PDF_PAGES} 页")
                target = root / "page"
                subprocess.run(
                    [pdftoppm, "-png", "-r", "144", str(source), str(target)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=45,
                )
            except subprocess.TimeoutExpired as error:
                raise MediaError("PDF 转图超时，请拆分或上传截图") from error
            except subprocess.CalledProcessError as error:
                raise MediaError("PDF 文件损坏、加密或无法读取") from error
            pages = sorted(root.glob("page-*.png"))
            if len(pages) != page_count:
                raise MediaError("PDF 转图页数不一致")
            return [(index, "image/png", path.read_bytes()) for index, path in enumerate(pages, 1)]


class MediaConfirmationWorkflow:
    """Own parse sessions so the browser cannot forge a confirmed generation."""

    def __init__(self, parser: MediaParser, generator: GenerationManager) -> None:
        self.parser = parser
        self.generator = generator
        self._sessions: dict[str, dict[str, Any]] = {}
        self._confirmations: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def parse_upload(self, filename: object, mime_type: object, data_base64: object) -> dict[str, Any]:
        parsed = self.parser.parse(filename, mime_type, data_base64)
        parse_id = uuid.uuid4().hex[:24]
        session = {"id": parse_id, **parsed, "teacher_confirmed": False}
        with self._lock:
            self._sessions[parse_id] = session
        return json.loads(json.dumps(session, ensure_ascii=False))

    def confirm_and_submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        expected = {
            "parse_id",
            "question_id",
            "teacher_confirmed",
            "question_text",
            "parameters",
            "current_direction",
            "asks",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise MediaError("确认请求字段不符合白名单")
        if payload["teacher_confirmed"] is not True:
            raise MediaError("必须由老师显式确认后才能生成")
        with self._lock:
            session = self._sessions.get(payload["parse_id"])
            if session is None:
                raise MediaError("解析记录不存在或已失效")
            if session["teacher_confirmed"]:
                raise MediaError("该解析记录已经确认，不可重复提交")
            original = next(
                (item for item in session["questions"] if item["id"] == payload["question_id"]),
                None,
            )
            if original is None:
                raise MediaError("所选题目不存在")
            if not original["supported"]:
                raise MediaError("该题超出当前模板范围，已转人工处理")

        question = normalize_question(payload["question_text"])
        parameters = payload["parameters"]
        if not isinstance(parameters, dict) or set(parameters) != EXPECTED_PARAMETER_KEYS:
            raise MediaError("确认参数字段不符合白名单")
        try:
            config = build_template_config(question, parameters)
        except (KeyError, TypeError, ValueError) as error:
            raise MediaError(str(error)) from error
        model = derive_physics(config)
        expected_current = "d_to_c" if model["current_sign"] > 0 else "c_to_d"
        if payload["current_direction"] not in CURRENT_DIRECTIONS:
            raise MediaError("请确认电流方向")
        if payload["current_direction"] != expected_current:
            raise MediaError("电流方向与已确认的磁场、运动方向不一致，请重新核对")
        asks = payload["asks"]
        if not isinstance(asks, list) or not 1 <= len(asks) <= 12 or any(
            not isinstance(item, str) or not item.strip() or len(item.strip()) > 160 for item in asks
        ):
            raise MediaError("请确认至少一个所求量")

        confirmation_id = uuid.uuid4().hex[:24]
        confirmation = {
            "id": confirmation_id,
            "parse_id": session["id"],
            "question_id": original["id"],
            "source_input_type": session["source_input_type"],
            "original_parameters": original["parameters"],
            "confirmed_parameters": dict(parameters),
            "current_direction": expected_current,
            "asks": [item.strip() for item in asks],
        }
        with self._lock:
            session["teacher_confirmed"] = True
            self._confirmations[confirmation_id] = confirmation
        self.generator.authorize_confirmation(confirmation_id)
        job = self.generator.submit_confirmed(
            confirmation_id=confirmation_id,
            question=question,
            parameters=parameters,
            source_input_type=session["source_input_type"],
            asks=confirmation["asks"],
        )
        return {
            "confirmation_id": confirmation_id,
            "corrections_applied": original["parameters"] != parameters,
            "job": job,
        }
