#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image Handler - 画像処理モジュール
画像のリサイズ、Base64エンコード、クリップボード対応
"""

import io
import base64
from pathlib import Path
from typing import Optional, Tuple, Union
from PIL import Image, ImageOps


class ImageHandler:
    """画像処理ハンドラ"""
    
    # 制約
    MAX_FILE_SIZE_MB = 5
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    
    # Vision API用推奨サイズ
    MAX_DIMENSION = 2048
    TARGET_DIMENSION = 1024
    
    # サポートするフォーマット
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    
    def __init__(self):
        self._current_image: Optional[Image.Image] = None
        self._original_path: Optional[Path] = None
        self._mime_type: str = "image/jpeg"
    
    def load_from_file(self, file_path: Union[str, Path]) -> Tuple[bool, str]:
        """
        ファイルから画像を読み込む
        
        Returns:
            (success, message): 成功フラグとメッセージ
        """
        path = Path(file_path)
        
        # 拡張子チェック
        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            return False, f"Unsupported format: {path.suffix}. Use: {self.SUPPORTED_FORMATS}"
        
        # ファイルサイズチェック
        file_size = path.stat().st_size
        if file_size > self.MAX_FILE_SIZE_BYTES:
            return False, f"File too large: {file_size / 1024 / 1024:.1f}MB > {self.MAX_FILE_SIZE_MB}MB limit"
        
        try:
            self._current_image = Image.open(path)
            self._original_path = path
            self._mime_type = self._get_mime_type(path.suffix)
            
            # EXIF Orientation対応
            self._current_image = ImageOps.exif_transpose(self._current_image)
            
            # RGBAをRGBに変換（JPEG保存のため）
            if self._current_image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', self._current_image.size, (255, 255, 255))
                if self._current_image.mode == 'P':
                    self._current_image = self._current_image.convert('RGBA')
                if self._current_image.mode in ('RGBA', 'LA'):
                    background.paste(self._current_image, mask=self._current_image.split()[-1] if self._current_image.mode in ('RGBA', 'LA') else None)
                    self._current_image = background
            
            return True, f"Loaded: {self._current_image.size[0]}x{self._current_image.size[1]}"
            
        except Exception as e:
            return False, f"Load error: {str(e)}"
    
    def load_from_bytes(self, data: bytes, mime_type: str = "image/png") -> Tuple[bool, str]:
        """
        バイトデータから画像を読み込む（クリップボード用）
        
        Returns:
            (success, message): 成功フラグとメッセージ
        """
        if len(data) > self.MAX_FILE_SIZE_BYTES:
            return False, f"Data too large: {len(data) / 1024 / 1024:.1f}MB > {self.MAX_FILE_SIZE_MB}MB limit"
        
        try:
            self._current_image = Image.open(io.BytesIO(data))
            self._original_path = None
            self._mime_type = mime_type
            
            # EXIF Orientation対応
            self._current_image = ImageOps.exif_transpose(self._current_image)
            
            # RGBAをRGBに変換
            if self._current_image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', self._current_image.size, (255, 255, 255))
                if self._current_image.mode == 'P':
                    self._current_image = self._current_image.convert('RGBA')
                if self._current_image.mode in ('RGBA', 'LA'):
                    background.paste(self._current_image, mask=self._current_image.split()[-1])
                    self._current_image = background
            
            return True, f"Loaded: {self._current_image.size[0]}x{self._current_image.size[1]}"
            
        except Exception as e:
            return False, f"Load error: {str(e)}"
    
    def resize_if_needed(self, max_dimension: int = TARGET_DIMENSION) -> Image.Image:
        """
        画像が大きすぎる場合にリサイズ
        
        Args:
            max_dimension: 最大辺の長さ
            
        Returns:
            リサイズされた画像（または元の画像）
        """
        if self._current_image is None:
            raise ValueError("No image loaded")
        
        width, height = self._current_image.size
        max_side = max(width, height)
        
        if max_side <= max_dimension:
            return self._current_image.copy()
        
        # アスペクト比を保持してリサイズ
        ratio = max_dimension / max_side
        new_size = (int(width * ratio), int(height * ratio))
        
        return self._current_image.resize(new_size, Image.Resampling.LANCZOS)
    
    def to_base64(self, quality: int = 85, max_dimension: int = TARGET_DIMENSION) -> Tuple[str, str]:
        """
        画像をBase64エンコード
        
        Args:
            quality: JPEG品質 (1-100)
            max_dimension: 最大辺の長さ
            
        Returns:
            (base64_string, mime_type): Base64文字列とMIMEタイプ
        """
        if self._current_image is None:
            raise ValueError("No image loaded")
        
        # リサイズ
        img = self.resize_if_needed(max_dimension)
        
        # JPEGにエンコード
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        buffer.seek(0)
        
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return encoded, "image/jpeg"
    
    def to_bytes(self, quality: int = 85, max_dimension: int = TARGET_DIMENSION) -> bytes:
        """
        画像をバイト列として取得
        
        Args:
            quality: JPEG品質
            max_dimension: 最大辺の長さ
            
        Returns:
            JPEGバイト列
        """
        if self._current_image is None:
            raise ValueError("No image loaded")
        
        img = self.resize_if_needed(max_dimension)
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def get_preview_size(self, max_width: int = 400, max_height: int = 300) -> Tuple[int, int]:
        """
        プレビュー用のサイズを計算
        
        Returns:
            (width, height): アスペクト比を保持したサイズ
        """
        if self._current_image is None:
            return (0, 0)
        
        width, height = self._current_image.size
        ratio = min(max_width / width, max_height / height, 1.0)
        
        return (int(width * ratio), int(height * ratio))
    
    def get_image(self) -> Optional[Image.Image]:
        """現在の画像を取得"""
        return self._current_image.copy() if self._current_image else None
    
    def get_dimensions(self) -> Tuple[int, int]:
        """画像サイズを取得"""
        if self._current_image is None:
            return (0, 0)
        return self._current_image.size
    
    def get_file_size_kb(self) -> Optional[float]:
        """元ファイルのサイズをKBで取得"""
        if self._original_path is None:
            return None
        return self._original_path.stat().st_size / 1024
    
    def clear(self):
        """画像をクリア"""
        self._current_image = None
        self._original_path = None
        self._mime_type = "image/jpeg"
    
    def has_image(self) -> bool:
        """画像が読み込まれているか"""
        return self._current_image is not None
    
    def _get_mime_type(self, ext: str) -> str:
        """拡張子からMIMEタイプを取得"""
        mapping = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        return mapping.get(ext.lower(), 'image/jpeg')
    
    @staticmethod
    def get_supported_extensions() -> list:
        """サポートされている拡張子のリストを取得"""
        return list(ImageHandler.SUPPORTED_FORMATS)
    
    @staticmethod
    def get_file_filter() -> str:
        """QFileDialog用のフィルタ文字列を取得"""
        return "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp);;All Files (*.*)"
