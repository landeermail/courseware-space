from __future__ import annotations

import json
import unittest

from research.generation.harness.contracts import ContractError, GeneratedArtifact, GeneratedModel, GeneratedView


def html(script: str) -> str:
    return f"""<!doctype html><html><head><style>body{{min-height:100vh}}</style></head><body><svg></svg><input data-control><input data-control><span data-physical-time></span><span data-demo-time></span><span data-readout></span><button data-replay>回放</button><!--HARNESS_PRIMITIVES--><!--HARNESS_MODEL--><!--HARNESS_INPUT--><script>{script}</script></body></html>"""


class ViewContractTests(unittest.TestCase):
    def parse(self, source: str) -> GeneratedView:
        return GeneratedView.parse(json.dumps({"teaching_intent": "观察、操控并验证物理过程中的因果关系。", "html": source}, ensure_ascii=False))

    def test_safe_svg_namespace_and_local_aliases_are_allowed(self) -> None:
        script = """const P=window.CoursewarePrimitives;const M=window.coursewareModel;document.createElementNS('http://www.w3.org/2000/svg','line');const sample=M.sample(globalThis.__HARNESS_INPUT__);P.createTimeline({durationPhysicalS:1,onChange(s){P.formatPhysicalTime(s.physicalTimeS);P.formatDemoRate(s.demoRate);}});"""
        self.assertIsInstance(self.parse(html(script)), GeneratedView)

    def test_external_url_and_direct_animation_loop_are_rejected(self) -> None:
        base = "const P=CoursewarePrimitives,M=coursewareModel;M.sample({});P.createTimeline({durationPhysicalS:1,onChange(s){P.formatPhysicalTime(s.physicalTimeS);P.formatDemoRate(s.demoRate)}});"
        with self.assertRaises(ContractError):
            self.parse(html(base + "fetch('https://example.com')"))
        with self.assertRaises(ContractError):
            self.parse(html(base + "requestAnimationFrame(()=>{})"))

    def test_dynamic_code_and_network_capabilities_are_rejected(self) -> None:
        base = "const P=CoursewarePrimitives,M=coursewareModel;M.sample({});P.createTimeline({durationPhysicalS:1,onChange(s){P.formatPhysicalTime(s.physicalTimeS);P.formatDemoRate(s.demoRate)}});"
        for capability in ("Function('return 1')", "navigator.sendBeacon('/x','y')", "new Worker('/x.js')", "<iframe src='about:blank'></iframe>"):
            with self.subTest(capability=capability), self.assertRaises(ContractError):
                self.parse(html(base + capability))

    def test_render_injects_a_default_deny_content_security_policy(self) -> None:
        artifact = GeneratedArtifact(
            title="抛体时空实验室",
            domain="projectile",
            teaching_intent="观察、操控并验证物理过程中的因果关系。",
            model_js="globalThis.coursewareModel=Object.freeze({sample(input){return {states:[],events:{}}}});",
            html=html("const P=CoursewarePrimitives,M=coursewareModel;M.sample({});P.createTimeline({durationPhysicalS:1,onChange(s){P.formatPhysicalTime(s.physicalTimeS);P.formatDemoRate(s.demoRate)}});"),
        )
        rendered = artifact.render("globalThis.CoursewarePrimitives={};", {"scenario": {}})
        self.assertIn('Content-Security-Policy', rendered)
        self.assertIn("connect-src 'none'", rendered)
        self.assertIn("data-harness-initial-scenario", rendered)
        self.assertIn("首次采样场景与老师确认题设不一致", rendered)
        self.assertIn("data-harness-runtime-error", rendered)

    def test_missing_head_is_rejected_before_render(self) -> None:
        source = html("const P=CoursewarePrimitives,M=coursewareModel;M.sample({});P.createTimeline({durationPhysicalS:1,onChange(s){P.formatPhysicalTime(s.physicalTimeS);P.formatDemoRate(s.demoRate)}});")
        with self.assertRaisesRegex(ContractError, "head"):
            self.parse(source.replace("<head>", "").replace("</head>", ""))

    def test_control_markers_in_script_text_cannot_fake_real_parameter_controls(self) -> None:
        source = html("const fake='data-control data-control';const P=CoursewarePrimitives,M=coursewareModel;M.sample({});P.createTimeline({durationPhysicalS:1,onChange(s){P.formatPhysicalTime(s.physicalTimeS);P.formatDemoRate(s.demoRate)}});")
        source = source.replace("<input data-control><input data-control>", "")
        with self.assertRaisesRegex(ContractError, "input/select"):
            self.parse(source)

    def test_javascript_string_with_literal_newline_is_normalized(self) -> None:
        script = "const P=CoursewarePrimitives,M=coursewareModel;M.sample({});P.createTimeline({durationPhysicalS:1,onChange(s){P.formatPhysicalTime(s.physicalTimeS);P.formatDemoRate(s.demoRate)}});const readout='第一行\n第二行';"
        view = self.parse(html(script))
        self.assertIn("第一行\\n第二行", view.html)
        self.assertEqual(view.normalizations, ("escaped_quoted_script_newlines",))

    def test_other_javascript_syntax_errors_are_still_rejected(self) -> None:
        script = "const P=CoursewarePrimitives,M=coursewareModel;M.sample({});P.createTimeline({durationPhysicalS:1,onChange(s){P.formatPhysicalTime(s.physicalTimeS);P.formatDemoRate(s.demoRate)}});const broken=;"
        with self.assertRaisesRegex(ContractError, "脚本语法"):
            self.parse(html(script))

    def test_harness_placeholders_inside_script_are_rejected(self) -> None:
        source = html("const P=CoursewarePrimitives,M=coursewareModel;M.sample({});P.createTimeline({durationPhysicalS:1,onChange(s){P.formatPhysicalTime(s.physicalTimeS);P.formatDemoRate(s.demoRate)}});")
        source = source.replace("<!--HARNESS_PRIMITIVES-->", "").replace(
            "<script>", "<script><!--HARNESS_PRIMITIVES-->", 1
        )
        with self.assertRaisesRegex(ContractError, "script 元素之外"):
            self.parse(source)


class ModelContractTests(unittest.TestCase):
    def parse(self, model_js: str) -> GeneratedModel:
        return GeneratedModel.parse(
            json.dumps({"title": "可复验物理模型", "domain": "projectile", "model_js": model_js}, ensure_ascii=False),
            "projectile",
        )

    def test_random_clock_and_callable_function_constructor_are_rejected(self) -> None:
        prefix = "globalThis.coursewareModel=Object.freeze({sample(input){"
        suffix = "return {states:[],events:{}};}});"
        for expression in ("Math.random();", "Date.now();", "Function('return 1')();", "setTimeout(()=>{},1);"):
            with self.subTest(expression=expression), self.assertRaises(ContractError):
                self.parse(prefix + expression + suffix)
