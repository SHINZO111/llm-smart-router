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
import yaml
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QComboBox, QLabel, QLineEdit,
    QGroupBox, QSplitter, QStatusBar, QMenuBar, QMenu,
    QMessageBox, QFileDialog, QProgressBar, QTabWidget,
    QFrame, QScrollArea, QGridLayout, QSpinBox, QDoubleSpinBox,
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QPlainTextEdit, QGraphicsDropShadowEffect,
    QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, QThread, Signal, Slot, QTimer, QSize, QSettings,
    QPropertyAnimation, QEasingCurve, Property, QRect,
    QParallelAnimationGroup, QSequentialAnimationGroup, QAbstractAnimation
)
from PySide6.QtGui import (
    QAction, QIcon, QFont, QPalette, QColor, QKeySequence,
    QShortcut, QFontDatabase, QPainter, QLinearGradient,
    QBrush, QPen, QRadialGradient, QPainterPath
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from security.key_manager import SecureKeyManager
from gui.dashboard import StatisticsDashboard
from gui.settings_dialog import SettingsDialog


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
    TEXT_DIM = '#94a3b8'
    TEXT_MUTED = '#64748b'

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
# LLM Worker Thread
# ============================================================

class LLMWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, router_path, input_text, model_type=None, config=None):
        super().__init__()
        self.router_path = router_path
        self.input_text = input_text
        self.model_type = model_type
        self.config = config or {}
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
        try:
            self.progress.emit("Preparing request...")
            cmd = ['node', os.path.join(self.router_path, 'openclaw-integration.js')]
            if self.model_type:
                cmd.append(self.model_type)
            cmd.append(self.input_text)

            env = os.environ.copy()
            km = SecureKeyManager()
            api_key = km.get_api_key('anthropic')
            if api_key:
                env['ANTHROPIC_API_KEY'] = api_key

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

            QLabel#section_title {{ color: {Colors.PRIMARY_LIGHT}; font-size: 13px; font-weight: 600; }}
            QLabel#status_ok {{ color: {Colors.SECONDARY}; font-weight: 500; }}
            QLabel#status_warn {{ color: {Colors.ACCENT}; font-weight: 500; }}
            QLabel#counter {{ color: {Colors.TEXT_MUTED}; font-size: 11px; }}
        """)


# ============================================================
# Main Window
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Smart Router Pro")
        self.setMinimumSize(1440, 900)
        self.settings = QSettings('LLMSmartRouter', 'Pro')
        self.router_path = self.settings.value(
            'router_path', str(Path(__file__).parent.parent.parent))
        self.worker = None
        self.session_stats = {
            'requests': 0, 'local': 0, 'cloud': 0,
            'tokens_in': 0, 'tokens_out': 0, 'cost': 0.0
        }
        self._init_ui()
        self._init_menu()
        self._init_shortcuts()
        self._init_timers()
        QTimer.singleShot(500, self.check_api_key)

    # ── UI Setup ─────────────────────────────────

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        root.addWidget(splitter)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([360, 640, 380])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(180)
        self.progress.setFixedHeight(8)
        self.progress.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress)

        self._mem_label = QLabel()
        self._mem_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        self.status_bar.addPermanentWidget(self._mem_label)

        self.status_bar.showMessage("Ready")

    def _build_left_panel(self):
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {Colors.BG_MAIN};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 16, 8, 16)
        lay.setSpacing(10)

        # ── Header ──
        header = QLabel("LLM Smart Router")
        header.setStyleSheet(
            f"color: {Colors.PRIMARY_LIGHT}; font-size: 18px; font-weight: 800;"
            f" letter-spacing: -0.5px; padding: 4px 0 8px 0;"
        )
        lay.addWidget(header)

        # ── Model Selector ──
        mg = QGroupBox("Model")
        ml = QVBoxLayout(mg)
        self.model_combo = QComboBox()
        self.model_combo.addItem("  Auto (Recommended)", "auto")
        self.model_combo.addItem("  Local LLM", "local")
        self.model_combo.addItem("  Claude API", "claude")
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        ml.addWidget(self.model_combo)

        status_row = QHBoxLayout()
        self._status_dot = StatusDot(Colors.SECONDARY)
        status_row.addWidget(self._status_dot)
        self.model_status = QLabel("Auto routing active")
        self.model_status.setObjectName("status_ok")
        status_row.addWidget(self.model_status)
        status_row.addStretch()
        ml.addLayout(status_row)
        lay.addWidget(mg)

        # ── Preset Selector ──
        pg = QGroupBox("Preset")
        pl = QVBoxLayout(pg)
        self.preset_combo = QComboBox()
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

        # ── Input ──
        ig = QGroupBox("Input")
        il = QVBoxLayout(ig)
        self.input_text = QPlainTextEdit()
        self.input_text.setPlaceholderText(
            "Type your question or task here...\n\n"
            "Examples:\n"
            "  - Review this construction cost estimate\n"
            "  - Optimize my streaming schedule\n"
            "  - Debug this Python code"
        )
        self.input_text.setMinimumHeight(120)
        self.input_text.setMaximumHeight(220)
        self.input_text.textChanged.connect(self._update_counter)
        il.addWidget(self.input_text)

        counter_row = QHBoxLayout()
        self._char_counter = QLabel("0 chars")
        self._char_counter.setObjectName("counter")
        counter_row.addWidget(self._char_counter)
        counter_row.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self.input_text.clear)
        counter_row.addWidget(clear_btn)

        paste_btn = QPushButton("Paste")
        paste_btn.setFixedHeight(28)
        paste_btn.clicked.connect(self._paste)
        counter_row.addWidget(paste_btn)

        load_btn = QPushButton("File")
        load_btn.setFixedHeight(28)
        load_btn.clicked.connect(self.load_file)
        counter_row.addWidget(load_btn)
        il.addLayout(counter_row)
        lay.addWidget(ig)

        # ── System Prompt ──
        sg = QGroupBox("System Prompt (optional)")
        sl = QVBoxLayout(sg)
        self.system_prompt = QPlainTextEdit()
        self.system_prompt.setPlaceholderText("Custom role or constraints...")
        self.system_prompt.setMaximumHeight(80)
        sl.addWidget(self.system_prompt)
        lay.addWidget(sg)

        # ── Execute ──
        self.execute_btn = PulseButton("  Execute  (Ctrl+Enter)")
        self.execute_btn.setObjectName("exec_btn")
        self.execute_btn.setMinimumHeight(52)
        self.execute_btn.setCursor(Qt.PointingHandCursor)
        self.execute_btn.clicked.connect(self.execute)
        lay.addWidget(self.execute_btn)

        self.stop_btn = QPushButton("  Stop  (Esc)")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.setMinimumHeight(52)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self.stop_execution)
        self.stop_btn.setVisible(False)
        lay.addWidget(self.stop_btn)

        lay.addStretch()
        return panel

    def _build_center_panel(self):
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {Colors.BG_DARK};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 16, 8, 16)
        lay.setSpacing(10)

        # ── Output Tabs ──
        self.output_tabs = QTabWidget()

        out_w = QWidget()
        out_l = QVBoxLayout(out_w)
        out_l.setContentsMargins(0, 8, 0, 0)
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("Response will appear here...")
        out_l.addWidget(self.output_text)

        btn_row = QHBoxLayout()
        for text, handler in [("Copy", self.copy_output), ("Save", self.save_output),
                              ("Clear", lambda: self.output_text.clear())]:
            b = QPushButton(text)
            b.setFixedHeight(30)
            b.clicked.connect(handler)
            btn_row.addWidget(b)
        btn_row.addStretch()
        out_l.addLayout(btn_row)
        self.output_tabs.addTab(out_w, "Output")

        log_w = QWidget()
        log_l = QVBoxLayout(log_w)
        log_l.setContentsMargins(0, 8, 0, 0)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Detailed logs appear here...")
        self.log_text.setStyleSheet(
            f"font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px;"
        )
        log_l.addWidget(self.log_text)
        self.output_tabs.addTab(log_w, "Logs")

        lay.addWidget(self.output_tabs)

        # ── Metadata Bar ──
        meta = QFrame()
        meta.setStyleSheet(f"""
            QFrame {{ background-color: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER};
                      border-radius: 8px; padding: 8px; }}
        """)
        meta_l = QHBoxLayout(meta)
        meta_l.setContentsMargins(12, 6, 12, 6)
        self.meta_model = QLabel("Model: --")
        self.meta_time = QLabel("Time: --")
        self.meta_tokens = QLabel("Tokens: --")
        self.meta_cost = QLabel("Cost: --")
        for lbl in [self.meta_model, self.meta_time, self.meta_tokens, self.meta_cost]:
            lbl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 12px; border: none;")
            meta_l.addWidget(lbl)
        meta_l.addStretch()
        lay.addWidget(meta)
        return panel

    def _build_right_panel(self):
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {Colors.BG_MAIN};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 16, 16, 16)
        lay.setSpacing(10)

        # ── Stats Cards ──
        title = QLabel("Dashboard")
        title.setStyleSheet(
            f"color: {Colors.PRIMARY_LIGHT}; font-size: 16px; font-weight: 700;"
            f" padding-bottom: 4px;"
        )
        lay.addWidget(title)

        cards = QHBoxLayout()
        cards.setSpacing(8)
        self.card_requests = StatCard("", "Requests", "0", Colors.PRIMARY)
        self.card_saved = StatCard("", "Saved", "¥0", Colors.SECONDARY)
        cards.addWidget(self.card_requests)
        cards.addWidget(self.card_saved)
        lay.addLayout(cards)

        # ── Dashboard ──
        self.dashboard = StatisticsDashboard()
        lay.addWidget(self.dashboard)

        # ── Session Stats ──
        sg = QGroupBox("Session")
        sgl = QGridLayout(sg)
        sgl.setSpacing(8)
        self.stat_requests = QLabel("Requests: 0")
        self.stat_local = QLabel("Local: 0")
        self.stat_cloud = QLabel("Cloud: 0")
        self.stat_cost = QLabel("Cost: ¥0")
        for i, (lbl, clr) in enumerate([
            (self.stat_requests, Colors.TEXT_DIM),
            (self.stat_local, Colors.SECONDARY),
            (self.stat_cloud, Colors.CYAN),
            (self.stat_cost, Colors.ACCENT)
        ]):
            lbl.setStyleSheet(f"color: {clr}; font-size: 12px;")
            sgl.addWidget(lbl, i // 2, i % 2)
        lay.addWidget(sg)

        # ── History ──
        hg = QGroupBox("History")
        hl = QVBoxLayout(hg)
        self.history_list = QTableWidget()
        self.history_list.setColumnCount(4)
        self.history_list.setHorizontalHeaderLabels(["Time", "Model", "Tokens", "Cost"])
        self.history_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_list.setMaximumHeight(180)
        self.history_list.verticalHeader().setVisible(False)
        self.history_list.setShowGrid(False)
        self.history_list.setAlternatingRowColors(True)
        hl.addWidget(self.history_list)
        lay.addWidget(hg)

        lay.addStretch()
        return panel

    # ── Menu ─────────────────────────────────────

    def _init_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("File")
        self._add_action(fm, "Open File...", self.load_file, QKeySequence.Open)
        self._add_action(fm, "Save Output...", self.save_output, QKeySequence.Save)
        fm.addSeparator()
        self._add_action(fm, "Exit", self.close, QKeySequence.Quit)

        em = mb.addMenu("Edit")
        self._add_action(em, "Clear Input", self.input_text.clear, "Ctrl+L")
        self._add_action(em, "Copy Output", self.copy_output, "Ctrl+Shift+C")

        vm = mb.addMenu("View")
        self._add_action(vm, "Dashboard", self._show_full_stats, "Ctrl+D")

        sm = mb.addMenu("Settings")
        self._add_action(sm, "API Keys...", self.open_settings, "Ctrl+,")
        self._add_action(sm, "Router Config...", self._open_config)

        tm = mb.addMenu("Tools")
        self._add_action(tm, "Statistics", self._show_full_stats)
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

    def _on_model_changed(self, idx):
        m = self.model_combo.currentData()
        if m == "auto":
            self.model_status.setText("Auto routing active")
            self._status_dot.set_color(Colors.SECONDARY)
        elif m == "local":
            self.model_status.setText("Local LLM only")
            self._status_dot.set_color(Colors.ACCENT)
        else:
            self.model_status.setText("Claude API only")
            self._status_dot.set_color(Colors.CYAN)

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

    # ── Execution ────────────────────────────────

    def execute(self):
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Error", "Input is empty")
            return

        pid = self.preset_combo.currentData()
        if not pid:
            detected = PresetManager.detect_preset(text)
            if detected:
                p = PresetManager.get_preset(detected)
                self.log_text.appendPlainText(f"[Preset] Auto: {p['name']}")

        model = self.model_combo.currentData()

        self.execute_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_bar.showMessage("Processing...")
        self.output_text.clear()
        self.execute_btn.start_pulse()

        self.worker = LLMWorker(
            self.router_path, text,
            None if model == "auto" else model,
            config={'timeout': 120}
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
        self.output_text.setPlainText(result['response'])
        dur = result.get('duration', 0)
        self.meta_model.setText(f"Model: {result['model']}")
        self.meta_time.setText(f"Time: {dur:.1f}s")
        self.log_text.appendPlainText(f"[Done] {result['model']} in {dur:.1f}s")
        self._update_stats(result)
        self._add_history(result)
        self._reset_ui()

    def _on_error(self, msg):
        self.output_text.setPlainText(f"Error:\n{msg}")
        self.log_text.appendPlainText(f"[Error] {msg}")
        self._reset_ui()

    def _on_progress(self, msg):
        self.status_bar.showMessage(msg)
        self.log_text.appendPlainText(f"[...] {msg}")

    def _reset_ui(self):
        self.execute_btn.stop_pulse()
        self.execute_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.progress.setVisible(False)
        self.status_bar.showMessage("Ready")

    def _update_stats(self, result):
        self.session_stats['requests'] += 1
        if result.get('model') == 'local':
            self.session_stats['local'] += 1
        else:
            self.session_stats['cloud'] += 1

        s = self.session_stats
        self.stat_requests.setText(f"Requests: {s['requests']}")
        self.stat_local.setText(f"Local: {s['local']}")
        self.stat_cloud.setText(f"Cloud: {s['cloud']}")
        self.card_requests.set_value(str(s['requests']))
        self.card_saved.set_value(f"¥{s['local'] * 5}")
        self.dashboard.update_stats(s)

    def _add_history(self, result):
        t = self.history_list
        row = t.rowCount()
        t.insertRow(row)
        t.setItem(row, 0, QTableWidgetItem(datetime.now().strftime("%H:%M:%S")))
        t.setItem(row, 1, QTableWidgetItem(result.get('model', '-')))
        t.setItem(row, 2, QTableWidgetItem("-"))
        t.setItem(row, 3, QTableWidgetItem("¥0"))
        t.scrollToBottom()

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
        QApplication.clipboard().setText(self.output_text.toPlainText())
        self.status_bar.showMessage("Copied to clipboard", 2000)

    def save_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save",
            f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text (*.txt);;Markdown (*.md)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.toPlainText())
                self.status_bar.showMessage(f"Saved: {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ── Dialogs ──────────────────────────────────

    def _show_full_stats(self):
        self.dashboard.show_full_dialog()

    def _reset_stats(self):
        self.session_stats = {
            'requests': 0, 'local': 0, 'cloud': 0,
            'tokens_in': 0, 'tokens_out': 0, 'cost': 0.0
        }
        for lbl in [self.stat_requests, self.stat_local, self.stat_cloud, self.stat_cost]:
            lbl.setText(lbl.text().split(":")[0] + ": 0")
        self.card_requests.set_value("0")
        self.card_saved.set_value("¥0")
        self.dashboard.reset()
        self.history_list.setRowCount(0)

    def _show_shortcuts(self):
        shortcuts = [
            ("Ctrl+Enter", "Execute query"),
            ("Escape", "Stop execution"),
            ("Ctrl+M", "Cycle model"),
            ("Ctrl+O", "Open file"),
            ("Ctrl+S", "Save output"),
            ("Ctrl+L", "Clear input"),
            ("Ctrl+Shift+C", "Copy output"),
            ("Ctrl+,", "Settings"),
            ("Ctrl+D", "Dashboard"),
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
    app = QApplication(sys.argv)
    DarkTheme.apply(app)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
