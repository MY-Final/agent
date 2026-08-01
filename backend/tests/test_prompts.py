import tempfile
import unittest
from pathlib import Path

from app.skills.parse_template import build_suggestion_prompt
from app.skills.prompt_loader import PROMPTS, load_prompt_templates, prompts_dir


class PromptTemplateTests(unittest.TestCase):
    def test_bundled_templates_load_with_expected_placeholders(self) -> None:
        self.assertEqual(
            set(PROMPTS),
            {"extract_system", "extract_user", "suggest_system", "suggest_user"},
        )
        self.assertIn("禁止", PROMPTS["extract_system"].content)
        self.assertIn(
            "qualification.category 只能使用",
            PROMPTS["extract_system"].content,
        )
        self.assertIn("qualifications", PROMPTS["suggest_system"].content)

    def test_extract_user_renders_placeholders(self) -> None:
        rendered = PROMPTS["extract_user"].render(
            template_description="项目名称（文本）",
            tender_text="项目名称：智慧园区建设项目",
        )
        self.assertIn("项目名称（文本）", rendered)
        self.assertIn("项目名称：智慧园区建设项目", rendered)

    def test_render_missing_parameter_raises(self) -> None:
        with self.assertRaises(ValueError):
            PROMPTS["extract_user"].render(template_description="缺少原文参数")

    def test_suggest_user_with_reference_text(self) -> None:
        rendered = build_suggestion_prompt(
            "提取资格要求与评分办法",
            "第一章 资格要求：具备甲级资质",
        )
        self.assertIn("提取资格要求与评分办法", rendered)
        self.assertIn("第一章 资格要求：具备甲级资质", rendered)
        self.assertIn("参考原文", rendered)

    def test_suggest_user_without_reference_text(self) -> None:
        rendered = build_suggestion_prompt("提取资格要求", None)
        self.assertIn("提取资格要求", rendered)
        self.assertNotIn("参考原文", rendered)

    def test_invalid_template_file_fails_fast(self) -> None:
        source = prompts_dir()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for path in source.iterdir():
                (target / path.name).write_text(
                    path.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            # 删掉 extract_user 的必需占位符，加载时必须立即失败。
            (target / "extract_user.txt").write_text(
                "缺少占位符的模板 {{template_description}}",
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                load_prompt_templates(target)


if __name__ == "__main__":
    unittest.main()
