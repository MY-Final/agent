import unittest

from app.schemas.skills.parse import ParseTemplate
from app.skills.llm import _fill_missing_template_data, _format_raw_llm_content
from app.skills.parse_template import SEED_PARSE_TEMPLATE


class FormatRawLlmContentTests(unittest.TestCase):
    def test_pretty_prints_valid_json(self) -> None:
        formatted = _format_raw_llm_content(
            '{"data": {"overview": {"project_name": null}}, "confidence": 0.5}'
        )
        self.assertIn("\n", formatted)
        self.assertIn('"project_name": null', formatted)

    def test_keeps_non_json_text_as_is(self) -> None:
        text = "抱歉，我无法完成该任务。"
        self.assertEqual(_format_raw_llm_content(text), text)

    def test_truncates_long_content(self) -> None:
        content = "x" * 5000
        formatted = _format_raw_llm_content(content, limit=1000)
        self.assertLessEqual(len(formatted), 1000 + len("\n...(已截断，完整内容见服务端日志)"))
        self.assertIn("已截断", formatted)

    def test_empty_content(self) -> None:
        self.assertEqual(_format_raw_llm_content(""), "<空响应>")
        self.assertEqual(_format_raw_llm_content(None), "<空响应>")


class FillMissingTemplateDataTests(unittest.TestCase):
    def test_missing_grid_section_is_filled_with_field_defaults(self) -> None:
        filled = _fill_missing_template_data(
            SEED_PARSE_TEMPLATE,
            {"overview": None},
        )
        overview = filled["overview"]
        self.assertIn("project_name", overview)
        self.assertIsNone(overview["project_name"])
        self.assertIn("budget", overview)

    def test_partial_grid_section_gets_missing_fields_filled(self) -> None:
        filled = _fill_missing_template_data(
            SEED_PARSE_TEMPLATE,
            {"overview": {"project_name": "测试项目"}},
        )
        overview = filled["overview"]
        self.assertEqual(overview["project_name"], "测试项目")
        self.assertIsNone(overview["budget"])

    def test_list_section_missing_is_filled_with_empty_list(self) -> None:
        filled = _fill_missing_template_data(
            SEED_PARSE_TEMPLATE,
            {"disqualification_items": None},
        )
        self.assertEqual(filled["disqualification_items"], [])

    def test_returns_template_valid_parse_result_shape(self) -> None:
        filled = _fill_missing_template_data(SEED_PARSE_TEMPLATE, {})
        template = ParseTemplate.model_validate(
            SEED_PARSE_TEMPLATE.model_dump()
        )
        self.assertEqual(
            set(filled),
            {section.id for section in template.sections},
        )


if __name__ == "__main__":
    unittest.main()
