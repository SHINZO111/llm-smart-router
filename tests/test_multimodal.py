"""
ImageHandler テストモジュール

画像読み込み、リサイズ、Base64変換、フォーマット検証、サイズ制約のテスト。
テスト画像はPILで動的に生成する（外部ファイル依存なし）。
"""
import sys
import io
import base64
from pathlib import Path

import pytest

# プロジェクトルートをパスに追加
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

pytestmark = pytest.mark.skipif(not HAS_PIL, reason="Pillow is not installed")

from multimodal.image_handler import ImageHandler


# ---------------------------------------------------------------------------
# テストヘルパー
# ---------------------------------------------------------------------------

def _create_test_image(width=100, height=100, color="red", fmt="PNG") -> bytes:
    """テスト用画像をバイト列で生成"""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _create_rgba_image(width=100, height=100) -> bytes:
    """RGBA画像をバイト列で生成"""
    img = Image.new("RGBA", (width, height), (255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_palette_image(width=100, height=100) -> bytes:
    """パレットモード(P)画像をバイト列で生成"""
    img = Image.new("P", (width, height))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _save_image_to_file(tmp_path, filename="test.png", width=100, height=100,
                        color="red", fmt="PNG") -> Path:
    """テスト画像をファイルに保存"""
    data = _create_test_image(width, height, color, fmt)
    file_path = tmp_path / filename
    file_path.write_bytes(data)
    return file_path


# ---------------------------------------------------------------------------
# 初期化テスト
# ---------------------------------------------------------------------------

class TestImageHandlerInit:
    """ImageHandler 初期化テスト"""

    def test_initial_state(self):
        handler = ImageHandler()
        assert handler.has_image() is False
        assert handler.get_image() is None
        assert handler.get_dimensions() == (0, 0)
        assert handler.get_file_size_kb() is None

    def test_constants(self):
        assert ImageHandler.MAX_FILE_SIZE_MB == 5
        assert ImageHandler.MAX_DIMENSION == 2048
        assert ImageHandler.TARGET_DIMENSION == 1024
        assert ".png" in ImageHandler.SUPPORTED_FORMATS
        assert ".jpg" in ImageHandler.SUPPORTED_FORMATS


# ---------------------------------------------------------------------------
# ファイルからの読み込みテスト
# ---------------------------------------------------------------------------

class TestLoadFromFile:
    """ファイルからの画像読み込みテスト"""

    def test_load_png(self, tmp_path):
        path = _save_image_to_file(tmp_path, "test.png")
        handler = ImageHandler()
        success, msg = handler.load_from_file(path)

        assert success is True
        assert handler.has_image() is True
        assert handler.get_dimensions() == (100, 100)
        assert "100x100" in msg

    def test_load_jpg(self, tmp_path):
        path = _save_image_to_file(tmp_path, "test.jpg", fmt="JPEG")
        handler = ImageHandler()
        success, msg = handler.load_from_file(path)

        assert success is True

    def test_load_bmp(self, tmp_path):
        path = _save_image_to_file(tmp_path, "test.bmp", fmt="BMP")
        handler = ImageHandler()
        success, msg = handler.load_from_file(path)

        assert success is True

    def test_unsupported_format(self, tmp_path):
        path = tmp_path / "test.tiff"
        path.write_bytes(b"\x00" * 100)
        handler = ImageHandler()
        success, msg = handler.load_from_file(path)

        assert success is False
        assert "Unsupported format" in msg

    def test_file_too_large(self, tmp_path):
        path = tmp_path / "big.png"
        # 6MBのダミーPNG
        img = Image.new("RGB", (100, 100), "red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        # ファイルサイズを6MBに膨らませる
        data = buf.getvalue()
        path.write_bytes(data + b"\x00" * (6 * 1024 * 1024))

        handler = ImageHandler()
        success, msg = handler.load_from_file(path)

        assert success is False
        assert "too large" in msg

    def test_nonexistent_file(self, tmp_path):
        handler = ImageHandler()
        with pytest.raises((FileNotFoundError, OSError)):
            handler.load_from_file(tmp_path / "nonexistent.png")

    def test_get_file_size_kb(self, tmp_path):
        path = _save_image_to_file(tmp_path, "test.png")
        handler = ImageHandler()
        handler.load_from_file(path)

        size_kb = handler.get_file_size_kb()
        assert size_kb is not None
        assert size_kb > 0


# ---------------------------------------------------------------------------
# バイトデータからの読み込みテスト
# ---------------------------------------------------------------------------

class TestLoadFromBytes:
    """バイトデータからの画像読み込みテスト"""

    def test_load_from_bytes(self):
        data = _create_test_image(200, 150)
        handler = ImageHandler()
        success, msg = handler.load_from_bytes(data)

        assert success is True
        assert handler.has_image() is True
        assert handler.get_dimensions() == (200, 150)

    def test_load_rgba(self):
        data = _create_rgba_image()
        handler = ImageHandler()
        success, msg = handler.load_from_bytes(data)

        assert success is True
        # RGBAはRGBに変換される
        img = handler.get_image()
        assert img.mode == "RGB"

    def test_load_palette_mode(self):
        data = _create_palette_image()
        handler = ImageHandler()
        success, msg = handler.load_from_bytes(data)

        assert success is True
        img = handler.get_image()
        assert img.mode == "RGB"

    def test_data_too_large(self):
        data = b"\x00" * (6 * 1024 * 1024)
        handler = ImageHandler()
        success, msg = handler.load_from_bytes(data)

        assert success is False
        assert "too large" in msg

    def test_invalid_data(self):
        handler = ImageHandler()
        success, msg = handler.load_from_bytes(b"not an image")

        assert success is False
        assert "Load error" in msg

    def test_custom_mime_type(self):
        data = _create_test_image()
        handler = ImageHandler()
        handler.load_from_bytes(data, mime_type="image/webp")

        assert handler._mime_type == "image/webp"


# ---------------------------------------------------------------------------
# リサイズテスト
# ---------------------------------------------------------------------------

class TestResize:
    """画像リサイズテスト"""

    def test_no_resize_needed(self):
        data = _create_test_image(100, 100)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        resized = handler.resize_if_needed(max_dimension=200)
        assert resized.size == (100, 100)

    def test_resize_large_image(self):
        data = _create_test_image(2000, 1000)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        resized = handler.resize_if_needed(max_dimension=500)
        w, h = resized.size
        assert max(w, h) == 500
        # アスペクト比保持
        assert abs(w / h - 2.0) < 0.01

    def test_resize_square_image(self):
        data = _create_test_image(1000, 1000)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        resized = handler.resize_if_needed(max_dimension=500)
        assert resized.size == (500, 500)

    def test_resize_no_image_raises(self):
        handler = ImageHandler()
        with pytest.raises(ValueError, match="No image loaded"):
            handler.resize_if_needed()

    def test_resize_at_boundary(self):
        data = _create_test_image(1024, 512)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        # max_dimension == max(w,h) の場合、リサイズなし
        resized = handler.resize_if_needed(max_dimension=1024)
        assert resized.size == (1024, 512)


# ---------------------------------------------------------------------------
# Base64変換テスト
# ---------------------------------------------------------------------------

class TestBase64Conversion:
    """Base64エンコードテスト"""

    def test_to_base64(self):
        data = _create_test_image(200, 200)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        b64, mime = handler.to_base64()
        assert isinstance(b64, str)
        assert mime == "image/jpeg"
        # 有効なbase64であることを確認
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0

    def test_to_base64_no_image_raises(self):
        handler = ImageHandler()
        with pytest.raises(ValueError, match="No image loaded"):
            handler.to_base64()

    def test_to_bytes(self):
        data = _create_test_image(200, 200)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        result = handler.to_bytes()
        assert isinstance(result, bytes)
        assert len(result) > 0
        # JPEGのマジックナンバー
        assert result[:2] == b"\xff\xd8"

    def test_to_bytes_no_image_raises(self):
        handler = ImageHandler()
        with pytest.raises(ValueError, match="No image loaded"):
            handler.to_bytes()

    def test_quality_parameter(self):
        data = _create_test_image(500, 500)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        low_q = handler.to_bytes(quality=10)
        high_q = handler.to_bytes(quality=95)
        # 低品質の方がファイルサイズが小さい
        assert len(low_q) < len(high_q)


# ---------------------------------------------------------------------------
# プレビューサイズテスト
# ---------------------------------------------------------------------------

class TestPreviewSize:
    """プレビューサイズ計算テスト"""

    def test_no_image(self):
        handler = ImageHandler()
        assert handler.get_preview_size() == (0, 0)

    def test_small_image_no_scale(self):
        data = _create_test_image(200, 150)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        w, h = handler.get_preview_size(max_width=400, max_height=300)
        assert w == 200
        assert h == 150

    def test_large_image_scales_down(self):
        data = _create_test_image(800, 600)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        w, h = handler.get_preview_size(max_width=400, max_height=300)
        assert w <= 400
        assert h <= 300


# ---------------------------------------------------------------------------
# MIMEタイプテスト
# ---------------------------------------------------------------------------

class TestMimeType:
    """MIMEタイプ判定テスト"""

    def test_jpeg_extensions(self):
        handler = ImageHandler()
        assert handler._get_mime_type(".jpg") == "image/jpeg"
        assert handler._get_mime_type(".jpeg") == "image/jpeg"
        assert handler._get_mime_type(".JPG") == "image/jpeg"

    def test_png_extension(self):
        handler = ImageHandler()
        assert handler._get_mime_type(".png") == "image/png"

    def test_gif_extension(self):
        handler = ImageHandler()
        assert handler._get_mime_type(".gif") == "image/gif"

    def test_webp_extension(self):
        handler = ImageHandler()
        assert handler._get_mime_type(".webp") == "image/webp"

    def test_bmp_extension(self):
        handler = ImageHandler()
        assert handler._get_mime_type(".bmp") == "image/bmp"

    def test_unknown_extension_defaults_jpeg(self):
        handler = ImageHandler()
        assert handler._get_mime_type(".unknown") == "image/jpeg"


# ---------------------------------------------------------------------------
# ユーティリティテスト
# ---------------------------------------------------------------------------

class TestUtilities:
    """ユーティリティメソッドテスト"""

    def test_clear(self):
        data = _create_test_image()
        handler = ImageHandler()
        handler.load_from_bytes(data)
        assert handler.has_image() is True

        handler.clear()
        assert handler.has_image() is False
        assert handler.get_image() is None

    def test_get_image_returns_copy(self):
        data = _create_test_image(50, 50)
        handler = ImageHandler()
        handler.load_from_bytes(data)

        img1 = handler.get_image()
        img2 = handler.get_image()
        assert img1 is not img2  # コピーを返す

    def test_supported_extensions(self):
        exts = ImageHandler.get_supported_extensions()
        assert isinstance(exts, list)
        assert ".png" in exts
        assert ".jpg" in exts

    def test_file_filter(self):
        filt = ImageHandler.get_file_filter()
        assert "*.png" in filt
        assert "*.jpg" in filt
        assert "Images" in filt
