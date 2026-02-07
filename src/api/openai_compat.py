"""
OpenAI互換APIエンドポイント

nanobotやLiteLLM等のOpenAI互換クライアントからSmart Routerを利用可能にする。
POST /v1/chat/completions でチャット補完、GET /v1/models でモデル一覧を提供。
"""

import json
import logging
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent  # src/
router_js_path = project_root.parent / "router.js"

openai_router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """OpenAI chat message"""
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Any]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """OpenAI chat completion request"""
    model: str
    messages: List[ChatMessage] = Field(..., min_length=1)
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=100000)
    stream: Optional[bool] = False
    # 受け付けるが処理しないフィールド（互換性のため）
    tools: Optional[List[Any]] = None
    tool_choice: Optional[Any] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[Any] = None
    n: Optional[int] = None
    user: Optional[str] = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: Dict[str, Any]
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: UsageInfo


class ModelObject(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "smart-router"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelObject]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _parse_model_name(model: str) -> Optional[str]:
    """
    OpenAIリクエストのmodelフィールドをSmart Routerのforce_modelに変換。

    LiteLLMは 'hosted_vllm/<model>' プレフィックスを付与するため除去する。
    - 'auto' / 'smart-router' → None（自動ルーティング）
    - 'local' → 'local'
    - 'cloud' / 'claude' → 'cloud'
    - 'local:<model-id>' → そのまま
    """
    for prefix in ("hosted_vllm/", "openai/", "vllm/"):
        if model.startswith(prefix):
            model = model[len(prefix):]
            break

    if model in ("auto", "smart-router", ""):
        return None
    if model == "local":
        return "local"
    if model in ("cloud", "claude"):
        return "cloud"
    if model.startswith("local:"):
        return model
    return None


def _extract_input_from_messages(messages: List[ChatMessage]) -> str:
    """
    messages配列からrouter.jsへの入力テキストを抽出。

    最後のuserメッセージを使用。systemメッセージがあればプレフィックスとして付加。
    """
    system_msg = None
    last_user_msg = None

    for msg in messages:
        if msg.role == "system" and msg.content:
            system_msg = msg.content
        if msg.role == "user" and msg.content:
            last_user_msg = msg.content

    if not last_user_msg:
        last_user_msg = "\n".join(
            m.content for m in messages if m.content
        ) or ""

    if system_msg:
        return f"[System: {system_msg}]\n\n{last_user_msg}"
    return last_user_msg


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@openai_router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI互換チャット補完エンドポイント"""

    if not router_js_path.exists():
        raise HTTPException(status_code=500, detail="Internal server error")

    # モデル名パース
    force_model = _parse_model_name(request.model)

    # メッセージ抽出
    input_text = _extract_input_from_messages(request.messages)
    if not input_text:
        raise HTTPException(status_code=400, detail="No input content found in messages")
    if len(input_text) > 100000:
        raise HTTPException(status_code=400, detail="Input too long")

    input_file = None
    try:
        input_data = {
            "input": input_text,
            "forceModel": force_model,
            "context": {},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(input_data, f)
            input_file = f.name

        result = subprocess.run(
            ["node", str(router_js_path), "--api-mode", input_file],
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
        )

        if result.returncode != 0:
            logger.error(f"router.js実行エラー（コード: {result.returncode}）")
            raise HTTPException(status_code=500, detail="Model execution failed")

        response_data = json.loads(result.stdout)

        if not response_data.get("success"):
            error_msg = response_data.get("error", "Unknown error")
            logger.error(f"router.jsルーティング失敗: {error_msg}")
            raise HTTPException(status_code=500, detail="Model execution failed")

        # OpenAI形式に変換
        metadata = response_data.get("metadata", {})
        tokens = metadata.get("tokens", {})
        model_ref = metadata.get("modelRef", response_data.get("model", "smart-router"))

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            created=int(time.time()),
            model=model_ref or "smart-router",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message={
                        "role": "assistant",
                        "content": response_data.get("response", ""),
                    },
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=tokens.get("input", 0),
                completion_tokens=tokens.get("output", 0),
                total_tokens=tokens.get("input", 0) + tokens.get("output", 0),
            ),
        )

    except subprocess.TimeoutExpired:
        logger.error("router.js実行タイムアウト（60秒）")
        raise HTTPException(status_code=504, detail="Request timed out")
    except json.JSONDecodeError:
        logger.error("router.js出力パース失敗")
        raise HTTPException(status_code=500, detail="Failed to parse model response")
    except HTTPException:
        raise
    except Exception:
        logger.error("チャット補完エラー", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if input_file:
            try:
                os.unlink(input_file)
            except OSError:
                pass


@openai_router.get("/models", response_model=ModelListResponse)
async def list_models():
    """利用可能モデル一覧をOpenAI形式で返却"""
    models = [
        ModelObject(id="smart-router"),
        ModelObject(id="auto"),
        ModelObject(id="local"),
        ModelObject(id="cloud"),
    ]

    try:
        from scanner.registry import ModelRegistry

        registry_path = str(project_root.parent / "data" / "model_registry.json")
        registry = ModelRegistry(cache_path=registry_path)
        for m in registry.get_local_models():
            models.append(ModelObject(id=f"local:{m.id}"))
    except Exception:
        logger.debug("レジストリからローカルモデル読み込みスキップ", exc_info=True)

    return ModelListResponse(data=models)
