import json
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import SecretStr, ValidationError

from app.schemas.llm_provider import (
    LLMConnectionTestRequest,
    LLMModelListRequest,
    LLMProviderCreate,
    LLMProviderRead,
    LLMProviderUpdate,
)
from app.services.llm_connection_service import LLMConnectionService
from app.services.llm_provider_service import LLMProviderService, LLMRuntimeConfig
from app.skills.llm import TenderLLMClient
from app.skills.parse_template import SEED_PARSE_TEMPLATE
from app.skills.prompt_loader import PROMPTS
from app.utils.secrets import looks_like_masked_api_key, mask_api_key
from app.utils.validation import translate_validation_errors


class LLMProviderSchemaTests(unittest.TestCase):
    def test_create_normalizes_text_and_url(self) -> None:
        payload = LLMProviderCreate(
            name=" 测试提供商 ",
            base_url="https://example.com/v1/",
            api_key="sk-example-12345678",
            default_model=" test-model ",
        )

        self.assertEqual(payload.name, "测试提供商")
        self.assertEqual(payload.base_url, "https://example.com/v1")
        self.assertEqual(payload.default_model, "test-model")

    def test_disabled_provider_cannot_be_created_as_default(self) -> None:
        with self.assertRaises(ValidationError):
            LLMProviderCreate(
                name="测试提供商",
                base_url="https://example.com/v1",
                api_key="sk-example-12345678",
                default_model="test-model",
                is_default=True,
                is_enabled=False,
            )

    def test_empty_update_api_key_means_keep_existing_value(self) -> None:
        payload = LLMProviderUpdate(api_key="")

        self.assertIsNone(payload.api_key)


class LLMProviderSecretTests(unittest.TestCase):
    def test_api_key_mask_only_exposes_edges(self) -> None:
        masked = mask_api_key("sk-example-12345678")

        self.assertEqual(masked, "sk-e********5678")
        self.assertTrue(looks_like_masked_api_key(masked or ""))
        self.assertNotIn("example", masked or "")
        self.assertFalse(looks_like_masked_api_key("sk-live****key-value"))

    def test_read_schema_never_returns_full_key(self) -> None:
        now = datetime.now(timezone.utc)
        record = SimpleNamespace(
            id=uuid.uuid4(),
            name="测试提供商",
            provider_type="openai_compatible",
            base_url="https://example.com/v1",
            api_key="sk-example-12345678",
            default_model="test-model",
            timeout_seconds=120,
            is_default=True,
            is_enabled=True,
            extra_config={},
            created_at=now,
            updated_at=now,
        )

        result = LLMProviderRead.from_record(record)

        self.assertEqual(result.api_key, "sk-e********5678")

    def test_validation_error_input_masks_nested_api_key(self) -> None:
        errors = translate_validation_errors(
            [
                {
                    "type": "value_error",
                    "loc": ("body",),
                    "msg": "Value error",
                    "input": {
                        "name": "测试提供商",
                        "api_key": "sk-must-not-leak",
                        "extra_config": {"token": "nested-secret"},
                    },
                    "ctx": {"error": "配置错误"},
                }
            ]
        )

        self.assertEqual(errors[0]["input"]["api_key"], "********")
        self.assertEqual(
            errors[0]["input"]["extra_config"]["token"],
            "********",
        )

    def test_validation_error_masks_field_level_api_key(self) -> None:
        errors = translate_validation_errors(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "api_key"),
                    "msg": "Value error",
                    "input": "sk-field-secret",
                    "ctx": {"error": "API Key 不能为空"},
                }
            ]
        )

        self.assertEqual(errors[0]["input"], "********")


class LLMProviderServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_config_prefers_database_default(self) -> None:
        provider_id = uuid.uuid4()
        provider = SimpleNamespace(
            id=provider_id,
            name="数据库提供商",
            provider_type="openai_compatible",
            base_url="https://database.example/v1",
            api_key="sk-database-secret",
            default_model="database-model",
            timeout_seconds=180,
            extra_config={"temperature": 0.2},
        )
        session = AsyncMock()
        session.scalar.return_value = provider

        result = await LLMProviderService.get_current_config(session)

        self.assertEqual(result.source, "database")
        self.assertEqual(result.provider_id, provider_id)
        self.assertEqual(result.api_key, "sk-database-secret")
        self.assertEqual(result.default_model, "database-model")

    async def test_current_config_falls_back_to_env(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = None
        fake_settings = SimpleNamespace(
            llm_api_key=SecretStr("sk-env-secret"),
            llm_base_url="https://env.example/v1",
            llm_model_name="env-model",
            llm_timeout_seconds=90.0,
        )

        with patch(
            "app.services.llm_provider_service.settings",
            fake_settings,
        ):
            result = await LLMProviderService.get_current_config(session)

        self.assertEqual(result.source, "env")
        self.assertIsNone(result.provider_id)
        self.assertEqual(result.api_key, "sk-env-secret")
        self.assertEqual(result.default_model, "env-model")

    async def test_masked_update_does_not_replace_real_api_key(self) -> None:
        provider = SimpleNamespace(
            id=uuid.uuid4(),
            api_key="sk-real-secret-12345678",
            is_default=False,
            is_enabled=True,
        )
        session = AsyncMock()
        payload = LLMProviderUpdate(api_key="sk-r********5678")

        with (
            patch.object(
                LLMProviderService,
                "get_provider",
                AsyncMock(return_value=provider),
            ),
            patch.object(LLMProviderService, "_commit", AsyncMock()),
        ):
            result = await LLMProviderService.update_provider(
                session,
                provider.id,
                payload,
            )

        self.assertEqual(result.api_key, "sk-real-secret-12345678")


class LLMConnectionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_models_sorts_and_deduplicates_results(self) -> None:
        fake_client = SimpleNamespace(
            models=SimpleNamespace(
                list=AsyncMock(
                    return_value=SimpleNamespace(
                        data=[
                            SimpleNamespace(id="model-z"),
                            SimpleNamespace(id="model-a"),
                            SimpleNamespace(id="model-a"),
                        ]
                    )
                )
            ),
            close=AsyncMock(),
        )
        payload = LLMModelListRequest(
            base_url="https://example.com/v1",
            api_key="sk-test-secret",
        )

        with patch.object(
            LLMConnectionService,
            "_create_client",
            return_value=fake_client,
        ):
            result = await LLMConnectionService.list_models(AsyncMock(), payload)

        self.assertEqual(result.models, ["model-a", "model-z"])
        self.assertEqual(result.count, 2)
        fake_client.close.assert_awaited_once()

    async def test_edit_connection_can_reuse_saved_api_key(self) -> None:
        provider_id = uuid.uuid4()
        provider = SimpleNamespace(
            base_url="https://example.com/v1",
            api_key="sk-saved-secret",
        )
        payload = LLMModelListRequest(
            provider_id=provider_id,
            base_url="https://example.com/v1",
        )

        with patch.object(
            LLMProviderService,
            "get_provider",
            AsyncMock(return_value=provider),
        ):
            config = await LLMConnectionService._resolve_config(
                AsyncMock(),
                payload,
            )

        self.assertEqual(config.api_key, "sk-saved-secret")

    async def test_saved_api_key_cannot_be_reused_for_changed_base_url(self) -> None:
        provider_id = uuid.uuid4()
        provider = SimpleNamespace(
            base_url="https://saved.example/v1",
            api_key="sk-saved-secret",
        )
        payload = LLMModelListRequest(
            provider_id=provider_id,
            base_url="https://changed.example/v1",
        )

        with (
            patch.object(
                LLMProviderService,
                "get_provider",
                AsyncMock(return_value=provider),
            ),
            self.assertRaisesRegex(Exception, "服务地址已修改"),
        ):
            await LLMConnectionService._resolve_config(AsyncMock(), payload)

    async def test_connection_uses_selected_model(self) -> None:
        completion_create = AsyncMock(
            return_value=SimpleNamespace(choices=[SimpleNamespace()])
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=completion_create),
            ),
            close=AsyncMock(),
        )
        payload = LLMConnectionTestRequest(
            base_url="https://example.com/v1",
            api_key="sk-test-secret",
            model="selected-model",
        )

        with patch.object(
            LLMConnectionService,
            "_create_client",
            return_value=fake_client,
        ):
            result = await LLMConnectionService.test_connection(
                AsyncMock(),
                payload,
            )

        self.assertTrue(result.success)
        self.assertEqual(result.model, "selected-model")
        self.assertEqual(
            completion_create.await_args.kwargs["model"],
            "selected-model",
        )
        fake_client.close.assert_awaited_once()


class TenderLLMClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_extract_uses_runtime_provider_configuration(self) -> None:
        result_payload = {
            "data": {
                "overview": {
                    "project_name": "测试项目",
                    "project_code": None,
                    "budget": None,
                    "duration": None,
                    "location": None,
                    "purchaser": None,
                },
                "qualifications": [],
                "scoring_method": {},
                "disqualification_items": [],
                "key_dates": {},
                "other_key_points": [],
            },
            "raw_summary": None,
            "confidence": 0.9,
        }
        completion = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(result_payload))
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=120,
                completion_tokens=240,
                total_tokens=360,
            ),
        )
        create_completion = AsyncMock(return_value=completion)
        close_client = AsyncMock()
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create_completion),
            ),
            close=close_client,
        )
        runtime_config = LLMRuntimeConfig(
            source="database",
            provider_id=uuid.uuid4(),
            provider_name="数据库提供商",
            provider_type="openai_compatible",
            base_url="https://database.example/v1",
            api_key="sk-database-secret",
            default_model="database-model",
            timeout_seconds=180,
            extra_config={"temperature": 0.2, "ignored_option": True},
        )

        with (
            patch(
                "app.skills.llm.get_current_llm_config",
                AsyncMock(return_value=runtime_config),
            ),
            patch("app.skills.llm.AsyncOpenAI", return_value=fake_client) as client_class,
        ):
            result = await TenderLLMClient().extract(
                "测试标书原文",
                SEED_PARSE_TEMPLATE,
            )

        self.assertEqual(result.project_name, "测试项目")
        client_class.assert_called_once_with(
            api_key="sk-database-secret",
            timeout=180,
            base_url="https://database.example/v1",
        )
        call_options = create_completion.await_args.kwargs
        self.assertEqual(call_options["model"], "database-model")
        self.assertEqual(call_options["temperature"], 0.2)
        self.assertNotIn("ignored_option", call_options)
        self.assertEqual(
            call_options["messages"][0],
            {"role": "system", "content": PROMPTS["extract_system"].content},
        )
        self.assertIn("测试标书原文", call_options["messages"][1]["content"])
        close_client.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
