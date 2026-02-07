#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Smart Router Pro - Premium GUI

作者: クラ for 新さん
バージョン: 3.0.0
"""

import sys
import os
import json
import subprocess
import base64
import yaml
import uuid
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QComboBox, QLabel, QLineEdit,
    QGroupBox, QSplitter, QStatusBar, QMenuBar, QMenu,
    QMessageBox, QFileDialog, QProgressBar, QTabWidget,
    QFrame, QScrollArea, QGridLayout, QSpinBox, QDoubleSpinBox,
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QPlainTextEdit, QGraphicsDropShadowEffect,
    QSizePolicy, QGraphicsOpacityEffect, QLabel, QStackedWidget
)
from PySide6.QtCore import (
    Qt, QThread, Signal, Slot, QTimer, QSize, QSettings,
    QPropertyAnimation, QEasingCurve, Property, QRect,
    QParallelAnimationGroup, QSequentialAnimationGroup, QAbstractAnimation,
    QBuffer
)
from PySide6.QtGui import (
    QAction, QIcon, QFont, QPalette, QColor, QKeySequence,
    QShortcut, QFontDatabase, QPainter, QLinearGradient,
    QBrush, QPen, QRadialGradient, QPainterPath, QPixmap, QImage
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from security.key_manager import SecureKeyManager
from gui.dashboard import StatisticsDashboard
from gui.settings_dialog import SettingsDialog
from gui.conversation_sidebar import ConversationSidebar, ConversationItem
from gui.conversation_tabs import ConversationTabWidget
from multimodal.image_handler import ImageHandler
from multimodal.vision_request import VisionRequestBuilder, VisionContent
from PIL.ImageQt import ImageQt


# ============================================================
# Premium Color Palette
# ============================================================

class Colors:
    BG_DARK = '#0a0a0f'
    BG_MAIN = '#10101a'
    BG_CARD = '#161625'
    BG_CARD_HOVER = '#1c1c30'
    BG_INPUT = '#12121f'
    BORDER = '#252540'
    BORDER_FOCUS = '#6366f1'

    PRIMARY = '#6366f1'
    PRIMARY_LIGHT = '#818cf8'
    PRIMARY_GLOW = '#6366f140'
    SECONDARY = '#10b981'
    SECONDARY_LIGHT = '#34d399'
    ACCENT = '#f59e0b'
    DANGER = '#ef4444'
    CYAN = '#06b6d4'

    TEXT = '#eef2ff'
    TEXT_PRIMARY = '#eef2ff'
    TEXT_DIM = '#94a3b8'
    TEXT_MUTED = '#64748b'

    BG_TERTIARY = '#1e1e35'
    BG_HOVER = '#252545'

    WARNING = '#f59e0b'
    ERROR = '#ef4444'

    GRADIENT_START = '#6366f1'
    GRADIENT_END = '#8b5cf6'


# ============================================================
# Animated Glow Widget
# ============================================================

class GlowCard(QFrame):
    def __init__(self, accent_color=Colors.PRIMARY, parent=None):
        super().__init__(parent)
        self.accent_color = accent_color
        self._glow_opacity = 0.0
        self.setStyleSheet(f"""
            GlowCard {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
                padding: 16px;
            }}
            GlowCard:hover {{
                background-color: {Colors.BG_CARD_HOVER};
                border-color: {accent_color}40;
            }}
        """)

    def set_glow(self, val):
        self._glow_opacity = val
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._glow_opacity > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setOpacity(self._glow_opacity * 0.15)
            grad = QRadialGradient(self.width() / 2, 0, self.width())
            grad.setColorAt(0, QColor(self.accent_color))
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(self.rect(), grad)
            p.end()


# ============================================================
# Stat Card Widget
# ============================================================

class StatCard(QFrame):
    def __init__(self, icon, title, value, color, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedHeight(90)
        self.setStyleSheet(f"""
            StatCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.BG_CARD}, stop:1 {color}10);
                border: 1px solid {Colors.BORDER};
                border-left: 3px solid {color};
                border-radius: 10px;
                padding: 12px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        header = QLabel(f"{icon} {title}")
        header.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 11px; border: none;")
        layout.addWidget(header)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: bold; border: none;"
        )
        layout.addWidget(self.value_label)

    def set_value(self, v):
        self.value_label.setText(str(v))


# ============================================================
# Animated Execute Button
# ============================================================

class PulseButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._pulse = 0.0
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._step)
        self._direction = 1
        self._animating = False

    def start_pulse(self):
        self._animating = True
        self._anim.start(40)

    def stop_pulse(self):
        self._animating = False
        self._anim.stop()
        self._pulse = 0.0
        self.update()

    def _step(self):
        self._pulse += 0.05 * self._direction
        if self._pulse >= 1.0:
            self._direction = -1
        elif self._pulse <= 0.0:
            self._direction = 1
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._animating and self._pulse > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setOpacity(self._pulse * 0.3)
            grad = QRadialGradient(self.width() / 2, self.height() / 2,
                                   max(self.width(), self.height()))
            grad.setColorAt(0, QColor(Colors.PRIMARY_LIGHT))
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            path = QPainterPath()
            path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)
            p.fillPath(path, grad)
            p.end()


# ============================================================
# Model Indicator Dot
# ============================================================

class StatusDot(QWidget):
    def __init__(self, color=Colors.SECONDARY, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(10, 10)

    def set_color(self, c):
        self.color = c
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.color))
        p.drawEllipse(1, 1, 8, 8)
        p.setOpacity(0.4)
        p.drawEllipse(0, 0, 10, 10)
        p.end()


# ============================================================
# Model Badge Widget
# ============================================================

class ModelBadge(QFrame):
    """使用中のモデルを目立つバッジで表示"""

    # モデル種別ごとの設定
    _STYLES = {
        'auto':  {'icon': '🤖', 'label': 'Auto',  'color': Colors.SECONDARY,     'bg': '#10b98118'},
        'local': {'icon': '💻', 'label': 'Local', 'color': Colors.ACCENT,        'bg': '#f59e0b18'},
        'cloud': {'icon': '☁️', 'label': 'Cloud', 'color': Colors.CYAN,          'bg': '#06b6d418'},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model_key = 'auto'
        self._model_detail = ''

        self.setMinimumHeight(48)
        self.setMaximumHeight(64)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(10)

        # アイコン
        self._icon = QLabel('🤖')
        self._icon.setStyleSheet('font-size: 22px; border: none; background: transparent;')
        self._icon.setFixedWidth(30)
        lay.addWidget(self._icon)

        # ラベル列
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        text_col.setContentsMargins(0, 0, 0, 0)

        self._type_label = QLabel('Auto')
        self._type_label.setStyleSheet(
            f'font-size: 15px; font-weight: 700; color: {Colors.SECONDARY};'
            ' border: none; background: transparent;'
        )
        text_col.addWidget(self._type_label)

        self._detail_label = QLabel('')
        self._detail_label.setStyleSheet(
            f'font-size: 11px; color: {Colors.TEXT_DIM};'
            ' border: none; background: transparent;'
        )
        text_col.addWidget(self._detail_label)

        lay.addLayout(text_col, 1)

        # ステータスドット
        self._dot = StatusDot(Colors.SECONDARY)
        lay.addWidget(self._dot)

        self._apply_style()

    def _resolve_key(self, model_data: str) -> str:
        if not model_data:
            return 'auto'
        if model_data == 'auto':
            return 'auto'
        if model_data.startswith('local:') or model_data == 'local':
            return 'local'
        return 'cloud'

    def set_model(self, model_data: str, detail: str = ''):
        """モデルを設定して表示を更新"""
        key = self._resolve_key(model_data)
        self._model_key = key
        self._model_detail = detail

        style = self._STYLES.get(key, self._STYLES['auto'])
        self._icon.setText(style['icon'])
        self._type_label.setText(style['label'])
        self._type_label.setStyleSheet(
            f'font-size: 15px; font-weight: 700; color: {style["color"]};'
            ' border: none; background: transparent;'
        )
        self._detail_label.setText(detail)
        self._dot.set_color(style['color'])
        self._apply_style()

    def set_detail(self, text: str):
        self._detail_label.setText(text)

    def set_processing(self, processing: bool):
        """処理中の見た目に切り替え"""
        if processing:
            self._detail_label.setText('Processing...')
            self._detail_label.setStyleSheet(
                f'font-size: 11px; color: {Colors.PRIMARY_LIGHT};'
                ' border: none; background: transparent;'
            )
        else:
            self._detail_label.setStyleSheet(
                f'font-size: 11px; color: {Colors.TEXT_DIM};'
                ' border: none; background: transparent;'
            )

    def _apply_style(self):
        style = self._STYLES.get(self._model_key, self._STYLES['auto'])
        self.setStyleSheet(f"""
            ModelBadge {{
                background-color: {style['bg']};
                border: 1px solid {style['color']}40;
                border-left: 4px solid {style['color']};
                border-radius: 10px;
            }}
        """)


# ============================================================
# LLM Worker Thread
# ============================================================

class LLMWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, router_path, input_text, model_type=None, config=None, api_key=None):
        super().__init__()
        self.router_path = router_path
        self.input_text = input_text
        self.model_type = model_type
        self.config = config or {}
        self._api_key = api_key
        self._cancelled = False
        self._process = None

    def cancel(self):
        self._cancelled = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def run(self):
        image_path = None
        try:
            self.progress.emit("Preparing request...")

            # 画像データがある場合は一時ファイルに保存
            if self.config.get('image_base64'):
                import tempfile
                image_data = base64.b64decode(self.config['image_base64'])
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as f:
                    f.write(image_data)
                    image_path = f.name

            cmd = ['node', os.path.join(self.router_path, 'router.js')]

            # モデル指定
            if self.model_type:
                cmd.extend(['--model', self.model_type])

            # 画像パスがあれば追加
            if image_path:
                cmd.extend(['--image', image_path])

            # 入力テキスト
            cmd.append(self.input_text)

            env = os.environ.copy()
            if self._api_key:
                env['ANTHROPIC_API_KEY'] = self._api_key

            if self._cancelled:
                return

            self.progress.emit("Querying LLM...")

            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', env=env
            )

            start = datetime.now()
            timeout = self.config.get('timeout', 120)
            lines = []

            while True:
                if self._cancelled:
                    self._process.terminate()
                    return
                elapsed = (datetime.now() - start).total_seconds()
                if elapsed > timeout:
                    self._process.terminate()
                    self.error.emit(f"Timeout after {timeout}s")
                    return
                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    break
                if line:
                    lines.append(line)
                self.msleep(10)

            rc = self._process.poll()
            stderr = self._process.stderr.read()

            if rc == 0:
                self.finished.emit({
                    'success': True,
                    'response': ''.join(lines),
                    'model': self.model_type or 'auto',
                    'duration': elapsed
                })
            else:
                self.error.emit(stderr or "Unknown error")

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if image_path:
                try:
                    os.unlink(image_path)
                except OSError:
                    pass


# ============================================================
# Preset Manager
# ============================================================

class PresetManager:
    PRESETS = {
        'cm_work': {
            'name': 'CM業務', 'description': '建設業のコスト管理・見積・工事関連',
            'system_prompt': 'あなたは建設業のプロフェッショナルアシスタントです。\n建設コスト・工事進捗・品質管理・法令対応・安全衛生の観点で回答してください。',
            'icon': '🏗️', 'default_model': 'cloud',
            'keywords': ['コスト', '見積', '工事', '施主', '建設']
        },
        'oshi_support': {
            'name': '推し活', 'description': 'KONO・mina・りぃなど推しのサポート',
            'system_prompt': 'あなたは熱心なファンをサポートするアシスタントです。\n配信スケジュール・応援コメント・SNSマーケティング・コミュニティ運営の観点で回答してください。',
            'icon': '💎', 'default_model': 'cloud',
            'keywords': ['配信', 'ライブ', '推し', 'ファン', '応援']
        },
        'coding': {
            'name': 'コーディング', 'description': 'コード生成・レビュー・デバッグ',
            'system_prompt': 'あなたはエキスパートプログラマーです。\nクリーンコード・セキュリティ・パフォーマンス・可読性の観点で回答してください。',
            'icon': '💻', 'default_model': 'auto',
            'keywords': ['コード', 'バグ', 'エラー', '関数', 'API']
        },
        'writing': {
            'name': '文章作成', 'description': 'ビジネス文書・SNS投稿・ブログ',
            'system_prompt': 'あなたはプロのライターです。\n明確な表現・適切なトーン・論理的構成・具体的事例で文章を作成してください。',
            'icon': '✍️', 'default_model': 'local',
            'keywords': ['文章', '作成', 'ブログ', 'SNS', '投稿']
        },
        'analysis': {
            'name': 'データ分析', 'description': 'データの分析・可視化・レポート',
            'system_prompt': 'あなたはデータアナリストです。\n統計的洞察・可視化提案・トレンド分析・ビジネス示唆の観点で分析してください。',
            'icon': '📊', 'default_model': 'cloud',
            'keywords': ['データ', '分析', 'グラフ', '統計', 'レポート']
        },
        'learning': {
            'name': '学習支援', 'description': '新しい知識の習得・解説・要約',
            'system_prompt': 'あなたは親しみやすい教師です。\n段階的説明・具体例・類似概念比較・実践演習で教えてください。',
            'icon': '📚', 'default_model': 'local',
            'keywords': ['学習', '教えて', '説明', '理解', 'まとめ']
        }
    }

    @classmethod
    def get_preset(cls, pid):
        return cls.PRESETS.get(pid)

    @classmethod
    def get_all_presets(cls):
        return cls.PRESETS

    @classmethod
    def detect_preset(cls, text):
        text_lower = text.lower()
        scores = {}
        for pid, p in cls.PRESETS.items():
            score = sum(1 for k in p['keywords'] if k.lower() in text_lower)
            if score > 0:
                scores[pid] = score
        return max(scores, key=scores.get) if scores else None


# ============================================================
# Premium Dark Theme
# ============================================================

class DarkTheme:
    COLORS = Colors.__dict__

    @classmethod
    def apply(cls, app):
        app.setStyle('Fusion')
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(Colors.BG_MAIN))
        pal.setColor(QPalette.WindowText, QColor(Colors.TEXT))
        pal.setColor(QPalette.Base, QColor(Colors.BG_INPUT))
        pal.setColor(QPalette.AlternateBase, QColor(Colors.BG_CARD))
        pal.setColor(QPalette.ToolTipBase, QColor(Colors.BG_CARD))
        pal.setColor(QPalette.ToolTipText, QColor(Colors.TEXT))
        pal.setColor(QPalette.Text, QColor(Colors.TEXT))
        pal.setColor(QPalette.Button, QColor(Colors.BG_CARD))
        pal.setColor(QPalette.ButtonText, QColor(Colors.TEXT))
        pal.setColor(QPalette.BrightText, QColor(Colors.PRIMARY_LIGHT))
        pal.setColor(QPalette.Highlight, QColor(Colors.PRIMARY))
        pal.setColor(QPalette.HighlightedText, QColor(Colors.TEXT))
        app.setPalette(pal)

        app.setStyleSheet(f"""
            * {{ font-family: "Segoe UI", "Yu Gothic UI", "Meiryo", sans-serif; }}

            QMainWindow {{ background-color: {Colors.BG_DARK}; }}

            QSplitter::handle {{
                background-color: {Colors.BORDER};
                width: 1px;
            }}

            QGroupBox {{
                font-weight: 600;
                font-size: 13px;
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
                margin-top: 14px;
                padding: 18px 12px 12px 12px;
                background-color: {Colors.BG_CARD};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 10px;
                color: {Colors.PRIMARY_LIGHT};
                font-size: 13px;
            }}

            QPushButton {{
                background-color: {Colors.BG_CARD};
                color: {Colors.TEXT};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_CARD_HOVER};
                border-color: {Colors.PRIMARY}80;
            }}
            QPushButton:pressed {{
                background-color: {Colors.PRIMARY};
                color: white;
            }}
            QPushButton#exec_btn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Colors.GRADIENT_START}, stop:1 {Colors.GRADIENT_END});
                color: white;
                border: none;
                font-size: 15px;
                font-weight: 700;
                border-radius: 10px;
            }}
            QPushButton#exec_btn:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Colors.PRIMARY_LIGHT}, stop:1 #a78bfa);
            }}
            QPushButton#stop_btn {{
                background-color: {Colors.DANGER};
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: 700;
            }}

            QComboBox {{
                background-color: {Colors.BG_INPUT};
                color: {Colors.TEXT};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                min-height: 20px;
            }}
            QComboBox:hover {{ border-color: {Colors.PRIMARY}80; }}
            QComboBox:focus {{ border-color: {Colors.PRIMARY}; }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_CARD};
                color: {Colors.TEXT};
                border: 1px solid {Colors.BORDER};
                selection-background-color: {Colors.PRIMARY};
                outline: none;
            }}

            QPlainTextEdit, QTextEdit {{
                background-color: {Colors.BG_INPUT};
                color: {Colors.TEXT};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
                padding: 12px;
                font-size: 14px;
                line-height: 1.6;
                selection-background-color: {Colors.PRIMARY}60;
            }}
            QPlainTextEdit:focus, QTextEdit:focus {{
                border-color: {Colors.PRIMARY};
            }}

            QTabWidget::pane {{
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
                background-color: {Colors.BG_CARD};
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: {Colors.BG_INPUT};
                color: {Colors.TEXT_MUTED};
                padding: 10px 24px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
                font-weight: 500;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Colors.GRADIENT_START}, stop:1 {Colors.GRADIENT_END});
                color: white;
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {Colors.BG_CARD_HOVER};
                color: {Colors.TEXT};
            }}

            QMenuBar {{
                background-color: {Colors.BG_DARK};
                color: {Colors.TEXT_DIM};
                border-bottom: 1px solid {Colors.BORDER};
                padding: 2px;
                font-size: 12px;
            }}
            QMenuBar::item:selected {{ background-color: {Colors.PRIMARY}; color: white; border-radius: 4px; }}
            QMenu {{
                background-color: {Colors.BG_CARD};
                color: {Colors.TEXT};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{ padding: 8px 24px; border-radius: 4px; }}
            QMenu::item:selected {{ background-color: {Colors.PRIMARY}; color: white; }}
            QMenu::separator {{ background-color: {Colors.BORDER}; height: 1px; margin: 4px 8px; }}

            QStatusBar {{
                background-color: {Colors.BG_DARK};
                color: {Colors.TEXT_MUTED};
                border-top: 1px solid {Colors.BORDER};
                font-size: 12px;
                padding: 2px 8px;
            }}

            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: {Colors.BG_INPUT};
                text-align: center;
                color: {Colors.TEXT};
                font-size: 11px;
                max-height: 8px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Colors.GRADIENT_START}, stop:1 {Colors.GRADIENT_END});
                border-radius: 4px;
            }}

            QTableWidget {{
                background-color: {Colors.BG_INPUT};
                color: {Colors.TEXT};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                gridline-color: {Colors.BORDER};
                font-size: 12px;
            }}
            QTableWidget::item:selected {{ background-color: {Colors.PRIMARY}40; }}
            QHeaderView::section {{
                background-color: {Colors.BG_CARD};
                color: {Colors.TEXT_DIM};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {Colors.PRIMARY};
                font-weight: 600;
                font-size: 11px;
            }}

            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                margin: 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background-color: {Colors.BORDER};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background-color: {Colors.PRIMARY}80; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

            QScrollBar:horizontal {{
                background-color: transparent;
                height: 8px;
                margin: 0 4px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {Colors.BORDER};
                border-radius: 4px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{ background-color: {Colors.PRIMARY}80; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

            QToolTip {{
                background-color: {Colors.BG_CARD};
                color: {Colors.TEXT};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                line-height: 1.4;
            }}

            QLabel#section_title {{ color: {Colors.PRIMARY_LIGHT}; font-size: 13px; font-weight: 600; }}
            QLabel#status_ok {{ color: {Colors.SECONDARY}; font-weight: 500; }}
            QLabel#status_warn {{ color: {Colors.ACCENT}; font-weight: 500; }}
            QLabel#counter {{ color: {Colors.TEXT_MUTED}; font-size: 11px; }}
        """)


# ============================================================
# Image Drop Area Widget
# ============================================================

class ImageDropArea(QFrame):
    """画像ドロップエリア"""
    imageDropped = Signal(str)  # ファイルパス
    imagePasted = Signal()  # クリップボード貼り付け
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self.setMaximumHeight(160)
        self._has_image = False
        self._update_style()
        
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignCenter)
        
        self._icon_label = QLabel("🖼️")
        self._icon_label.setStyleSheet("font-size: 32px;")
        self._icon_label.setAlignment(Qt.AlignCenter)
        
        self._text_label = QLabel("画像をドラッグ＆ドロップ\nまたはクリックして選択")
        self._text_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px;")
        self._text_label.setAlignment(Qt.AlignCenter)
        
        self._layout.addWidget(self._icon_label)
        self._layout.addWidget(self._text_label)
    
    def _update_style(self):
        border_color = Colors.PRIMARY if self._has_image else Colors.BORDER
        bg_color = f"{Colors.PRIMARY}10" if self._has_image else Colors.BG_INPUT
        self.setStyleSheet(f"""
            ImageDropArea {{
                background-color: {bg_color};
                border: 2px dashed {border_color};
                border-radius: 12px;
            }}
            ImageDropArea:hover {{
                background-color: {Colors.BG_CARD_HOVER};
                border-color: {Colors.PRIMARY};
            }}
        """)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
            self.setStyleSheet(f"""
                ImageDropArea {{
                    background-color: {Colors.PRIMARY}20;
                    border: 2px solid {Colors.PRIMARY};
                    border-radius: 12px;
                }}
            """)
    
    def dragLeaveEvent(self, event):
        self._update_style()
    
    def dropEvent(self, event):
        self._update_style()
        mime_data = event.mimeData()
        
        if mime_data.hasUrls():
            urls = mime_data.urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if file_path:
                    self.imageDropped.emit(file_path)
        elif mime_data.hasImage():
            self.imagePasted.emit()
    
    def mousePressEvent(self, event):
        """クリックでファイル選択ダイアログを開く"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "画像を選択", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*.*)"
        )
        if file_path:
            self.imageDropped.emit(file_path)
    
    def set_has_image(self, has_image: bool):
        self._has_image = has_image
        if has_image:
            self._icon_label.setText("✓")
            self._text_label.setText("画像が読み込まれました")
        else:
            self._icon_label.setText("🖼️")
            self._text_label.setText("画像をドラッグ＆ドロップ\nまたはクリックして選択")
        self._update_style()


# ============================================================
# Image Preview Widget
# ============================================================

class ImagePreviewWidget(QFrame):
    """画像プレビューウィジェット"""
    cleared = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(140, 100)
        self.setMaximumSize(260, 200)
        self.setStyleSheet(f"""
            ImagePreviewWidget {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        self._image_label = QLabel("画像プレビュー")
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        self._image_label.setScaledContents(True)
        layout.addWidget(self._image_label)
        
        # クリアボタン
        self._clear_btn = QPushButton("✕ クリア")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.DANGER};
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #dc2626;
            }}
        """)
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setVisible(False)
        layout.addWidget(self._clear_btn)
        
        self._info_label = QLabel("")
        self._info_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px;")
        self._info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._info_label)
    
    def set_image(self, pil_image, file_size_kb: float = None):
        """PIL Imageを表示"""
        if pil_image is None:
            self._clear()
            return
        
        # PIL Image → QPixmap
        qimage = ImageQt(pil_image)
        pixmap = QPixmap.fromImage(qimage)
        
        # スケーリング
        scaled = pixmap.scaled(
            self._image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        self._image_label.setPixmap(scaled)
        self._image_label.setText("")
        self._clear_btn.setVisible(True)
        
        # 情報表示
        info = f"{pil_image.size[0]}×{pil_image.size[1]}"
        if file_size_kb:
            info += f" | {file_size_kb:.0f}KB"
        self._info_label.setText(info)
    
    def _clear(self):
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText("画像プレビュー")
        self._clear_btn.setVisible(False)
        self._info_label.setText("")
        self.cleared.emit()
    
    def _on_clear(self):
        self._clear()


# ============================================================
# Conversation Manager
# ============================================================

class ConversationManager:
    """会話管理クラス"""
    
    def __init__(self):
        self.conversations: Dict[str, ConversationItem] = {}
        self.current_conversation_id: Optional[str] = None
    
    def create_conversation(self, title: str = "Untitled", model: str = "auto") -> str:
        """新しい会話を作成"""
        conversation_id = str(uuid.uuid4())
        conversation = ConversationItem(
            id=conversation_id,
            title=title,
            date=datetime.now(),
            model=model,
            message_count=0
        )
        self.conversations[conversation_id] = conversation
        self.current_conversation_id = conversation_id
        return conversation_id
    
    def get_conversation(self, conversation_id: str) -> Optional[ConversationItem]:
        """会話を取得"""
        return self.conversations.get(conversation_id)
    
    def update_conversation(self, conversation_id: str, **kwargs):
        """会話を更新"""
        conv = self.conversations.get(conversation_id)
        if conv:
            for key, value in kwargs.items():
                if hasattr(conv, key):
                    setattr(conv, key, value)
    
    def delete_conversation(self, conversation_id: str):
        """会話を削除"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
        if self.current_conversation_id == conversation_id:
            self.current_conversation_id = None
    
    def get_all_conversations(self) -> List[ConversationItem]:
        """全ての会話を取得"""
        return list(self.conversations.values())
    
    def set_current(self, conversation_id: str):
        """現在の会話を設定"""
        if conversation_id in self.conversations:
            self.current_conversation_id = conversation_id


# ============================================================
# Logging Setup
# ============================================================

def setup_gui_logging():
    """GUIアプリケーションのログローテーション設定（最大50MB: 10MB×5ファイル）"""
    project_root = Path(__file__).parent.parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "gui.log"

    # RotatingFileHandler: 10MB毎にローテーション、最大5ファイル保持
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # ルートロガーに追加
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 既存のハンドラーをクリア（重複防止）
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


# ============================================================
# Main Window
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Smart Router Pro")
        self.setMinimumSize(900, 600)
        self.settings = QSettings('LLMSmartRouter', 'Pro')
        self.router_path = self.settings.value(
            'router_path', str(Path(__file__).parent.parent.parent))
        self.worker = None
        self.session_stats = {
            'requests': 0, 'local': 0, 'cloud': 0,
            'tokens_in': 0, 'tokens_out': 0, 'cost': 0.0
        }
        # リクエストキュー（並列リクエスト処理用）
        from collections import deque
        self.request_queue = deque()
        
        # 会話管理
        self.conv_manager = ConversationManager()
        
        # 画像処理
        self.image_handler = ImageHandler()
        self.vision_builder = VisionRequestBuilder('claude')
        
        self._init_ui()
        self._init_menu()
        self._init_shortcuts()
        self._init_timers()
        QTimer.singleShot(500, self.check_api_key)
        QTimer.singleShot(1000, self._check_registry_freshness)  # レジストリ鮮度チェック

        # バッジ初期化
        self._on_model_changed(self.model_combo.currentIndex())

        # 初期会話を作成
        self._create_new_conversation()

    # ── UI Setup ─────────────────────────────────

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # メインスプリッター（3ペイン）
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(1)
        root.addWidget(self.main_splitter)

        # 左: サイドバー（会話一覧）
        self.conversation_sidebar = ConversationSidebar()
        self.conversation_sidebar.conversation_selected.connect(self._on_conversation_selected)
        self.conversation_sidebar.conversation_double_clicked.connect(self._on_conversation_double_clicked)
        self.conversation_sidebar.conversation_new_requested.connect(self._create_new_conversation)
        self.conversation_sidebar.conversation_delete_requested.connect(self._on_conversation_delete)
        self.conversation_sidebar.conversation_rename_requested.connect(self._on_conversation_rename)
        self.conversation_sidebar.conversation_pin_requested.connect(self._on_conversation_pin)
        self.main_splitter.addWidget(self.conversation_sidebar)

        # 中央: タブエリア（複数会話）
        self.conversation_tabs = ConversationTabWidget()
        self.conversation_tabs.tab_conversation_switched.connect(self._on_tab_switched)
        self.conversation_tabs.tab_conversation_closed.connect(self._on_tab_closed)
        self.conversation_tabs.tab_conversation_new_requested.connect(self._create_new_conversation)
        self.conversation_tabs.tab_conversation_close_others_requested.connect(self._on_close_other_tabs)
        self.conversation_tabs.tab_conversation_close_all_requested.connect(self._on_close_all_tabs)
        self.conversation_tabs.tab_conversation_close_right_requested.connect(self._on_close_tabs_to_right)
        self.main_splitter.addWidget(self.conversation_tabs)

        # 右: チャットパネル（入力・出力）
        self.chat_panel = self._build_chat_panel()
        self.main_splitter.addWidget(self.chat_panel)

        # スプリッター比率（2:4:4）と伸縮ファクター
        self.main_splitter.setStretchFactor(0, 2)  # サイドバー
        self.main_splitter.setStretchFactor(1, 4)  # タブエリア
        self.main_splitter.setStretchFactor(2, 4)  # チャットパネル
        self._splitter_ratios = [0.2, 0.4, 0.4]
        self.main_splitter.setSizes([300, 500, 500])

        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(180)
        self.progress.setFixedHeight(8)
        self.progress.setToolTip("リクエスト処理中...")
        self.progress.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress)

        self._mem_label = QLabel()
        self._mem_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        self._mem_label.setToolTip("アプリケーションのメモリ使用量")
        self.status_bar.addPermanentWidget(self._mem_label)

        self.status_bar.showMessage("Ready")

    def _build_chat_panel(self):
        """チャットパネルを構築"""
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {Colors.BG_MAIN};")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # スクロール可能にして小さいウィンドウでも操作可能にする
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.BG_MAIN}; border: none; }}"
        )

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # ── Header ──
        header = QLabel("💬 Chat")
        header.setStyleSheet(
            f"color: {Colors.PRIMARY_LIGHT}; font-size: 18px; font-weight: 800;"
            f" letter-spacing: -0.5px; padding: 4px 0 8px 0;"
        )
        lay.addWidget(header)

        # ── Model Badge (目立つ表示) ──
        self.model_badge = ModelBadge()
        self.model_badge.setToolTip(
            "現在選択中のモデル\n"
            "Auto=緑 / Local=黄 / Cloud=青"
        )
        lay.addWidget(self.model_badge)

        # ── Model Selector ──
        mg = QGroupBox("Model")
        ml = QVBoxLayout(mg)
        self.model_combo = QComboBox()
        self.model_combo.setToolTip(
            "使用するモデルを選択\n"
            "Auto: 入力内容に応じて最適なモデルを自動選択\n"
            "Local: ローカルLLM（LM Studio等）を使用\n"
            "Cloud: クラウドAPI（Claude等）を使用\n"
            "ショートカット: Ctrl+M でモデルを切り替え"
        )
        self.model_combo.addItem("  Auto (Recommended)", "auto")
        self.model_combo.addItem("  Local LLM", "local")
        self.model_combo.addItem("  Claude API", "claude")
        self._populate_model_combo()
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        ml.addWidget(self.model_combo)

        status_row = QHBoxLayout()
        self._status_dot = StatusDot(Colors.SECONDARY)
        self._status_dot.setToolTip("モデル接続状態（緑=正常 / 黄=切替中 / 赤=エラー）")
        status_row.addWidget(self._status_dot)
        self.model_status = QLabel("Auto routing active")
        self.model_status.setObjectName("status_ok")
        self.model_status.setToolTip("現在のルーティング状態とフォールバックチェーン")
        status_row.addWidget(self.model_status)
        status_row.addStretch()

        # モデルリフレッシュボタン
        self._refresh_btn = QPushButton("Scan")
        self._refresh_btn.setFixedWidth(60)
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ background: {Colors.BG_TERTIARY}; color: {Colors.TEXT_MUTED};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 4px; padding: 2px 6px; font-size: 11px; }}"
            f" QPushButton:hover {{ background: {Colors.BG_HOVER}; color: {Colors.TEXT_PRIMARY}; }}"
        )
        self._refresh_btn.setToolTip("ローカルLLMランタイムを再スキャン")
        self._refresh_btn.clicked.connect(self._refresh_models)
        status_row.addWidget(self._refresh_btn)

        ml.addLayout(status_row)
        lay.addWidget(mg)

        # ── Preset Selector ──
        pg = QGroupBox("Preset")
        pl = QVBoxLayout(pg)
        self.preset_combo = QComboBox()
        self.preset_combo.setToolTip(
            "用途別プリセットを選択\n"
            "Auto-detect: 入力内容からプリセットを自動判定\n"
            "各プリセットにはシステムプロンプトと推奨モデルが設定されています"
        )
        self.preset_combo.addItem("  Auto-detect", None)
        for pid, p in PresetManager.get_all_presets().items():
            self.preset_combo.addItem(f"  {p['icon']}  {p['name']}", pid)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        pl.addWidget(self.preset_combo)

        self.preset_desc = QLabel("AI will detect the best preset")
        self.preset_desc.setWordWrap(True)
        self.preset_desc.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px;")
        pl.addWidget(self.preset_desc)
        lay.addWidget(pg)

        # ── Image Input ──
        img_g = QGroupBox("Image Input")
        img_l = QHBoxLayout(img_g)
        
        # ドロップエリア
        self.drop_area = ImageDropArea()
        self.drop_area.setToolTip(
            "画像をドラッグ＆ドロップ、またはクリックしてファイルを選択\n"
            "対応形式: PNG, JPG, GIF, BMP, WebP\n"
            "画像付きの質問はVision対応モデル（Claude）で処理されます"
        )
        self.drop_area.imageDropped.connect(self._on_image_dropped)
        self.drop_area.imagePasted.connect(self._on_image_pasted)
        img_l.addWidget(self.drop_area)
        
        # プレビュー
        self.image_preview = ImagePreviewWidget()
        self.image_preview.cleared.connect(self._on_image_cleared)
        img_l.addWidget(self.image_preview)
        
        # 画像操作ボタン
        btn_layout = QVBoxLayout()
        self.paste_img_btn = QPushButton("📋 Paste")
        self.paste_img_btn.setFixedHeight(32)
        self.paste_img_btn.setToolTip("クリップボードから画像を貼り付け（スクリーンショット等）")
        self.paste_img_btn.clicked.connect(self._paste_image_from_clipboard)
        btn_layout.addWidget(self.paste_img_btn)

        self.clear_img_btn = QPushButton("🗑️ Clear")
        self.clear_img_btn.setFixedHeight(32)
        self.clear_img_btn.setToolTip("読み込んだ画像をクリア")
        self.clear_img_btn.clicked.connect(self._on_image_cleared)
        self.clear_img_btn.setEnabled(False)
        btn_layout.addWidget(self.clear_img_btn)
        
        btn_layout.addStretch()
        img_l.addLayout(btn_layout)
        
        lay.addWidget(img_g)

        # ── Input ──
        ig = QGroupBox("Input")
        il = QVBoxLayout(ig)
        self.input_text = QPlainTextEdit()
        self.input_text.setToolTip("質問やタスクを入力（Ctrl+Enter で実行）")
        self.input_text.setPlaceholderText(
            "Type your question or task here...\n\n"
            "Examples:\n"
            "  - Review this construction cost estimate\n"
            "  - Optimize my streaming schedule\n"
            "  - Debug this Python code\n"
            "  - Describe this image"
        )
        self.input_text.setMinimumHeight(80)
        self.input_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.input_text.textChanged.connect(self._update_counter)
        il.addWidget(self.input_text)

        counter_row = QHBoxLayout()
        self._char_counter = QLabel("0 chars")
        self._char_counter.setObjectName("counter")
        counter_row.addWidget(self._char_counter)
        counter_row.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(28)
        clear_btn.setToolTip("入力テキストをクリア（Ctrl+L）")
        clear_btn.clicked.connect(self.input_text.clear)
        counter_row.addWidget(clear_btn)

        paste_btn = QPushButton("Paste")
        paste_btn.setFixedHeight(28)
        paste_btn.setToolTip("クリップボードからテキストを貼り付け")
        paste_btn.clicked.connect(self._paste)
        counter_row.addWidget(paste_btn)

        load_btn = QPushButton("File")
        load_btn.setFixedHeight(28)
        load_btn.setToolTip("テキストファイルを読み込み（Ctrl+O）")
        load_btn.clicked.connect(self.load_file)
        counter_row.addWidget(load_btn)
        il.addLayout(counter_row)
        lay.addWidget(ig)

        # ── System Prompt ──
        sg = QGroupBox("System Prompt (optional)")
        sl = QVBoxLayout(sg)
        self.system_prompt = QPlainTextEdit()
        self.system_prompt.setToolTip(
            "AIの役割や制約を指定するシステムプロンプト（任意）\n"
            "プリセット選択で自動設定されます"
        )
        self.system_prompt.setPlaceholderText("Custom role or constraints...")
        self.system_prompt.setMinimumHeight(40)
        self.system_prompt.setMaximumHeight(120)
        sl.addWidget(self.system_prompt)
        lay.addWidget(sg)

        # ── Execute ──
        self.execute_btn = PulseButton("  Execute  (Ctrl+Enter)")
        self.execute_btn.setObjectName("exec_btn")
        self.execute_btn.setMinimumHeight(52)
        self.execute_btn.setCursor(Qt.PointingHandCursor)
        self.execute_btn.setToolTip("入力内容をLLMに送信して応答を取得（Ctrl+Enter）")
        self.execute_btn.clicked.connect(self.execute)
        lay.addWidget(self.execute_btn)

        self.stop_btn = QPushButton("  Stop  (Esc)")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.setMinimumHeight(52)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setToolTip("実行中のリクエストを中止（Esc）")
        self.stop_btn.clicked.connect(self.stop_execution)
        self.stop_btn.setVisible(False)
        lay.addWidget(self.stop_btn)

        lay.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return panel

    # ── Menu ─────────────────────────────────────

    def _init_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("File")
        self._add_action(fm, "New Conversation", self._create_new_conversation, "Ctrl+N")
        self._add_action(fm, "Open File...", self.load_file, QKeySequence.Open)
        fm.addSeparator()
        self._add_action(fm, "Exit", self.close, QKeySequence.Quit)

        em = mb.addMenu("Edit")
        self._add_action(em, "Clear Input", self.input_text.clear, "Ctrl+L")
        self._add_action(em, "Copy Output", self.copy_output, "Ctrl+Shift+C")

        vm = mb.addMenu("View")
        self._add_action(vm, "Toggle Sidebar", self._toggle_sidebar, "Ctrl+B")
        self._add_action(vm, "Toggle Tabs", self._toggle_tabs, "Ctrl+T")

        sm = mb.addMenu("Settings")
        self._add_action(sm, "API Keys...", self.open_settings, "Ctrl+,")
        self._add_action(sm, "Router Config...", self._open_config)

        tm = mb.addMenu("Tools")
        self._add_action(tm, "Reset Stats", self._reset_stats)

        hm = mb.addMenu("Help")
        self._add_action(hm, "Shortcuts", self._show_shortcuts, "F1")
        self._add_action(hm, "About", self._show_about)

    def _add_action(self, menu, text, handler, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(handler)
        menu.addAction(a)

    # ── Shortcuts ────────────────────────────────

    def _init_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.execute)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.stop_execution)
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._cycle_model)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self._close_current_tab)
        QShortcut(QKeySequence("Ctrl+Tab"), self).activated.connect(self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self).activated.connect(self._prev_tab)

    # ── Responsive Resize ────────────────────────

    def resizeEvent(self, event):
        """ウィンドウリサイズ時にレイアウトを動的調整"""
        super().resizeEvent(event)
        w = event.size().width()
        h = event.size().height()

        # スプリッター比率を維持
        total = self.main_splitter.width()
        if total > 0:
            self.main_splitter.setSizes([
                int(total * r) for r in self._splitter_ratios
            ])

        # 小さいウィンドウではサイドバーを自動非表示
        if w < 1100:
            if self.conversation_sidebar.isVisible():
                self.conversation_sidebar.setVisible(False)
        else:
            if not self.conversation_sidebar.isVisible():
                self.conversation_sidebar.setVisible(True)

        # 画像エリアの高さを調整
        if hasattr(self, 'drop_area'):
            img_h = max(80, min(160, int(h * 0.12)))
            self.drop_area.setMaximumHeight(img_h)

    # ── Timers ───────────────────────────────────

    def _init_timers(self):
        t = QTimer(self)
        t.timeout.connect(self._update_mem)
        t.start(5000)

    def _update_mem(self):
        try:
            import psutil
            mb = psutil.Process().memory_info().rss / 1024 / 1024
            self._mem_label.setText(f"{mb:.0f} MB")
        except Exception:
            pass

    # ── Conversation Management ──────────────────

    def _create_new_conversation(self):
        """新しい会話を作成"""
        model = self.model_combo.currentData() or "auto"
        conversation_id = self.conv_manager.create_conversation(
            title="Untitled",
            model=model
        )
        
        # サイドバーに追加
        conv = self.conv_manager.get_conversation(conversation_id)
        self.conversation_sidebar.add_conversation(conv)
        
        # タブに追加
        self.conversation_tabs.add_conversation_tab(
            conversation_id, 
            title="Untitled",
            model=model
        )
        
        # 選択
        self.conversation_sidebar.select_conversation(conversation_id)
        
        self.status_bar.showMessage("New conversation created", 2000)

    def _on_conversation_selected(self, conversation_id: str):
        """サイドバーで会話が選択された"""
        conv = self.conv_manager.get_conversation(conversation_id)
        if not conv:
            return
        
        # タブを切り替え
        if self.conversation_tabs.has_tab(conversation_id):
            self.conversation_tabs.switch_to_tab(conversation_id)
        else:
            # タブがない場合は開く
            self.conversation_tabs.add_conversation_tab(
                conversation_id,
                title=conv.title,
                model=conv.model
            )
        
        self.conv_manager.set_current(conversation_id)

    def _on_conversation_double_clicked(self, conversation_id: str):
        """サイドバーで会話がダブルクリックされた"""
        self._on_conversation_selected(conversation_id)

    def _on_conversation_delete(self, conversation_id: str):
        """会話を削除"""
        self.conv_manager.delete_conversation(conversation_id)
        self.conversation_sidebar.remove_conversation(conversation_id)
        self.conversation_tabs.close_tab(conversation_id)
        
        # 残りの会話があれば選択
        remaining = self.conv_manager.get_all_conversations()
        if remaining:
            self.conversation_sidebar.select_conversation(remaining[0].id)
        
        self.status_bar.showMessage("Conversation deleted", 2000)

    def _on_conversation_rename(self, conversation_id: str, new_title: str):
        """会話名を変更"""
        self.conv_manager.update_conversation(conversation_id, title=new_title)
        self.conversation_sidebar.update_conversation(conversation_id, title=new_title)
        self.conversation_tabs.update_tab_title(conversation_id, new_title)

    def _on_conversation_pin(self, conversation_id: str, is_pinned: bool):
        """会話をピン留め"""
        self.conv_manager.update_conversation(conversation_id, is_pinned=is_pinned)
        self.conversation_sidebar.update_conversation(conversation_id, is_pinned=is_pinned)

    def _on_tab_switched(self, conversation_id: str):
        """タブが切り替わった"""
        conv = self.conv_manager.get_conversation(conversation_id)
        if conv:
            self.conv_manager.set_current(conversation_id)
            self.conversation_sidebar.select_conversation(conversation_id)
            # モデル表示を更新（シグナルループ防止）
            self.model_combo.blockSignals(True)
            try:
                self.model_combo.setCurrentText(f"  {conv.model.capitalize()}")
            finally:
                self.model_combo.blockSignals(False)

    def _on_tab_closed(self, conversation_id: str):
        """タブが閉じられた"""
        # タブは閉じるが、会話自体は削除しない（サイドバーに残す）
        pass

    def _on_close_other_tabs(self, keep_conversation_id: str):
        """他のタブを閉じる"""
        self.conversation_tabs.close_all_tabs_except(keep_conversation_id)

    def _on_close_all_tabs(self):
        """全タブを閉じる"""
        self.conversation_tabs.close_all_tabs()

    def _on_close_tabs_to_right(self, conversation_id: str):
        """右のタブを閉じる"""
        self.conversation_tabs.close_all_tabs_to_right(conversation_id)

    def _close_current_tab(self):
        """現在のタブを閉じる"""
        current_id = self.conversation_tabs.get_current_conversation_id()
        if current_id:
            self.conversation_tabs.close_tab(current_id)

    def _next_tab(self):
        """次のタブへ"""
        count = self.conversation_tabs.get_tab_count()
        current = self.conversation_tabs.currentIndex()
        if count > 0:
            next_idx = (current + 1) % count
            self.conversation_tabs.setCurrentIndex(next_idx)

    def _prev_tab(self):
        """前のタブへ"""
        count = self.conversation_tabs.get_tab_count()
        current = self.conversation_tabs.currentIndex()
        if count > 0:
            prev_idx = (current - 1) % count
            self.conversation_tabs.setCurrentIndex(prev_idx)

    def _toggle_sidebar(self):
        """サイドバーの表示/非表示"""
        self.conversation_sidebar.setVisible(not self.conversation_sidebar.isVisible())

    def _toggle_tabs(self):
        """タブエリアの表示/非表示"""
        self.conversation_tabs.setVisible(not self.conversation_tabs.isVisible())

    # ── Event Handlers ───────────────────────────

    def _update_counter(self):
        n = len(self.input_text.toPlainText())
        self._char_counter.setText(f"{n:,} chars")
        if n > 50000:
            self._char_counter.setStyleSheet(f"color: {Colors.DANGER}; font-size: 11px;")
        elif n > 10000:
            self._char_counter.setStyleSheet(f"color: {Colors.ACCENT}; font-size: 11px;")
        else:
            self._char_counter.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")

    def _populate_model_combo(self):
        """レジストリからモデルコンボを動的更新"""
        try:
            import scanner.registry as _rg

            project_root = Path(__file__).parent.parent.parent
            registry = _rg.ModelRegistry(
                cache_path=str(project_root / "data" / "model_registry.json")
            )
            if registry.get_total_count() == 0:
                return  # レジストリ空ならデフォルト3項目のまま

            # デフォルト3項目をクリアして再構築
            self.model_combo.clear()
            self.model_combo.addItem("  Auto (Recommended)", "auto")

            # ローカルモデル
            local_models = registry.get_local_models()
            if local_models:
                for m in local_models:
                    rt = m.runtime.runtime_type.value if m.runtime else "local"
                    label = f"  [{rt}] {m.name}"
                    self.model_combo.addItem(label, f"local:{m.id}")

            # セパレーター
            if local_models:
                self.model_combo.insertSeparator(self.model_combo.count())

            # クラウドモデル
            cloud_models = registry.get_cloud_models()
            if cloud_models:
                for m in cloud_models:
                    label = f"  [{m.provider}] {m.name}"
                    self.model_combo.addItem(label, f"cloud:{m.id}")
            else:
                # フォールバック: 従来のハードコード項目
                self.model_combo.addItem("  Claude API", "claude")

        except ImportError:
            pass  # scanner パッケージ未インストール時はデフォルトのまま
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"モデルコンボ更新失敗: {e}")

    def _refresh_models(self):
        """Scanボタン: バックグラウンドでランタイムスキャン実行"""
        # 二重スキャン防止
        if hasattr(self, '_scan_thread') and self._scan_thread is not None and self._scan_thread.isRunning():
            return

        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("...")
        self.model_status.setText("Scanning...")
        self._status_dot.set_color(Colors.WARNING)

        class _ScanThread(QThread):
            finished = Signal(int)

            def __init__(self, parent=None):
                super().__init__(parent)

            def run(self):
                import asyncio
                try:
                    import scanner.scanner as _sc
                    import scanner.registry as _rg
                    s = _sc.MultiRuntimeScanner()
                    loop = asyncio.new_event_loop()
                    try:
                        results = loop.run_until_complete(s.scan_all())
                    finally:
                        loop.close()
                    project_root = Path(__file__).parent.parent.parent
                    registry = _rg.ModelRegistry(
                        cache_path=str(project_root / "data" / "model_registry.json")
                    )
                    registry.update(results)
                    self.finished.emit(registry.get_total_count())
                except Exception:
                    self.finished.emit(-1)

        # 選択保存
        self._prev_model_data = self.model_combo.currentData()

        self._scan_thread = _ScanThread(parent=self)

        def _on_done(count):
            self._refresh_btn.setEnabled(True)
            self._refresh_btn.setText("Scan")
            if count >= 0:
                self.model_combo.blockSignals(True)
                try:
                    self._populate_model_combo()
                    # 選択復元
                    if self._prev_model_data:
                        idx = self.model_combo.findData(self._prev_model_data)
                        if idx >= 0:
                            self.model_combo.setCurrentIndex(idx)
                finally:
                    self.model_combo.blockSignals(False)
                self.model_status.setText(f"{count} models detected")
                self._status_dot.set_color(Colors.SECONDARY)
            else:
                self.model_status.setText("Scan failed")
                self._status_dot.set_color(Colors.ERROR)

        self._scan_thread.finished.connect(_on_done)
        self._scan_thread.start()

    def _get_fallback_summary(self):
        """fallback_priority.jsonからチェーン概要を生成"""
        try:
            import json as _json
            priority_path = Path(__file__).resolve().parent.parent.parent / "data" / "fallback_priority.json"
            if not priority_path.exists():
                return None
            data = _json.loads(priority_path.read_text(encoding="utf-8"))
            refs = data.get("priority", [])
            if not refs:
                return None
            names = []
            for ref in refs[:4]:  # 最大4つまで表示
                if ref.startswith("local:"):
                    mid = ref[len("local:"):]
                    names.append(mid.split("/")[-1] if "/" in mid else mid)
                elif ref == "cloud":
                    names.append("Claude")
                else:
                    names.append(ref)
            summary = " → ".join(names)
            if len(refs) > 4:
                summary += f" (+{len(refs) - 4})"
            return summary
        except Exception:
            return None

    def _on_model_changed(self, idx):
        m = self.model_combo.currentData()
        if not m:
            return
        if m == "auto":
            summary = self._get_fallback_summary()
            if summary:
                self.model_status.setText(f"Auto: {summary}")
                self.model_badge.set_model(m, summary)
            else:
                self.model_status.setText("Auto routing active")
                self.model_badge.set_model(m, "入力内容に応じて最適なモデルを自動選択")
            self._status_dot.set_color(Colors.SECONDARY)
        elif m.startswith("local:") or m == "local":
            detail = m.replace('local:', '')
            self.model_status.setText(f"Local: {detail}")
            self.model_badge.set_model(m, detail or "ローカルLLM")
            self._status_dot.set_color(Colors.ACCENT)
        elif m.startswith("cloud:") or m == "claude":
            detail = m.replace('cloud:', '')
            self.model_status.setText(f"Cloud: {detail}")
            self.model_badge.set_model(m, detail or "Claude API")
            self._status_dot.set_color(Colors.CYAN)
        else:
            self.model_status.setText(m)
            self.model_badge.set_model(m, m)
            self._status_dot.set_color(Colors.CYAN)

        # 現在の会話のモデルを更新
        current_id = self.conv_manager.current_conversation_id
        if current_id:
            self.conv_manager.update_conversation(current_id, model=m)
            self.conversation_sidebar.update_conversation(current_id, model=m)
            self.conversation_tabs.update_tab_model(current_id, m)

    def _on_preset_changed(self, idx):
        pid = self.preset_combo.currentData()
        if pid:
            p = PresetManager.get_preset(pid)
            self.preset_desc.setText(p['description'])
            self.system_prompt.setPlainText(p['system_prompt'])
        else:
            self.preset_desc.setText("AI will detect the best preset")
            self.system_prompt.clear()

    def _cycle_model(self):
        c = self.model_combo
        c.setCurrentIndex((c.currentIndex() + 1) % c.count())

    def _paste(self):
        self.input_text.setPlainText(QApplication.clipboard().text())

    # ── Image Handlers ──────────────────────────

    def _on_image_dropped(self, file_path: str):
        """ドラッグ＆ドロップで画像を読み込み"""
        success, msg = self.image_handler.load_from_file(file_path)
        if success:
            self._update_image_preview()
            self.drop_area.set_has_image(True)
            self.clear_img_btn.setEnabled(True)
            self.status_bar.showMessage(f"Image loaded: {msg}", 3000)
        else:
            QMessageBox.warning(self, "Image Error", msg)

    def _on_image_pasted(self):
        """ドラッグ＆ドロップでの画像貼り付け"""
        self._paste_image_from_clipboard()

    def _paste_image_from_clipboard(self):
        """クリップボードから画像を貼り付け"""
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        if mime_data.hasImage():
            # QImage → PIL Image
            qimage = clipboard.image()
            if not qimage.isNull():
                # QImage → bytes
                buffer = QBuffer()
                buffer.open(QBuffer.ReadWrite)
                qimage.save(buffer, "PNG")
                data = bytes(buffer.data().data())
                
                success, msg = self.image_handler.load_from_bytes(data, "image/png")
                if success:
                    self._update_image_preview()
                    self.drop_area.set_has_image(True)
                    self.clear_img_btn.setEnabled(True)
                    self.status_bar.showMessage(f"Image pasted: {msg}", 3000)
                else:
                    QMessageBox.warning(self, "Image Error", msg)
        elif mime_data.hasUrls():
            urls = mime_data.urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if file_path:
                    self._on_image_dropped(file_path)
        else:
            QMessageBox.information(self, "Clipboard", "No image found in clipboard")

    def _update_image_preview(self):
        """画像プレビューを更新"""
        if self.image_handler.has_image():
            img = self.image_handler.get_image()
            file_size = self.image_handler.get_file_size_kb()
            self.image_preview.set_image(img, file_size)

    def _on_image_cleared(self):
        """画像をクリア"""
        self.image_handler.clear()
        self.image_preview._clear()
        self.drop_area.set_has_image(False)
        self.clear_img_btn.setEnabled(False)
        self.status_bar.showMessage("Image cleared", 2000)

    # ── Execution ────────────────────────────────

    def execute(self):
        text = self.input_text.toPlainText().strip()
        has_image = self.image_handler.has_image()

        if not text and not has_image:
            QMessageBox.warning(self, "Error", "Input is empty")
            return

        # 既にリクエスト実行中ならキューに追加
        if self.worker and self.worker.isRunning():
            pid = self.preset_combo.currentData()
            model = self.model_combo.currentData()
            if has_image:
                model = 'claude'
            image_base64 = None
            if has_image:
                image_base64, _ = self.image_handler.to_base64()

            self.request_queue.append({
                'text': text,
                'model': model,
                'preset_id': pid,
                'image_base64': image_base64,
                'has_image': has_image
            })
            queue_len = len(self.request_queue)
            self.status_bar.showMessage(f"⏳ リクエストをキューに追加（待機中: {queue_len}）", 3000)
            return

        pid = self.preset_combo.currentData()
        if not pid:
            detected = PresetManager.detect_preset(text)
            if detected:
                p = PresetManager.get_preset(detected)
                self.status_bar.showMessage(f"Preset: {p['name']}", 2000)

        model = self.model_combo.currentData()

        # 画像がある場合はVision対応モデルを強制
        if has_image:
            model = 'claude'  # VisionタスクはClaude優先
            self.status_bar.showMessage("Using Claude for vision task", 2000)

        self.execute_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_bar.showMessage("Processing...")
        self.execute_btn.start_pulse()
        self.model_badge.set_processing(True)

        # 画像がある場合はバッジも更新
        if has_image:
            self.model_badge.set_model('claude', 'Vision (Claude)')

        # 現在の会話を更新
        current_id = self.conv_manager.current_conversation_id
        if current_id:
            self.conv_manager.update_conversation(
                current_id,
                message_count=self.conv_manager.get_conversation(current_id).message_count + 1
            )
            self.conversation_tabs.set_tab_loading(current_id, True)

            # ユーザー入力をタブに表示
            idx = self.conversation_tabs.get_tab_index(current_id)
            if idx >= 0:
                tab_widget = self.conversation_tabs.widget(idx)
                if hasattr(tab_widget, 'add_message'):
                    tab_widget.add_message("user", text)

        # 画像データを準備
        image_base64 = None
        if has_image:
            image_base64, mime_type = self.image_handler.to_base64()

        # APIキーはメインスレッドで取得（QThread内でのSecureKeyManager呼び出し回避）
        _api_key = None
        try:
            km = SecureKeyManager()
            _api_key = km.get_api_key('anthropic')
        except Exception:
            pass

        self.worker = LLMWorker(
            self.router_path, text,
            None if model == "auto" else model,
            config={'timeout': 120, 'image_base64': image_base64},
            api_key=_api_key,
        )
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def stop_execution(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_bar.showMessage("Stopped")
            self._reset_ui()

    def _on_finished(self, result):
        # 実際に使われたモデルをバッジに表示
        used_model = result.get('model', '')
        if used_model:
            self.model_badge.set_detail(f"最後に使用: {used_model}")

        # レスポンスをタブに表示
        response_text = result.get('response', '')
        current_id = self.conv_manager.current_conversation_id
        if current_id and response_text:
            idx = self.conversation_tabs.get_tab_index(current_id)
            if idx >= 0:
                tab_widget = self.conversation_tabs.widget(idx)
                if hasattr(tab_widget, 'add_message'):
                    tab_widget.add_message("assistant", response_text, used_model)

        # 現在の会話IDを取得（再利用）

        # 会話タイトルを自動生成（初回メッセージの場合）
        if current_id:
            conv = self.conv_manager.get_conversation(current_id)
            if conv and conv.title == "Untitled" and conv.message_count == 1:
                # 最初のメッセージからタイトルを生成
                input_text = self.input_text.toPlainText()[:30]
                if input_text:
                    auto_title = input_text + ("..." if len(input_text) >= 30 else "")
                    self._on_conversation_rename(current_id, auto_title)

            self.conversation_tabs.set_tab_loading(current_id, False)

        # 課金警告チェック
        metadata = result.get('metadata', {})
        if metadata.get('costWarning'):
            cost_msg = metadata.get('costWarningMessage', 'クラウドAPIを使用しました')
            QMessageBox.warning(
                self,
                "💰 課金警告",
                f"⚠️  {cost_msg}\n\n"
                f"ローカルLLMが利用できなかったため、有料のクラウドAPIにフォールバックしました。\n"
                f"継続して使用する場合は課金が発生します。"
            )

        self._update_stats(result)
        self._reset_ui()
        self._process_next_queued_request()

    def _on_error(self, msg):
        current_id = self.conv_manager.current_conversation_id
        if current_id:
            self.conversation_tabs.set_tab_loading(current_id, False)
        self._reset_ui()
        self._process_next_queued_request()

    def _on_progress(self, msg):
        self.status_bar.showMessage(msg)

    def _reset_ui(self):
        self.execute_btn.stop_pulse()
        self.execute_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.progress.setVisible(False)
        self.model_badge.set_processing(False)
        # バッジを現在のコンボ選択に戻す
        self._on_model_changed(self.model_combo.currentIndex())
        self.status_bar.showMessage("Ready")

    def _process_next_queued_request(self):
        """キューから次のリクエストを取り出して実行"""
        if not self.request_queue:
            return

        next_req = self.request_queue.popleft()
        queue_len = len(self.request_queue)
        self.status_bar.showMessage(
            f"⏳ キューから次のリクエストを実行中（残り: {queue_len}）", 3000
        )

        # 入力フィールドを次のリクエストの内容で更新
        self.input_text.setPlainText(next_req['text'])

        # 画像がある場合は復元（現在はbase64のみ保存）
        if next_req['has_image'] and next_req['image_base64']:
            # 画像復元は省略（複雑なため、テキストのみキュー処理）
            pass

        # リクエスト実行
        self.execute_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.execute_btn.start_pulse()

        current_id = self.conv_manager.current_conversation_id
        if current_id:
            self.conv_manager.update_conversation(
                current_id,
                message_count=self.conv_manager.get_conversation(current_id).message_count + 1
            )
            self.conversation_tabs.set_tab_loading(current_id, True)

        _api_key = None
        try:
            km = SecureKeyManager()
            _api_key = km.get_api_key('anthropic')
        except Exception:
            pass

        self.worker = LLMWorker(
            self.router_path,
            next_req['text'],
            None if next_req['model'] == "auto" else next_req['model'],
            config={'timeout': 120, 'image_base64': next_req['image_base64']},
            api_key=_api_key,
        )
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _update_stats(self, result):
        self.session_stats['requests'] += 1
        if result.get('model') == 'local':
            self.session_stats['local'] += 1
        else:
            self.session_stats['cloud'] += 1

    # ── API Key ──────────────────────────────────

    def check_api_key(self):
        km = SecureKeyManager()
        if not km.get_api_key('anthropic'):
            reply = QMessageBox.question(
                self, "API Key Required",
                "Anthropic API key is not configured.\nSet it now?\n\n"
                "Keys are stored securely in your OS credential store.",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.open_settings()

    def _check_registry_freshness(self):
        """起動時にモデルレジストリの鮮度をチェックし、古ければスキャンを提案"""
        try:
            import scanner.registry as _rg
            project_root = Path(__file__).parent.parent.parent
            registry = _rg.ModelRegistry(
                cache_path=str(project_root / "data" / "model_registry.json")
            )

            if not registry.is_cache_valid():
                reply = QMessageBox.question(
                    self,
                    "🔄 モデルスキャン推奨",
                    "モデルレジストリのキャッシュが古くなっています（5分以上経過）。\n\n"
                    "最新のローカルLLMランタイムをスキャンしますか？\n"
                    "（スキャンには数秒かかります）",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self._refresh_models()
        except ImportError:
            pass  # scanner パッケージ未インストール時は無視
        except Exception as e:
            logging.getLogger(__name__).debug(f"レジストリチェック失敗: {e}")

    def open_settings(self):
        SettingsDialog(self).exec()

    def _open_config(self):
        p = os.path.join(self.router_path, 'config.yaml')
        if os.path.exists(p):
            subprocess.Popen(['notepad', p])
        else:
            QMessageBox.warning(self, "Error", "config.yaml not found")

    # ── File Operations ──────────────────────────

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "",
            "Text (*.txt);;Markdown (*.md);;All (*.*)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.input_text.setPlainText(f.read())
                self.status_bar.showMessage(f"Loaded: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def copy_output(self):
        """現在のタブの会話内容をクリップボードにコピー"""
        current_id = self.conversation_tabs.get_current_conversation_id()
        if not current_id:
            self.status_bar.showMessage("No tab open", 2000)
            return

        index = self.conversation_tabs.get_tab_index(current_id)
        if index < 0:
            return

        tab_widget = self.conversation_tabs.widget(index)
        if hasattr(tab_widget, 'get_content'):
            content = tab_widget.get_content()
            if content.strip():
                QApplication.clipboard().setText(content)
                self.status_bar.showMessage("Copied to clipboard", 2000)
            else:
                self.status_bar.showMessage("No content to copy", 2000)
        else:
            self.status_bar.showMessage("No content to copy", 2000)

    # ── Dialogs ──────────────────────────────────

    def _reset_stats(self):
        self.session_stats = {
            'requests': 0, 'local': 0, 'cloud': 0,
            'tokens_in': 0, 'tokens_out': 0, 'cost': 0.0
        }

    def _show_shortcuts(self):
        shortcuts = [
            ("Ctrl+N", "New conversation"),
            ("Ctrl+Enter", "Execute query"),
            ("Escape", "Stop execution"),
            ("Ctrl+M", "Cycle model"),
            ("Ctrl+W", "Close current tab"),
            ("Ctrl+Tab", "Next tab"),
            ("Ctrl+Shift+Tab", "Previous tab"),
            ("Ctrl+B", "Toggle sidebar"),
            ("Ctrl+T", "Toggle tabs"),
            ("Ctrl+O", "Open file"),
            ("Ctrl+L", "Clear input"),
            ("Ctrl+Shift+C", "Copy output"),
            ("Ctrl+,", "Settings"),
            ("F1", "This help"),
        ]
        text = "\n".join(f"  {k:<20}{v}" for k, v in shortcuts)
        QMessageBox.information(self, "Keyboard Shortcuts", text)

    def _show_about(self):
        QMessageBox.about(self, "About", """
            <h2 style='color:#818cf8'>LLM Smart Router Pro v3.0</h2>
            <p>Intelligent routing between Local LLM and Claude API</p>
            <p><b>Author:</b> クラ for 新さん</p>
            <br>
            <p style='color:#64748b'>Built with PySide6 + Node.js</p>
        """)


# ============================================================
# Entry Point
# ============================================================

def main():
    setup_gui_logging()  # ログローテーション設定
    app = QApplication(sys.argv)
    DarkTheme.apply(app)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
