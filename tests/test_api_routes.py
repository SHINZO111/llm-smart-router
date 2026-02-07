"""
API Routes 追加テストモジュール

バリデーション、エクスポート/インポート、ルーター統計、モデル管理エンドポイントのテスト。
基本CRUDは src/tests/test_api.py でカバー済み。
"""
import sys
import json
import io
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# プロジェクトルートをパスに追加
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from fastapi.testclient import TestClient
from api.main import app


client = TestClient(app)


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _create_conversation(title="Test", first_message=None):
    """テスト用会話を作成"""
    payload = {"title": title}
    if first_message:
        payload["first_message"] = first_message
    resp = client.post("/api/v1/conversations", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_topic(name="Test Topic"):
    """テスト用トピックを作成"""
    resp = client.post("/api/v1/topics", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# バリデーションテスト
# ---------------------------------------------------------------------------

class TestValidation:
    """入力バリデーションテスト"""

    def test_message_role_too_long(self):
        cid = _create_conversation()
        resp = client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"role": "x" * 21, "content": "hello"}
        )
        assert resp.status_code == 422

    def test_message_content_too_long(self):
        cid = _create_conversation()
        resp = client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"role": "user", "content": "x" * 100001}
        )
        assert resp.status_code == 422

    def test_message_model_too_long(self):
        cid = _create_conversation()
        resp = client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"role": "user", "content": "hi", "model": "x" * 101}
        )
        assert resp.status_code == 422

    def test_message_negative_tokens(self):
        cid = _create_conversation()
        resp = client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"role": "user", "content": "hi", "tokens": -1}
        )
        assert resp.status_code == 422

    def test_topic_name_too_long(self):
        resp = client.post(
            "/api/v1/topics",
            json={"name": "x" * 101}
        )
        assert resp.status_code == 422

    def test_topic_name_empty(self):
        resp = client.post(
            "/api/v1/topics",
            json={"name": ""}
        )
        assert resp.status_code == 422

    def test_topic_description_too_long(self):
        resp = client.post(
            "/api/v1/topics",
            json={"name": "ok", "description": "x" * 501}
        )
        assert resp.status_code == 422

    def test_topic_invalid_color(self):
        resp = client.post(
            "/api/v1/topics",
            json={"name": "ok", "color": "not-a-color"}
        )
        assert resp.status_code == 422

    def test_topic_valid_hex_color(self):
        resp = client.post(
            "/api/v1/topics",
            json={"name": "ok", "color": "#FF00FF"}
        )
        assert resp.status_code == 201
        assert resp.json()["color"] == "#FF00FF"

    def test_invalid_sort_field(self):
        resp = client.get("/api/v1/conversations?sort_by=invalid_field")
        assert resp.status_code == 400

    def test_invalid_status_filter(self):
        resp = client.get("/api/v1/conversations?status=invalid_status")
        assert resp.status_code == 400

    def test_list_limit_too_large(self):
        resp = client.get("/api/v1/conversations?limit=1001")
        assert resp.status_code == 422

    def test_list_limit_zero(self):
        resp = client.get("/api/v1/conversations?limit=0")
        assert resp.status_code == 422

    def test_messages_limit_cap(self):
        cid = _create_conversation()
        resp = client.get(f"/api/v1/conversations/{cid}/messages?limit=1001")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# エクスポート/インポートテスト
# ---------------------------------------------------------------------------

class TestExportImport:
    """エクスポート/インポートエンドポイントテスト"""

    def test_export_single_conversation(self):
        cid = _create_conversation("Export Test")
        # メッセージ追加
        client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"role": "user", "content": "Hello export"}
        )
        resp = client.get(f"/api/v1/export/{cid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "export_data" in data
        assert data["export_data"]["version"] == "1.0"
        conv = data["export_data"]["conversation"]
        assert conv["title"] == "Export Test"
        assert len(conv["messages"]) >= 1

    def test_export_nonexistent(self):
        resp = client.get(f"/api/v1/export/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_export_multiple(self):
        cid1 = _create_conversation("Multi 1")
        cid2 = _create_conversation("Multi 2")
        resp = client.post("/api/v1/export", json={"conversation_ids": [cid1, cid2]})
        assert resp.status_code == 200
        data = resp.json()["export_data"]
        assert data["metadata"]["total_conversations"] == 2

    def test_export_all(self):
        resp = client.post("/api/v1/export", json={})
        assert resp.status_code == 200
        data = resp.json()["export_data"]
        assert data["metadata"]["total_conversations"] >= 0

    def test_import_single_conversation(self):
        import_data = {
            "conversations": [{
                "title": "Imported Conv",
                "messages": [
                    {"role": "user", "content": "imported msg 1"},
                    {"role": "assistant", "content": "imported msg 2"},
                ]
            }]
        }
        content = json.dumps(import_data).encode("utf-8")
        resp = client.post(
            "/api/v1/import",
            files={"file": ("import.json", io.BytesIO(content), "application/json")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported_count"] == 1
        assert len(data["conversation_ids"]) == 1

        # インポートされた会話を確認
        cid = data["conversation_ids"][0]
        conv_resp = client.get(f"/api/v1/conversations/{cid}")
        assert conv_resp.status_code == 200
        assert conv_resp.json()["title"] == "Imported Conv"

    def test_import_invalid_json(self):
        resp = client.post(
            "/api/v1/import",
            files={"file": ("bad.json", io.BytesIO(b"not json"), "application/json")},
        )
        assert resp.status_code == 400

    def test_import_missing_conversations_key(self):
        content = json.dumps({"foo": "bar"}).encode("utf-8")
        resp = client.post(
            "/api/v1/import",
            files={"file": ("bad.json", io.BytesIO(content), "application/json")},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 検索テスト（追加）
# ---------------------------------------------------------------------------

class TestSearchExtended:
    """拡張検索テスト"""

    def test_search_messages_endpoint(self):
        cid = _create_conversation("SearchMsg Test", first_message="unique_search_term_xyz")
        resp = client.post(
            "/api/v1/search/messages",
            data={"query": "unique_search_term_xyz", "limit": "10"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_search_messages_invalid_role(self):
        resp = client.post(
            "/api/v1/search/messages",
            data={"query": "test", "role": "invalid_role"}
        )
        assert resp.status_code == 400

    def test_search_messages_with_role_filter(self):
        resp = client.post(
            "/api/v1/search/messages",
            data={"query": "test", "role": "user"}
        )
        assert resp.status_code == 200

    def test_search_conversations_with_limit(self):
        resp = client.get("/api/v1/search?q=test&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 5


# ---------------------------------------------------------------------------
# 統計テスト（追加）
# ---------------------------------------------------------------------------

class TestStatsExtended:
    """統計エンドポイント拡張テスト"""

    def test_stats_structure(self):
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_conversations" in data
        assert "total_messages" in data

    def test_stats_with_user_id(self):
        resp = client.get("/api/v1/stats?user_id=test_user")
        assert resp.status_code == 200

    def test_message_history_endpoint(self):
        cid = _create_conversation("History Test")
        client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"role": "user", "content": "Q1"}
        )
        resp = client.get(f"/api/v1/conversations/{cid}/history?max_messages=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == cid
        assert isinstance(data["messages"], list)

    def test_message_history_not_found(self):
        resp = client.get(f"/api/v1/conversations/{uuid.uuid4()}/history")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# モデル検出テスト
# ---------------------------------------------------------------------------

class TestModelEndpoints:
    """モデル検出エンドポイントテスト"""

    def test_get_detected_models(self):
        resp = client.get("/api/v1/models/detected")
        assert resp.status_code == 200
        data = resp.json()
        assert "local" in data
        assert "cloud" in data
        assert "total" in data

    def test_trigger_scan(self):
        resp = client.post("/api/v1/models/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("started", "already_running")


# ---------------------------------------------------------------------------
# ルーター統計テスト
# ---------------------------------------------------------------------------

class TestRouterEndpoints:
    """ルーターエンドポイントテスト"""

    def test_router_stats(self):
        resp = client.get("/api/v1/router/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "conversations" in data

    def test_config_reload(self):
        resp = client.post("/api/v1/router/config/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# RouterQueryRequestバリデーション
# ---------------------------------------------------------------------------

class TestRouterQueryValidation:
    """ルータークエリバリデーションテスト"""

    def test_empty_input_rejected(self):
        resp = client.post("/api/v1/router/query", json={"input": ""})
        assert resp.status_code == 422

    def test_input_too_long_rejected(self):
        resp = client.post("/api/v1/router/query", json={"input": "x" * 10001})
        assert resp.status_code == 422

    def test_context_too_many_keys(self):
        big_ctx = {f"key_{i}": "val" for i in range(51)}
        resp = client.post(
            "/api/v1/router/query",
            json={"input": "test", "context": big_ctx}
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Ollamaルートバリデーション
# ---------------------------------------------------------------------------

class TestOllamaValidation:
    """Ollamaエンドポイントバリデーションテスト"""

    def test_invalid_model_name_show(self):
        resp = client.get("/api/v1/models/ollama/model name with spaces!")
        assert resp.status_code == 400

    def test_model_name_too_long_show(self):
        resp = client.get(f"/api/v1/models/ollama/{'x' * 201}")
        assert resp.status_code == 400

    def test_invalid_model_name_delete(self):
        resp = client.delete("/api/v1/models/ollama/model name with spaces!")
        assert resp.status_code == 400

    def test_pull_invalid_name(self):
        resp = client.post(
            "/api/v1/models/ollama/pull",
            json={"name": "../../../bad"}
        )
        # field_validatorがキャッチ → 422、またはOllama未起動で503
        assert resp.status_code in (422, 503)


# ---------------------------------------------------------------------------
# OpenAI互換APIテスト
# ---------------------------------------------------------------------------

class TestOpenAICompat:
    """OpenAI互換APIエンドポイントテスト"""

    def test_models_endpoint(self):
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert "data" in data

    def test_chat_completions_missing_messages(self):
        resp = client.post("/v1/chat/completions", json={"model": "auto"})
        assert resp.status_code == 422

    def test_chat_completions_empty_messages(self):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "auto", "messages": []}
        )
        # 空messagesはバリデーションエラーまたはエラーレスポンス
        assert resp.status_code in (400, 422, 500)
