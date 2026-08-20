from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


VALIDATOR = Path(__file__).with_name("validate_learner_surface.py")


class LearnerSurfaceValidatorTests(unittest.TestCase):
    def run_validator(self, html: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "index.html"
            path.write_text(html, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(VALIDATOR), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_valid_typeset_symbol_and_semantic_binding_pass(self) -> None:
        result = self.run_validator(
            """
            <svg><g data-physics-id="normal-force-b"><text>Nᵦ</text></g></svg>
            <button data-physics-ref="normal-force-b">支持力</button>
            <span class="tex" data-tex="N_b"></span>
            <script>const internalName = "N_b";</script>
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_raw_visible_notation_and_internal_copy_fail(self) -> None:
        result = self.run_validator(
            "<main>N_b 机器代入：不用计算器</main>"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("裸源码符号", result.stderr)
        self.assertIn("内部生产语言", result.stderr)

    def test_missing_target_and_unfocusable_binding_fail(self) -> None:
        result = self.run_validator(
            '<span data-physics-ref="electric-force">库仑力</span>'
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("没有对应", result.stderr)
        self.assertIn("键盘聚焦", result.stderr)

    def test_explicit_internal_wrapper_is_not_learner_copy(self) -> None:
        result = self.run_validator(
            '<div data-audience="internal"><p>N_b artifact 验证</p></div>'
            '<main>可见正文</main>'
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
