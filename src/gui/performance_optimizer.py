#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Smart Router GUI v2.0 改善モジュール

【改善内容】
1. GUIパフォーマンス最適化 - 大規模テキスト・非同期処理
2. エラーメッセージ改善 - ユーザーフレンドリーな表示
3. キーボードショートカット追加 - 効率化
4. ログ記録機能 - デバッグ・監査用

使用方法:
    # main_window.py の該当箇所を置き換え
    from performance_optimizer import PerformanceOptimizer, ErrorHandler
    from keyboard_shortcuts import ShortcutManager

【作者】クラ for 新さん
【バージョン】2.0.1-improved
"""

import sys
import os
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Any
from functools import wraps
from contextlib import contextmanager

from PySide6.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QTextEdit, QPushButton,
    QHBoxLayout, QLabel, QApplication, QPlainTextEdit, QProgressDialog
)
from PySide6.QtCore import (
    Qt, QObject, Signal, Slot, QThread, QTimer,
    QRunnable, QThreadPool, QMetaObject, Q_ARG
)
from PySide6.QtGui import QKeySequence, QAction, QShortcut


# ============================================================
# 1. パフォーマンス最適化
# ============================================================

class PerformanceOptimizer:
    """
    GUIパフォーマンス最適化クラス
    
    - 大規模テキストの効率的な処理
    - 非同期操作の管理
    - メモリ使用量の最適化
    """
    
    # テキストサイズ閾値
    LARGE_TEXT_THRESHOLD = 10000  # 文字数
    CHUNK_SIZE = 1000  # チャンク処理サイズ
    
    def __init__(self, parent=None):
        self.parent = parent
        self.thread_pool = QThreadPool.globalInstance()
        self._operation_queue = []
        self._is_processing = False
        
    def optimize_text_edit(self, text_edit: QPlainTextEdit, text: str) -> bool:
        """
        テキストエディタへの大規模テキスト設定を最適化
        
        Args:
            text_edit: 対象のテキストエディタ
            text: 設定するテキスト
            
        Returns:
            最適化処理を実行したかどうか
        """
        if len(text) < self.LARGE_TEXT_THRESHOLD:
            # 小規模テキストは直接設定
            text_edit.setPlainText(text)
            return False
        
        # 大規模テキストはチャンク処理
        self._set_large_text_async(text_edit, text)
        return True
    
    def _set_large_text_async(self, text_edit: QPlainTextEdit, text: str):
        """大規模テキストを非同期で設定"""
        # プログレス表示
        progress = QProgressDialog("テキストを読み込み中...", "キャンセル", 0, 100, self.parent)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        
        # ワーカースレッドで処理
        worker = LargeTextWorker(text_edit, text, self.CHUNK_SIZE)
        worker.progress.connect(progress.setValue)
        worker.finished.connect(progress.close)
        worker.start()
    
    @staticmethod
    def debounce(delay_ms: int = 300):
        """
        デバounceデコレータ - 高頻度イベントを間引き
        
        Usage:
            @PerformanceOptimizer.debounce(500)
            def on_text_changed(self):
                pass
        """
        def decorator(func: Callable) -> Callable:
            timer = None
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                nonlocal timer
                
                def delayed_call():
                    func(*args, **kwargs)
                
                if timer:
                    timer.stop()
                    timer.deleteLater()
                
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(delayed_call)
                timer.start(delay_ms)
            
            return wrapper
        return decorator
    
    @staticmethod
    def throttle(interval_ms: int = 100):
        """
        スロットルデコレータ - イベント発生間隔を制限
        
        Usage:
            @PerformanceOptimizer.throttle(100)
            def on_resize(self):
                pass
        """
        def decorator(func: Callable) -> Callable:
            last_call = 0
            pending = False
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                nonlocal last_call, pending
                
                current = datetime.now().timestamp() * 1000
                
                if current - last_call >= interval_ms:
                    last_call = current
                    func(*args, **kwargs)
                elif not pending:
                    pending = True
                    def delayed():
                        nonlocal pending, last_call
                        pending = False
                        last_call = datetime.now().timestamp() * 1000
                        func(*args, **kwargs)
                    
                    QTimer.singleShot(interval_ms, delayed)
            
            return wrapper
        return decorator
    
    @contextmanager
    def batch_update(self, widget):
        """
        バッチ更新コンテキストマネージャ
        複数のUI更新を一括で処理し、再描画を抑制
        """
        widget.setUpdatesEnabled(False)
        try:
            yield
        finally:
            widget.setUpdatesEnabled(True)
            widget.update()
    
    def run_async(self, func: Callable, callback: Optional[Callable] = None, 
                  error_handler: Optional[Callable] = None):
        """
        関数を非同期で実行
        
        Args:
            func: 実行する関数
            callback: 成功時のコールバック (result) -> None
            error_handler: エラー時のコールバック (error) -> None
        """
        class Worker(QRunnable):
            def run(self):
                try:
                    result = func()
                    if callback:
                        QMetaObject.invokeMethod(
                            callback.__self__ if hasattr(callback, '__self__') else None,
                            callback.__name__,
                            Qt.QueuedConnection,
                            Q_ARG(object, result)
                        )
                except Exception as e:
                    if error_handler:
                        error_handler(e)
        
        self.thread_pool.start(Worker())


class LargeTextWorker(QThread):
    """大規模テキスト処理ワーカー"""
    
    progress = Signal(int)
    finished = Signal()
    chunk_ready = Signal(str)
    
    def __init__(self, text_edit: QPlainTextEdit, text: str, chunk_size: int = 1000):
        super().__init__()
        self.text_edit = text_edit
        self.text = text
        self.chunk_size = chunk_size
        
    def run(self):
        try:
            total_chunks = (len(self.text) + self.chunk_size - 1) // self.chunk_size
            
            # 既存のテキストをクリア
            QMetaObject.invokeMethod(
                self.text_edit, "clear",
                Qt.QueuedConnection
            )
            
            for i in range(total_chunks):
                if self.isInterruptionRequested():
                    break
                
                start = i * self.chunk_size
                end = min(start + self.chunk_size, len(self.text))
                chunk = self.text[start:end]
                
                # メインスレッドでテキスト追加
                QMetaObject.invokeMethod(
                    self.text_edit, "appendPlainText",
                    Qt.QueuedConnection,
                    Q_ARG(str, chunk)
                )
                
                progress = int((i + 1) / total_chunks * 100)
                self.progress.emit(progress)
                
                # UI更新のため短時間スリープ
                self.msleep(1)
            
            self.finished.emit()
            
        except Exception as e:
            print(f"LargeTextWorker error: {e}")
            self.finished.emit()


# ============================================================
# 2. エラーメッセージ改善
# ============================================================

class ErrorHandler:
    """
    ユーザーフレンドリーなエラーハンドリング
    
    - エラーの分類と翻訳
    - 詳細情報の表示/非表示
    - リカバリー提案
    """
    
    # エラーカテゴリ定義
    ERROR_CATEGORIES = {
        'CONNECTION': {
            'icon': '🔌',
            'title': '接続エラー',
            'color': '#ef4444',
            'suggestions': [
                'インターネット接続を確認してください',
                'ファイアウォール設定を確認してください',
                'VPN/プロキシ設定を確認してください'
            ]
        },
        'AUTH': {
            'icon': '🔐',
            'title': '認証エラー',
            'color': '#f59e0b',
            'suggestions': [
                'APIキーが正しく設定されているか確認してください',
                '設定 → APIキー でキーを再設定してください',
                'APIキーの有効期限を確認してください'
            ]
        },
        'TIMEOUT': {
            'icon': '⏱️',
            'title': 'タイムアウト',
            'color': '#f59e0b',
            'suggestions': [
                'ネットワーク環境が混雑していないか確認してください',
                'リクエストサイズを小さくしてみてください',
                '設定でタイムアウト時間を延長してください'
            ]
        },
        'MODEL': {
            'icon': '🤖',
            'title': 'モデルエラー',
            'color': '#6366f1',
            'suggestions': [
                'モデル選択を変更してみてください',
                'ローカルLLMが起動しているか確認してください',
                'モデルの互換性を確認してください'
            ]
        },
        'RESOURCE': {
            'icon': '💾',
            'title': 'リソース不足',
            'color': '#ef4444',
            'suggestions': [
                '不要なアプリケーションを終了してください',
                'ディスク容量を確認してください',
                'システムを再起動してください'
            ]
        },
        'UNKNOWN': {
            'icon': '❓',
            'title': '予期しないエラー',
            'color': '#6b7280',
            'suggestions': [
                'アプリケーションを再起動してください',
                'ログを確認してください',
                'サポートにお問い合わせください'
            ]
        }
    }
    
    # エラーパターンとカテゴリのマッピング
    ERROR_PATTERNS = {
        'CONNECTION': [
            'connection', 'network', 'socket', 'timeout', 'refused',
            ' unreachable', 'dns', 'proxy', 'ssl', 'certificate'
        ],
        'AUTH': [
            'authentication', 'unauthorized', 'forbidden', 'api key',
            'invalid token', 'credential', 'permission', 'access denied'
        ],
        'TIMEOUT': [
            'timeout', 'timed out', 'deadline exceeded'
        ],
        'MODEL': [
            'model not found', 'model unavailable', 'lm studio',
            'ollama', 'local llm', 'context length'
        ],
        'RESOURCE': [
            'memory', 'disk', 'space', 'quota exceeded', 'rate limit'
        ]
    }
    
    def __init__(self, parent=None):
        self.parent = parent
        self.error_log = []
        
    def handle_error(self, error: Exception, context: str = "") -> str:
        """
        エラーを処理し、ユーザーフレンドリーなメッセージを返す
        
        Args:
            error: 発生した例外
            context: エラー発生時のコンテキスト
            
        Returns:
            ユーザーフレンドリーなエラーメッセージ
        """
        error_msg = str(error)
        error_type = type(error).__name__
        
        # カテゴリ判定
        category = self._categorize_error(error_msg, error_type)
        
        # エラー情報をログ
        error_info = {
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': error_msg,
            'context': context,
            'category': category,
            'traceback': traceback.format_exc()
        }
        self.error_log.append(error_info)
        
        # ダイアログ表示
        self._show_error_dialog(error_info, category)
        
        return self._format_user_message(error_info, category)
    
    def _categorize_error(self, error_msg: str, error_type: str) -> str:
        """エラーをカテゴリ分類"""
        msg_lower = error_msg.lower()
        type_lower = error_type.lower()
        
        for category, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern in msg_lower or pattern in type_lower:
                    return category
        
        return 'UNKNOWN'
    
    def _show_error_dialog(self, error_info: dict, category: str):
        """エラーダイアログを表示"""
        cat_info = self.ERROR_CATEGORIES.get(category, self.ERROR_CATEGORIES['UNKNOWN'])
        
        dialog = ErrorDialog(error_info, cat_info, self.parent)
        dialog.exec()
    
    def _format_user_message(self, error_info: dict, category: str) -> str:
        """ユーザー向けメッセージをフォーマット"""
        cat_info = self.ERROR_CATEGORIES.get(category, self.ERROR_CATEGORIES['UNKNOWN'])
        
        lines = [
            f"{cat_info['icon']} {cat_info['title']}",
            "",
            f"詳細: {error_info['message']}",
            "",
            "【対処方法】"
        ]
        
        for suggestion in cat_info['suggestions']:
            lines.append(f"  • {suggestion}")
        
        return "\n".join(lines)
    
    def get_error_log(self) -> list:
        """エラーログを取得"""
        return self.error_log.copy()
    
    def clear_error_log(self):
        """エラーログをクリア"""
        self.error_log.clear()


class ErrorDialog(QDialog):
    """改良版エラーダイアログ"""
    
    def __init__(self, error_info: dict, category_info: dict, parent=None):
        super().__init__(parent)
        self.error_info = error_info
        self.category_info = category_info
        
        self.setWindowTitle(f"{category_info['icon']} {category_info['title']}")
        self.setMinimumSize(500, 400)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # ヘッダー
        header = QLabel(f"{self.category_info['icon']} {self.category_info['title']}")
        header.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {self.category_info['color']};
            padding: 10px;
        """)
        layout.addWidget(header)
        
        # エラーメッセージ
        msg_label = QLabel(f"<b>エラー内容:</b><br>{self.error_info['message']}")
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("padding: 10px; background-color: #2d2d2d; border-radius: 6px;")
        layout.addWidget(msg_label)
        
        # 対処方法
        suggestions_group = QLabel("<b>【対処方法】</b>")
        layout.addWidget(suggestions_group)
        
        for suggestion in self.category_info['suggestions']:
            suggestion_label = QLabel(f"  • {suggestion}")
            suggestion_label.setStyleSheet("color: #10b981; padding: 4px;")
            layout.addWidget(suggestion_label)
        
        # 詳細情報（折りたたみ可能）
        details_btn = QPushButton("🔍 技術的詳細を表示")
        details_btn.setCheckable(True)
        details_btn.toggled.connect(self.toggle_details)
        layout.addWidget(details_btn)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlainText(self.error_info['traceback'])
        self.details_text.setVisible(False)
        self.details_text.setMaximumHeight(150)
        layout.addWidget(self.details_text)
        
        # ボタン
        buttons = QHBoxLayout()
        
        copy_btn = QPushButton("📋 エラーをコピー")
        copy_btn.clicked.connect(self.copy_error)
        buttons.addWidget(copy_btn)
        
        buttons.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        buttons.addWidget(ok_btn)
        
        layout.addLayout(buttons)
    
    def toggle_details(self, checked: bool):
        """詳細表示の切り替え"""
        self.details_text.setVisible(checked)
        self.adjustSize()
    
    def copy_error(self):
        """エラー情報をクリップボードにコピー"""
        clipboard = QApplication.clipboard()
        error_text = f"""
エラー情報
==========
時刻: {self.error_info['timestamp']}
タイプ: {self.error_info['type']}
カテゴリ: {self.error_info['category']}
コンテキスト: {self.error_info['context']}
メッセージ: {self.error_info['message']}

スタックトレース:
{self.error_info['traceback']}
"""
        clipboard.setText(error_text)
        QMessageBox.information(self, "コピー完了", "エラー情報をクリップボードにコピーしました")


# ============================================================
# 3. キーボードショートカット
# ============================================================

class ShortcutManager:
    """
    キーボードショートカット管理クラス
    
    追加ショートカット:
    - Ctrl+Enter: 実行
    - Ctrl+Shift+Enter: 停止
    - Ctrl+N: 新規
    - Ctrl+O: ファイルを開く
    - Ctrl+S: 結果を保存
    - Ctrl+L: 入力クリア
    - Ctrl+Shift+C: 出力コピー
    - Ctrl+M: モデル切替
    - Ctrl+P: プリセット選択
    - Ctrl+T: 設定
    - Ctrl+D: ダッシュボード
    - Ctrl+H: ヘルプ
    - Ctrl+Q: 終了
    - F1: クイックヘルプ
    - Esc: 停止/キャンセル
    - Ctrl+Plus: フォント拡大
    - Ctrl+Minus: フォント縮小
    - Ctrl+0: フォントリセット
    """
    
    SHORTCUTS = {
        'execute': {'key': 'Ctrl+Return', 'desc': '実行'},
        'stop': {'key': 'Ctrl+Shift+Return', 'desc': '停止'},
        'new': {'key': 'Ctrl+N', 'desc': '新規'},
        'open': {'key': 'Ctrl+O', 'desc': 'ファイルを開く'},
        'save': {'key': 'Ctrl+S', 'desc': '結果を保存'},
        'clear_input': {'key': 'Ctrl+L', 'desc': '入力クリア'},
        'copy_output': {'key': 'Ctrl+Shift+C', 'desc': '出力コピー'},
        'toggle_model': {'key': 'Ctrl+M', 'desc': 'モデル切替'},
        'preset': {'key': 'Ctrl+P', 'desc': 'プリセット選択'},
        'settings': {'key': 'Ctrl+T', 'desc': '設定'},
        'dashboard': {'key': 'Ctrl+D', 'desc': 'ダッシュボード'},
        'help': {'key': 'Ctrl+H', 'desc': 'ヘルプ'},
        'quit': {'key': 'Ctrl+Q', 'desc': '終了'},
        'quick_help': {'key': 'F1', 'desc': 'クイックヘルプ'},
        'cancel': {'key': 'Escape', 'desc': 'キャンセル'},
        'font_up': {'key': 'Ctrl+Plus', 'desc': 'フォント拡大'},
        'font_down': {'key': 'Ctrl+Minus', 'desc': 'フォント縮小'},
        'font_reset': {'key': 'Ctrl+0', 'desc': 'フォントリセット'},
    }
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.actions = {}
        self._font_size = 12
        
    def register_all(self):
        """すべてのショートカットを登録"""
        # 実行・停止
        self._register('execute', self.main_window.execute)
        self._register('stop', self.main_window.stop_execution)
        
        # ファイル操作
        self._register('open', self.main_window.load_file)
        self._register('save', self.main_window.save_output)
        
        # 編集
        self._register('clear_input', self.main_window.clear_input)
        self._register('copy_output', self.main_window.copy_output)
        
        # モデル・プリセット
        self._register('toggle_model', self._cycle_model)
        self._register('preset', self._show_preset_menu)
        
        # 設定・ダッシュボード
        self._register('settings', self.main_window.open_settings)
        self._register('dashboard', self.main_window.show_full_stats)
        
        # ヘルプ
        self._register('help', self.main_window.show_about)
        self._register('quick_help', self._show_quick_help)
        
        # 終了
        self._register('quit', self.main_window.close)
        
        # フォントサイズ
        self._register('font_up', self._increase_font)
        self._register('font_down', self._decrease_font)
        self._register('font_reset', self._reset_font)
    
    def _register(self, name: str, handler: Callable):
        """ショートカットを登録"""
        shortcut_info = self.SHORTCUTS.get(name)
        if not shortcut_info:
            return
        
        shortcut = QShortcut(
            QKeySequence(shortcut_info['key']),
            self.main_window
        )
        shortcut.activated.connect(handler)
        self.actions[name] = shortcut
    
    def get_shortcut_text(self, name: str) -> str:
        """ショートカットのテキスト表現を取得"""
        info = self.SHORTCUTS.get(name, {})
        return f"{info.get('desc', '')} ({info.get('key', '')})"
    
    def get_all_shortcuts(self) -> dict:
        """すべてのショートカットを取得"""
        return self.SHORTCUTS.copy()
    
    # --- ハンドラー ---
    
    def _cycle_model(self):
        """モデルを順番に切り替え"""
        combo = self.main_window.model_combo
        current = combo.currentIndex()
        next_index = (current + 1) % combo.count()
        combo.setCurrentIndex(next_index)
    
    def _show_preset_menu(self):
        """プリセットメニューを表示"""
        self.main_window.preset_combo.showPopup()
    
    def _show_quick_help(self):
        """クイックヘルプを表示"""
        dialog = QuickHelpDialog(self.main_window)
        dialog.exec()
    
    def _increase_font(self):
        """フォントサイズを拡大"""
        self._font_size = min(self._font_size + 1, 24)
        self._apply_font_size()
    
    def _decrease_font(self):
        """フォントサイズを縮小"""
        self._font_size = max(self._font_size - 1, 8)
        self._apply_font_size()
    
    def _reset_font(self):
        """フォントサイズをリセット"""
        self._font_size = 12
        self._apply_font_size()
    
    def _apply_font_size(self):
        """フォントサイズを適用"""
        from PySide6.QtGui import QFont
        
        font = QFont("Segoe UI", self._font_size)
        self.main_window.input_text.setFont(font)
        self.main_window.output_text.setFont(font)
        self.main_window.system_prompt.setFont(font)
        
        self.main_window.status_bar.showMessage(
            f"フォントサイズ: {self._font_size}pt", 2000
        )


class QuickHelpDialog(QDialog):
    """クイックヘルプダイアログ"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⌨️ キーボードショートカット")
        self.setMinimumSize(450, 500)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # タイトル
        title = QLabel("⌨️ キーボードショートカット一覧")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #6366f1;")
        layout.addWidget(title)
        
        # ショートカット一覧
        shortcuts = ShortcutManager.SHORTCUTS
        
        categories = [
            ('実行・停止', ['execute', 'stop', 'cancel']),
            ('ファイル操作', ['new', 'open', 'save']),
            ('編集', ['clear_input', 'copy_output']),
            ('モデル・プリセット', ['toggle_model', 'preset']),
            ('設定・表示', ['settings', 'dashboard', 'font_up', 'font_down', 'font_reset']),
            ('ヘルプ・終了', ['help', 'quick_help', 'quit']),
        ]
        
        for cat_name, keys in categories:
            group = QLabel(f"<b>{cat_name}</b>")
            group.setStyleSheet("color: #10b981; margin-top: 10px;")
            layout.addWidget(group)
            
            for key in keys:
                if key in shortcuts:
                    info = shortcuts[key]
                    line = QLabel(f"  <code>{info['key']}</code> - {info['desc']}")
                    line.setStyleSheet("padding: 2px 10px;")
                    layout.addWidget(line)
        
        layout.addStretch()
        
        # 閉じるボタン
        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# ============================================================
# 4. ログ記録機能
# ============================================================

class ApplicationLogger:
    """
    アプリケーション全体のログ管理
    
    - ファイルログ
    - メモリログ（UI表示用）
    - ログレベル制御
    """
    
    def __init__(self, log_dir: str = None):
        self.log_dir = Path(log_dir or Path.home() / '.llm-smart-router' / 'logs')
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # ログファイル設定
        log_file = self.log_dir / f"app_{datetime.now():%Y%m%d}.log"
        
        self.logger = logging.getLogger('LLMSmartRouter')
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(file_handler)
            self.logger.addHandler(stream_handler)
        self.memory_logs = []
        self.max_memory_logs = 1000
        
    def log(self, level: str, message: str, **kwargs):
        """ログを記録"""
        # ファイルログ
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        if kwargs:
            extra_str = ', '.join(f'{k}={v}' for k, v in kwargs.items())
            log_func(f"{message} [{extra_str}]")
        else:
            log_func(message)
        
        # メモリログ
        entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'extra': kwargs
        }
        self.memory_logs.append(entry)
        
        # メモリログ制限
        if len(self.memory_logs) > self.max_memory_logs:
            self.memory_logs.pop(0)
    
    def debug(self, message: str, **kwargs):
        self.log('DEBUG', message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self.log('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.log('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.log('ERROR', message, **kwargs)
    
    def get_memory_logs(self, level: str = None, limit: int = 100) -> list:
        """メモリログを取得"""
        logs = self.memory_logs
        if level:
            logs = [l for l in logs if l['level'] == level.upper()]
        return logs[-limit:]
    
    def export_logs(self, path: str = None) -> str:
        """ログをエクスポート"""
        if path is None:
            path = self.log_dir / f"export_{datetime.now():%Y%m%d_%H%M%S}.json"
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.memory_logs, f, ensure_ascii=False, indent=2)
        
        return str(path)


# ============================================================
# 使用例
# ============================================================

def example_usage():
    """改善モジュールの使用例"""
    
    # 1. パフォーマンス最適化
    optimizer = PerformanceOptimizer()
    
    # デバounce使用例
    @PerformanceOptimizer.debounce(500)
    def on_search_text_changed():
        print("検索実行（500ms遅延）")
    
    # バッチ更新
    # with optimizer.batch_update(text_widget):
    #     text_widget.appendPlainText(chunk1)
    #     text_widget.appendPlainText(chunk2)
    #     text_widget.appendPlainText(chunk3)
    
    # 2. エラーハンドリング
    error_handler = ErrorHandler()
    
    try:
        # 何かしらの処理
        raise ConnectionError("Failed to connect to API")
    except Exception as e:
        error_handler.handle_error(e, context="API呼び出し中")
    
    # 3. ショートカット
    # shortcut_manager = ShortcutManager(main_window)
    # shortcut_manager.register_all()
    
    # 4. ログ
    logger = ApplicationLogger()
    logger.info("アプリケーション起動")
    logger.error("エラー発生", error_code=500)


if __name__ == '__main__':
    example_usage()
