"""
OpenAI互換APIエンドポイントのテスト
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# プロジェクトルートをsys.pathに追加
_src_root = str(Path(__file__).parent.parent / "src")
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from api.openai_compat import (
    ChatMessage,
    _extract_input_from_messages,
    _parse_model_name,
)


# ---------------------------------------------------------------------------
# _parse_model_name テスト
# ---------------------------------------------------------------------------

class TestParseModelName:
    """モデル名パースのテスト"""

    def test_hosted_vllm_smart_router(self):
        assert _parse_model_name("hosted_vllm/smart-router") is None

    def test_hosted_vllm_auto(self):
        assert _parse_model_name("hosted_vllm/auto") is None

    def test_hosted_vllm_local(self):
        assert _parse_model_name("hosted_vllm/local") == "local"

    def test_hosted_vllm_cloud(self):
        assert _parse_model_name("hosted_vllm/cloud") == "cloud"

    def test_hosted_vllm_claude(self):
        assert _parse_model_name("hosted_vllm/claude") == "cloud"

    def test_hosted_vllm_local_model_id(self):
        assert _parse_model_name("hosted_vllm/local:qwen/qwen3-4b") == "local:qwen/qwen3-4b"

    def test_plain_smart_router(self):
        assert _parse_model_name("smart-router") is None

    def test_plain_auto(self):
        assert _parse_model_name("auto") is None

    def test_plain_local(self):
        assert _parse_model_name("local") == "local"

    def test_plain_cloud(self):
        assert _parse_model_name("cloud") == "cloud"

    def test_plain_local_model_id(self):
        assert _parse_model_name("local:essentialai/rnj-1") == "local:essentialai/rnj-1"

    def test_empty_string(self):
        assert _parse_model_name("") is None

    def test_unknown_model(self):
        assert _parse_model_name("gpt-4o") is None

    def test_openai_prefix(self):
        assert _parse_model_name("openai/smart-router") is None

    def test_vllm_prefix(self):
        assert _parse_model_name("vllm/local") == "local"


# ---------------------------------------------------------------------------
# _extract_input_from_messages テスト
# ---------------------------------------------------------------------------

class TestExtractInputFromMessages:
    """メッセージ抽出のテスト"""

    def test_single_user_message(self):
        messages = [ChatMessage(role="user", content="Hello")]
        assert _extract_input_from_messages(messages) == "Hello"

    def test_system_and_user(self):
        messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello"),
        ]
        result = _extract_input_from_messages(messages)
        assert "[System: You are helpful]" in result
        assert "Hello" in result

    def test_multi_turn_uses_last_user(self):
        messages = [
            ChatMessage(role="user", content="First question"),
            ChatMessage(role="assistant", content="First answer"),
            ChatMessage(role="user", content="Second question"),
        ]
        assert _extract_input_from_messages(messages) == "Second question"

    def test_no_user_message_fallback(self):
        messages = [ChatMessage(role="system", content="System only")]
        result = _extract_input_from_messages(messages)
        assert "System only" in result

    def test_empty_content(self):
        messages = [ChatMessage(role="user", content=None)]
        result = _extract_input_from_messages(messages)
        assert result == ""

    def test_multiple_system_messages(self):
        messages = [
            ChatMessage(role="system", content="First system"),
            ChatMessage(role="system", content="Second system"),
            ChatMessage(role="user", content="Question"),
        ]
        result = _extract_input_from_messages(messages)
        assert "[System: Second system]" in result
        assert "Question" in result


# ---------------------------------------------------------------------------
# APIエンドポイント統合テスト（subprocess モック）
# ---------------------------------------------------------------------------

class TestChatCompletionsEndpoint:
    """チャット補完エンドポイントの統合テスト"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def _mock_router_response(self, success=True, response="Hello!", model="local"):
        """router.jsのモックレスポンスを生成"""
        data = {
            "success": success,
            "model": model,
            "response": response,
            "metadata": {
                "elapsed": "0.5s",
                "tokens": {"input": 10, "output": 5},
                "cost": 0.0,
                "modelRef": f"local:test-model",
            },
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(data)
        mock_result.stderr = ""
        return mock_result

    @patch("api.openai_compat.router_js_path")
    @patch("subprocess.run")
    def test_basic_completion(self, mock_run, mock_path, client):
        mock_path.exists.return_value = True
        mock_run.return_value = self._mock_router_response()

        resp = client.post("/v1/chat/completions", json={
            "model": "smart-router",
            "messages": [{"role": "user", "content": "Hello"}],
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] == "Hello!"
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["usage"]["prompt_tokens"] == 10
        assert data["usage"]["completion_tokens"] == 5
        assert data["id"].startswith("chatcmpl-")

    @patch("api.openai_compat.router_js_path")
    @patch("subprocess.run")
    def test_model_name_forwarded(self, mock_run, mock_path, client):
        mock_path.exists.return_value = True
        captured_input = {}

        def capture_and_respond(*args, **kwargs):
            # temp fileがまだ存在する間に内容を読む
            input_file_path = args[0][-1]
            with open(input_file_path, encoding="utf-8") as f:
                captured_input.update(json.load(f))
            return self._mock_router_response()

        mock_run.side_effect = capture_and_respond

        client.post("/v1/chat/completions", json={
            "model": "hosted_vllm/local",
            "messages": [{"role": "user", "content": "test"}],
        })

        assert captured_input["forceModel"] == "local"

    def test_empty_messages_rejected(self, client):
        resp = client.post("/v1/chat/completions", json={
            "model": "smart-router",
            "messages": [],
        })
        assert resp.status_code == 422

    @patch("api.openai_compat.router_js_path")
    def test_router_js_not_found(self, mock_path, client):
        mock_path.exists.return_value = False

        resp = client.post("/v1/chat/completions", json={
            "model": "smart-router",
            "messages": [{"role": "user", "content": "test"}],
        })
        assert resp.status_code == 500

    @patch("api.openai_compat.router_js_path")
    @patch("subprocess.run")
    def test_timeout_returns_504(self, mock_run, mock_path, client):
        import subprocess as sp
        mock_path.exists.return_value = True
        mock_run.side_effect = sp.TimeoutExpired(cmd="node", timeout=60)

        resp = client.post("/v1/chat/completions", json={
            "model": "smart-router",
            "messages": [{"role": "user", "content": "test"}],
        })
        assert resp.status_code == 504


class TestModelsEndpoint:
    """モデル一覧エンドポイントのテスト"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_models_list(self, client):
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        ids = [m["id"] for m in data["data"]]
        assert "smart-router" in ids
        assert "auto" in ids
        assert "local" in ids
        assert "cloud" in ids

    def test_model_object_format(self, client):
        resp = client.get("/v1/models")
        data = resp.json()
        for model in data["data"]:
            assert model["object"] == "model"
            assert model["owned_by"] == "smart-router"
