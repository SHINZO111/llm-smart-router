#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vision Request Builder - Vision APIリクエスト構築モジュール
ClaudeとGPT-4o向けのリクエストを構築
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass


@dataclass
class VisionContent:
    """Vision API用コンテンツ"""
    text: str
    image_base64: Optional[str] = None
    mime_type: str = "image/jpeg"


class VisionRequestBuilder:
    """Vision APIリクエストビルダー"""
    
    # 対応モデル
    VISION_MODELS = {
        'claude': {
            'primary': 'claude-3-5-sonnet-20241022',
            'fallback': 'claude-3-opus-20240229',
            'max_tokens': 4096
        },
        'gpt': {
            'primary': 'gpt-4o',
            'fallback': 'gpt-4o-mini',
            'max_tokens': 4096
        }
    }
    
    def __init__(self, provider: str = 'claude'):
        """
        Args:
            provider: 'claude' または 'gpt'
        """
        self.provider = provider.lower()
        if self.provider not in self.VISION_MODELS:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def build_request(
        self,
        content: VisionContent,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Vision APIリクエストを構築
        
        Args:
            content: テキストと画像を含むコンテンツ
            model: 使用するモデル（Noneでデフォルト）
            max_tokens: 最大トークン数
            temperature: 温度パラメータ
            system_prompt: システムプロンプト
            
        Returns:
            APIリクエスト用の辞書
        """
        if self.provider == 'claude':
            return self._build_claude_request(
                content, model, max_tokens, temperature, system_prompt
            )
        else:
            return self._build_gpt_request(
                content, model, max_tokens, temperature, system_prompt
            )
    
    def _build_claude_request(
        self,
        content: VisionContent,
        model: Optional[str],
        max_tokens: Optional[int],
        temperature: float,
        system_prompt: Optional[str]
    ) -> Dict[str, Any]:
        """Claude向けリクエスト構築"""
        config = self.VISION_MODELS['claude']
        
        request = {
            'model': model or config['primary'],
            'max_tokens': max_tokens or config['max_tokens'],
            'temperature': temperature,
            'messages': []
        }
        
        # メッセージコンテンツ構築
        message_content = []
        
        # 画像がある場合
        if content.image_base64:
            message_content.append({
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': content.mime_type,
                    'data': content.image_base64
                }
            })
        
        # テキスト追加
        message_content.append({
            'type': 'text',
            'text': content.text
        })
        
        request['messages'].append({
            'role': 'user',
            'content': message_content
        })
        
        # システムプロンプト
        if system_prompt:
            request['system'] = system_prompt
        
        return request
    
    def _build_gpt_request(
        self,
        content: VisionContent,
        model: Optional[str],
        max_tokens: Optional[int],
        temperature: float,
        system_prompt: Optional[str]
    ) -> Dict[str, Any]:
        """GPT-4o向けリクエスト構築"""
        config = self.VISION_MODELS['gpt']
        
        request = {
            'model': model or config['primary'],
            'max_tokens': max_tokens or config['max_tokens'],
            'temperature': temperature,
            'messages': []
        }
        
        # システムメッセージ
        if system_prompt:
            request['messages'].append({
                'role': 'system',
                'content': system_prompt
            })
        
        # ユーザーメッセージコンテンツ構築
        message_content = []
        
        # テキスト追加
        message_content.append({
            'type': 'text',
            'text': content.text
        })
        
        # 画像がある場合
        if content.image_base64:
            message_content.append({
                'type': 'image_url',
                'image_url': {
                    'url': f"data:{content.mime_type};base64,{content.image_base64}",
                    'detail': 'auto'
                }
            })
        
        request['messages'].append({
            'role': 'user',
            'content': message_content
        })
        
        return request
    
    @classmethod
    def select_model_for_image_task(
        cls,
        user_preference: Optional[str] = None,
        claude_available: bool = True,
        gpt_available: bool = True
    ) -> Dict[str, str]:
        """
        画像タスクに最適なモデルを選択
        
        Args:
            user_preference: ユーザー指定 ('claude' または 'gpt')
            claude_available: Claude APIが利用可能か
            gpt_available: GPT APIが利用可能か
            
        Returns:
            {'provider': str, 'model': str} の辞書
        """
        # 優先順位: Claude > GPT-4o
        if user_preference == 'claude' or (user_preference is None and claude_available):
            if claude_available:
                return {
                    'provider': 'claude',
                    'model': cls.VISION_MODELS['claude']['primary']
                }
        
        if user_preference == 'gpt' or gpt_available:
            if gpt_available:
                return {
                    'provider': 'gpt',
                    'model': cls.VISION_MODELS['gpt']['primary']
                }
        
        # フォールバック
        if claude_available:
            return {
                'provider': 'claude',
                'model': cls.VISION_MODELS['claude']['fallback']
            }
        
        return {
            'provider': 'gpt',
            'model': cls.VISION_MODELS['gpt']['fallback']
        }
    
    @staticmethod
    def estimate_image_tokens(width: int, height: int) -> int:
        """
        画像のトークン数を概算（GPT-4o Vision方式）
        
        Args:
            width: 画像幅
            height: 画像高さ
            
        Returns:
            概算トークン数
        """
        # 512pxタイルに分割
        tiles_x = (width + 511) // 512
        tiles_y = (height + 511) // 512
        total_tiles = tiles_x * tiles_y
        
        # ベース85トークン + タイルあたり170トークン
        return 85 + (total_tiles * 170)
    
    @staticmethod
    def get_vision_capabilities() -> Dict[str, Any]:
        """Vision対応モデルの機能情報"""
        return {
            'claude-3-5-sonnet-20241022': {
                'max_image_size': 5,  # MB
                'supported_formats': ['jpeg', 'png', 'gif', 'webp'],
                'max_dimension': 10920,
                'strengths': ['詳細な画像分析', 'テキスト認識', 'チャート解析']
            },
            'gpt-4o': {
                'max_image_size': 20,  # MB
                'supported_formats': ['jpeg', 'png', 'gif', 'webp'],
                'max_dimension': 2048,
                'strengths': ['汎用的な画像理解', '高速処理']
            }
        }
