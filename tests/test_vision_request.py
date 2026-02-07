"""
VisionRequestBuilder テストモジュール

VisionContent, VisionRequestBuilder のリクエスト構築、
モデル選択ロジック、トークン概算のテスト。
"""
import sys
from pathlib import Path

import pytest

# プロジェクトルートをパスに追加
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from multimodal.vision_request import VisionContent, VisionRequestBuilder


# ---------------------------------------------------------------------------
# VisionContent テスト
# ---------------------------------------------------------------------------

class TestVisionContent:
    """VisionContentデータクラスのテスト"""

    def test_text_only(self):
        vc = VisionContent(text="What is this?")
        assert vc.text == "What is this?"
        assert vc.image_base64 is None
        assert vc.mime_type == "image/jpeg"

    def test_with_image(self):
        vc = VisionContent(text="Describe", image_base64="abc123", mime_type="image/png")
        assert vc.image_base64 == "abc123"
        assert vc.mime_type == "image/png"


# ---------------------------------------------------------------------------
# VisionRequestBuilder 初期化テスト
# ---------------------------------------------------------------------------

class TestVisionRequestBuilderInit:
    """初期化テスト"""

    def test_claude_provider(self):
        builder = VisionRequestBuilder("claude")
        assert builder.provider == "claude"

    def test_gpt_provider(self):
        builder = VisionRequestBuilder("gpt")
        assert builder.provider == "gpt"

    def test_case_insensitive(self):
        builder = VisionRequestBuilder("Claude")
        assert builder.provider == "claude"

    def test_unsupported_provider(self):
        with pytest.raises(ValueError, match="Unsupported provider"):
            VisionRequestBuilder("gemini")


# ---------------------------------------------------------------------------
# Claude リクエスト構築テスト
# ---------------------------------------------------------------------------

class TestClaudeRequest:
    """Claude向けリクエスト構築テスト"""

    def setup_method(self):
        self.builder = VisionRequestBuilder("claude")

    def test_text_only_request(self):
        content = VisionContent(text="Hello")
        req = self.builder.build_request(content)

        assert req["model"] == "claude-3-5-sonnet-20241022"
        assert req["max_tokens"] == 4096
        assert req["temperature"] == 0.7
        assert len(req["messages"]) == 1
        msg = req["messages"][0]
        assert msg["role"] == "user"
        # テキストのみの場合、コンテンツは1要素
        assert len(msg["content"]) == 1
        assert msg["content"][0]["type"] == "text"
        assert msg["content"][0]["text"] == "Hello"

    def test_image_request(self):
        content = VisionContent(
            text="What is this?",
            image_base64="base64data",
            mime_type="image/png",
        )
        req = self.builder.build_request(content)

        msg_content = req["messages"][0]["content"]
        assert len(msg_content) == 2

        # 画像が先
        assert msg_content[0]["type"] == "image"
        assert msg_content[0]["source"]["type"] == "base64"
        assert msg_content[0]["source"]["media_type"] == "image/png"
        assert msg_content[0]["source"]["data"] == "base64data"

        # テキストが後
        assert msg_content[1]["type"] == "text"

    def test_system_prompt(self):
        content = VisionContent(text="Hi")
        req = self.builder.build_request(content, system_prompt="You are helpful")

        assert req["system"] == "You are helpful"

    def test_no_system_prompt(self):
        content = VisionContent(text="Hi")
        req = self.builder.build_request(content)

        assert "system" not in req

    def test_custom_model(self):
        content = VisionContent(text="Hi")
        req = self.builder.build_request(content, model="claude-3-opus-20240229")

        assert req["model"] == "claude-3-opus-20240229"

    def test_custom_max_tokens(self):
        content = VisionContent(text="Hi")
        req = self.builder.build_request(content, max_tokens=1000)

        assert req["max_tokens"] == 1000

    def test_custom_temperature(self):
        content = VisionContent(text="Hi")
        req = self.builder.build_request(content, temperature=0.3)

        assert req["temperature"] == 0.3


# ---------------------------------------------------------------------------
# GPT リクエスト構築テスト
# ---------------------------------------------------------------------------

class TestGPTRequest:
    """GPT向けリクエスト構築テスト"""

    def setup_method(self):
        self.builder = VisionRequestBuilder("gpt")

    def test_text_only_request(self):
        content = VisionContent(text="Hello")
        req = self.builder.build_request(content)

        assert req["model"] == "gpt-4o"
        assert len(req["messages"]) == 1
        msg = req["messages"][0]
        assert msg["role"] == "user"
        assert msg["content"][0]["type"] == "text"
        assert msg["content"][0]["text"] == "Hello"

    def test_image_request(self):
        content = VisionContent(
            text="Describe",
            image_base64="imgdata",
            mime_type="image/jpeg",
        )
        req = self.builder.build_request(content)

        msg_content = req["messages"][0]["content"]
        assert len(msg_content) == 2

        # テキストが先
        assert msg_content[0]["type"] == "text"

        # 画像が後（GPT形式）
        assert msg_content[1]["type"] == "image_url"
        url = msg_content[1]["image_url"]["url"]
        assert url.startswith("data:image/jpeg;base64,")
        assert "imgdata" in url
        assert msg_content[1]["image_url"]["detail"] == "auto"

    def test_system_prompt_as_message(self):
        content = VisionContent(text="Hi")
        req = self.builder.build_request(content, system_prompt="Be helpful")

        # GPTではsystemメッセージとして追加
        assert len(req["messages"]) == 2
        assert req["messages"][0]["role"] == "system"
        assert req["messages"][0]["content"] == "Be helpful"
        assert req["messages"][1]["role"] == "user"

    def test_no_system_prompt(self):
        content = VisionContent(text="Hi")
        req = self.builder.build_request(content)

        assert len(req["messages"]) == 1
        assert req["messages"][0]["role"] == "user"


# ---------------------------------------------------------------------------
# モデル選択テスト
# ---------------------------------------------------------------------------

class TestModelSelection:
    """select_model_for_image_task テスト"""

    def test_default_prefers_claude(self):
        result = VisionRequestBuilder.select_model_for_image_task()
        assert result["provider"] == "claude"

    def test_user_prefers_claude(self):
        result = VisionRequestBuilder.select_model_for_image_task(
            user_preference="claude", claude_available=True, gpt_available=True
        )
        assert result["provider"] == "claude"
        assert "claude" in result["model"]

    def test_user_prefers_gpt(self):
        result = VisionRequestBuilder.select_model_for_image_task(
            user_preference="gpt", claude_available=True, gpt_available=True
        )
        assert result["provider"] == "gpt"
        assert "gpt" in result["model"]

    def test_claude_unavailable_fallback_to_gpt(self):
        result = VisionRequestBuilder.select_model_for_image_task(
            claude_available=False, gpt_available=True
        )
        assert result["provider"] == "gpt"

    def test_gpt_unavailable_uses_claude(self):
        result = VisionRequestBuilder.select_model_for_image_task(
            claude_available=True, gpt_available=False
        )
        assert result["provider"] == "claude"

    def test_both_unavailable_returns_gpt_fallback(self):
        result = VisionRequestBuilder.select_model_for_image_task(
            claude_available=False, gpt_available=False
        )
        # どちらも使えない場合、GPTフォールバック
        assert result["provider"] == "gpt"
        assert result["model"] == "gpt-4o-mini"

    def test_user_prefers_claude_but_unavailable(self):
        result = VisionRequestBuilder.select_model_for_image_task(
            user_preference="claude", claude_available=False, gpt_available=True
        )
        assert result["provider"] == "gpt"


# ---------------------------------------------------------------------------
# トークン概算テスト
# ---------------------------------------------------------------------------

class TestTokenEstimation:
    """estimate_image_tokens テスト"""

    def test_small_image(self):
        # 256x256 → 1タイル
        tokens = VisionRequestBuilder.estimate_image_tokens(256, 256)
        assert tokens == 85 + 170  # 255

    def test_512x512(self):
        # 512x512 → 1タイル
        tokens = VisionRequestBuilder.estimate_image_tokens(512, 512)
        assert tokens == 85 + 170

    def test_1024x1024(self):
        # 1024x1024 → 2x2=4タイル
        tokens = VisionRequestBuilder.estimate_image_tokens(1024, 1024)
        assert tokens == 85 + (4 * 170)

    def test_1920x1080(self):
        # 1920x1080 → 4x3=12タイル (ceil(1920/512)=4, ceil(1080/512)=3)
        tiles_x = (1920 + 511) // 512  # 4
        tiles_y = (1080 + 511) // 512  # 3 (actually 2.109 → 3)
        expected = 85 + (tiles_x * tiles_y * 170)
        tokens = VisionRequestBuilder.estimate_image_tokens(1920, 1080)
        assert tokens == expected

    def test_single_pixel(self):
        tokens = VisionRequestBuilder.estimate_image_tokens(1, 1)
        assert tokens == 85 + 170


# ---------------------------------------------------------------------------
# Vision Capabilities テスト
# ---------------------------------------------------------------------------

class TestVisionCapabilities:
    """get_vision_capabilities テスト"""

    def test_returns_dict(self):
        caps = VisionRequestBuilder.get_vision_capabilities()
        assert isinstance(caps, dict)

    def test_claude_model_in_capabilities(self):
        caps = VisionRequestBuilder.get_vision_capabilities()
        assert "claude-3-5-sonnet-20241022" in caps

    def test_gpt_model_in_capabilities(self):
        caps = VisionRequestBuilder.get_vision_capabilities()
        assert "gpt-4o" in caps

    def test_capability_fields(self):
        caps = VisionRequestBuilder.get_vision_capabilities()
        for model_info in caps.values():
            assert "max_image_size" in model_info
            assert "supported_formats" in model_info
            assert "max_dimension" in model_info
            assert "strengths" in model_info
