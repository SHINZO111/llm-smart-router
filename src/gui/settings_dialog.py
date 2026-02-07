#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
設定ダイアログ (v2)

サイドナビゲーション + 4セクション構成。
config.yaml / .env / data/*.json への直接読み書きに対応。
"""

import os
import sys
import json
import logging
import threading
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox, QGroupBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QTextEdit, QFileDialog,
    QComboBox, QProgressBar, QListWidget, QListWidgetItem,
    QAbstractItemView, QStackedWidget, QScrollArea, QFrame,
    QSizePolicy, QInputDialog
)
from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QFont

sys.path.insert(0, str(Path(__file__).parent.parent))

from security.key_manager import SecureKeyManager
from gui.design_tokens import Colors, Spacing, Radius, Typography, L10n
from gui.components import (
    SectionHeader, StatusIndicator, ConfigSourceBadge, ConfigField,
    ActionButton, CardWidget, NavListItem
)
from gui.config_manager import ConfigManager


class SettingsDialog(QDialog):
    """設定ダイアログ — サイドナビ + config.yaml 連携"""

    settings_changed = Signal()  # 保存完了時に発火

    # ナビセクション定義
    SECTIONS = [
        ("connection", "🔐", L10n.SECTION_CONNECTION),
        ("runtime", "🚀", L10n.SECTION_RUNTIME),
        ("routing", "🔀", L10n.SECTION_ROUTING),
        ("advanced", "⚙️", L10n.SECTION_ADVANCED),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"⚙️ {L10n.SETTINGS_TITLE}")
        self.setMinimumSize(820, 580)
        self.resize(900, 650)

        self.key_manager = SecureKeyManager()
        self.settings = QSettings('LLMSmartRouter', 'Pro')
        self.config = ConfigManager()

        self._nav_items: list[NavListItem] = []
        self._init_ui()
        self._load_all()

    # ════════════════════════════════════════════
    # UIレイアウト
    # ════════════════════════════════════════════

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # メインコンテンツ (ナビ + ページ)
        body = QHBoxLayout()
        body.setSpacing(0)

        # 左: ナビゲーション
        nav_panel = QWidget()
        nav_panel.setFixedWidth(180)
        nav_panel.setStyleSheet(
            f"background-color: {Colors.SURFACE_2};"
            f" border-right: 1px solid {Colors.BORDER};"
        )
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(Spacing.SM, Spacing.LG, Spacing.SM, Spacing.SM)
        nav_layout.setSpacing(Spacing.XS)

        # ナビタイトル
        nav_title = QLabel(f"⚙️ {L10n.SETTINGS_TITLE}")
        nav_title.setStyleSheet(
            f"color: {Colors.TEXT};"
            f" font-size: {Typography.SIZE_LG}px;"
            f" font-weight: {Typography.WEIGHT_BOLD};"
            f" padding: {Spacing.SM}px {Spacing.MD}px {Spacing.LG}px;"
        )
        nav_layout.addWidget(nav_title)

        # ナビアイテム
        for section_id, icon, label in self.SECTIONS:
            item = NavListItem(icon, label)
            item.clicked.connect(lambda sid=section_id: self._navigate_to(sid))
            nav_layout.addWidget(item)
            self._nav_items.append(item)

        nav_layout.addStretch()
        body.addWidget(nav_panel)

        # 右: スタックドページ
        self.page_stack = QStackedWidget()
        self.page_stack.setStyleSheet(f"background-color: {Colors.SURFACE_1};")

        self.page_stack.addWidget(self._create_connection_page())
        self.page_stack.addWidget(self._create_runtime_page())
        self.page_stack.addWidget(self._create_routing_page())
        self.page_stack.addWidget(self._create_advanced_page())

        body.addWidget(self.page_stack)
        root.addLayout(body)

        # 下部: ボタンバー
        btn_bar = QWidget()
        btn_bar.setStyleSheet(
            f"background-color: {Colors.SURFACE_2};"
            f" border-top: 1px solid {Colors.BORDER};"
        )
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)

        btn_layout.addStretch()

        cancel_btn = ActionButton(L10n.SETTINGS_CANCEL, variant="ghost")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._save_btn = ActionButton(L10n.SETTINGS_SAVE, variant="primary")
        self._save_btn.clicked.connect(self._save_all)
        btn_layout.addWidget(self._save_btn)

        root.addWidget(btn_bar)

        # 初期選択
        self._navigate_to("connection")

    def _navigate_to(self, section_id: str):
        """ナビゲーション切り替え"""
        for i, (sid, _, _) in enumerate(self.SECTIONS):
            self._nav_items[i].set_selected(sid == section_id)
            if sid == section_id:
                self.page_stack.setCurrentIndex(i)

    def _make_scroll_page(self, content_widget: QWidget) -> QScrollArea:
        """スクロール可能なページラッパーを作成"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {Colors.SURFACE_1}; border: none; }}"
            f" QScrollBar:vertical {{ background: {Colors.SURFACE_2}; width: 8px; }}"
            f" QScrollBar::handle:vertical {{ background: {Colors.BORDER}; border-radius: 4px; }}"
        )
        scroll.setWidget(content_widget)
        return scroll

    # ════════════════════════════════════════════
    # セクション1: 接続・認証
    # ════════════════════════════════════════════

    def _create_connection_page(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(SectionHeader(
            L10n.SECTION_CONNECTION,
            "APIキーとエンドポイントの接続設定"
        ))

        # ── Anthropic ──
        anthropic_card = CardWidget("Anthropic (Claude)", Colors.CYAN)
        cl = anthropic_card.content_layout()

        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.Password)
        self.anthropic_key.setPlaceholderText("sk-ant-api03-...")
        cl.addWidget(ConfigField(
            "APIキー", self.anthropic_key,
            source=ConfigSourceBadge.KEYSTORE,
            tooltip="Anthropic APIキーを入力（OSキーストアに暗号化保存）"
        ))

        anthropic_btns = QHBoxLayout()
        self.show_key_btn = QPushButton(f"👁️ {L10n.API_KEY_SHOW}")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_anthropic_visibility)
        anthropic_btns.addWidget(self.show_key_btn)

        self.test_key_btn = QPushButton(f"🧪 {L10n.API_KEY_TEST}")
        self.test_key_btn.clicked.connect(self._test_anthropic_key)
        anthropic_btns.addWidget(self.test_key_btn)

        self.delete_key_btn = QPushButton(f"🗑️ {L10n.API_KEY_DELETE}")
        self.delete_key_btn.clicked.connect(self._delete_anthropic_key)
        anthropic_btns.addWidget(self.delete_key_btn)

        anthropic_btns.addStretch()
        cl.addLayout(anthropic_btns)
        layout.addWidget(anthropic_card)

        # ── OpenAI ──
        openai_card = CardWidget("OpenAI (GPT-4o)", Colors.SECONDARY)
        ol = openai_card.content_layout()

        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.Password)
        self.openai_key.setPlaceholderText("sk-...")
        ol.addWidget(ConfigField(
            "APIキー", self.openai_key,
            source=ConfigSourceBadge.KEYSTORE,
            tooltip="OpenAI APIキーを入力"
        ))

        openai_btns = QHBoxLayout()
        self.openai_show_btn = QPushButton(f"👁️ {L10n.API_KEY_SHOW}")
        self.openai_show_btn.setCheckable(True)
        self.openai_show_btn.toggled.connect(
            lambda checked: self.openai_key.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        openai_btns.addWidget(self.openai_show_btn)

        self.openai_test_btn = QPushButton(f"🧪 {L10n.API_KEY_TEST}")
        self.openai_test_btn.clicked.connect(lambda: self._test_generic_key("openai"))
        openai_btns.addWidget(self.openai_test_btn)

        openai_btns.addStretch()
        ol.addLayout(openai_btns)
        layout.addWidget(openai_card)

        # ── Google ──
        google_card = CardWidget("Google (Gemini)", Colors.ACCENT)
        gl = google_card.content_layout()

        self.google_key = QLineEdit()
        self.google_key.setEchoMode(QLineEdit.Password)
        self.google_key.setPlaceholderText("AIza...")
        gl.addWidget(ConfigField(
            "APIキー", self.google_key,
            source=ConfigSourceBadge.KEYSTORE,
            tooltip="Google APIキーを入力"
        ))

        google_btns = QHBoxLayout()
        self.google_show_btn = QPushButton(f"👁️ {L10n.API_KEY_SHOW}")
        self.google_show_btn.setCheckable(True)
        self.google_show_btn.toggled.connect(
            lambda checked: self.google_key.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        google_btns.addWidget(self.google_show_btn)
        google_btns.addStretch()
        gl.addLayout(google_btns)
        layout.addWidget(google_card)

        # ── OpenRouter ──
        openrouter_card = CardWidget("OpenRouter (Kimi)", Colors.PRIMARY)
        rl = openrouter_card.content_layout()

        self.openrouter_key = QLineEdit()
        self.openrouter_key.setEchoMode(QLineEdit.Password)
        self.openrouter_key.setPlaceholderText("sk-or-...")
        rl.addWidget(ConfigField(
            "APIキー", self.openrouter_key,
            source=ConfigSourceBadge.KEYSTORE,
            tooltip="OpenRouter APIキーを入力"
        ))

        openrouter_btns = QHBoxLayout()
        self.openrouter_show_btn = QPushButton(f"👁️ {L10n.API_KEY_SHOW}")
        self.openrouter_show_btn.setCheckable(True)
        self.openrouter_show_btn.toggled.connect(
            lambda checked: self.openrouter_key.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        openrouter_btns.addWidget(self.openrouter_show_btn)
        openrouter_btns.addStretch()
        rl.addLayout(openrouter_btns)
        layout.addWidget(openrouter_card)

        # ── セキュリティ情報 ──
        sec_card = CardWidget("セキュリティ情報", Colors.TEXT_MUTED)
        sl = sec_card.content_layout()
        self.keyring_status = QLabel("確認中...")
        self.keyring_status.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: {Typography.SIZE_SM}px;")
        sl.addWidget(self.keyring_status)
        self.backend_label = QLabel("-")
        self.backend_label.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: {Typography.SIZE_SM}px;")
        sl.addWidget(self.backend_label)
        layout.addWidget(sec_card)

        layout.addStretch()
        return self._make_scroll_page(page)

    # ════════════════════════════════════════════
    # セクション2: ランタイム管理
    # ════════════════════════════════════════════

    def _create_runtime_page(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(SectionHeader(
            L10n.SECTION_RUNTIME,
            "ローカルLLMランタイムの起動・停止とモデル管理"
        ))

        # ── LM Studio ──
        lmstudio_card = CardWidget(L10n.LMSTUDIO_TITLE, Colors.ACCENT)
        lsl = lmstudio_card.content_layout()

        # ステータス行
        ls_status_row = QHBoxLayout()
        self.lmstudio_status = StatusIndicator(Colors.STATUS_UNKNOWN, "未確認")
        ls_status_row.addWidget(self.lmstudio_status)
        ls_status_row.addStretch()
        lsl.addLayout(ls_status_row)

        self.lmstudio_enabled = QCheckBox(L10n.RUNTIME_ENABLED)
        self.lmstudio_enabled.setChecked(True)
        lsl.addWidget(ConfigField(
            "", self.lmstudio_enabled,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="オーケストレーター起動時にLM Studioを自動起動するか"
        ))

        self.lmstudio_endpoint = QLineEdit()
        self.lmstudio_endpoint.setText("http://localhost:1234/v1")
        lsl.addWidget(ConfigField(
            L10n.ENDPOINT_LABEL, self.lmstudio_endpoint,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="LM Studio APIのエンドポイントURL"
        ))

        self.lmstudio_timeout = QDoubleSpinBox()
        self.lmstudio_timeout.setRange(10.0, 300.0)
        self.lmstudio_timeout.setSuffix(" 秒")
        self.lmstudio_timeout.setValue(60.0)
        lsl.addWidget(ConfigField(
            "タイムアウト", self.lmstudio_timeout,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="API応答待ちタイムアウト（秒）"
        ))

        self.lmstudio_retry = QSpinBox()
        self.lmstudio_retry.setRange(0, 10)
        self.lmstudio_retry.setValue(2)
        lsl.addWidget(ConfigField(
            "リトライ回数", self.lmstudio_retry,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="接続失敗時のリトライ回数"
        ))

        self.lmstudio_model_detect = QCheckBox("モデル自動検出")
        self.lmstudio_model_detect.setChecked(True)
        lsl.addWidget(ConfigField(
            "", self.lmstudio_model_detect,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="起動時にLM Studioのモデルを自動検出するか"
        ))

        self.lmstudio_model_detect_timeout = QDoubleSpinBox()
        self.lmstudio_model_detect_timeout.setRange(5.0, 120.0)
        self.lmstudio_model_detect_timeout.setSuffix(" 秒")
        self.lmstudio_model_detect_timeout.setValue(30.0)
        lsl.addWidget(ConfigField(
            "検出タイムアウト", self.lmstudio_model_detect_timeout,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="モデル自動検出のタイムアウト（秒）"
        ))

        lmstudio_btns = QHBoxLayout()
        self.lmstudio_start_btn = ActionButton(f"▶ {L10n.RUNTIME_START}", variant="success")
        self.lmstudio_start_btn.clicked.connect(self._lmstudio_start)
        lmstudio_btns.addWidget(self.lmstudio_start_btn)

        self.lmstudio_stop_btn = ActionButton(f"■ {L10n.RUNTIME_STOP}", variant="danger")
        self.lmstudio_stop_btn.clicked.connect(self._lmstudio_stop)
        lmstudio_btns.addWidget(self.lmstudio_stop_btn)

        lmstudio_check = ActionButton(f"🔍 {L10n.RUNTIME_CHECK}", variant="ghost")
        lmstudio_check.clicked.connect(self._lmstudio_check_status)
        lmstudio_btns.addWidget(lmstudio_check)
        lmstudio_btns.addStretch()
        lsl.addLayout(lmstudio_btns)

        layout.addWidget(lmstudio_card)

        # ── Ollama ──
        ollama_card = CardWidget("Ollama", Colors.SECONDARY)
        ol = ollama_card.content_layout()

        # ステータス行
        status_row = QHBoxLayout()
        self.ollama_status = StatusIndicator(Colors.STATUS_UNKNOWN, "未確認")
        status_row.addWidget(self.ollama_status)
        status_row.addStretch()
        ol.addLayout(status_row)

        self.ollama_enabled = QCheckBox(L10n.RUNTIME_ENABLED)
        self.ollama_enabled.setChecked(False)
        ol.addWidget(ConfigField(
            "", self.ollama_enabled,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="オーケストレーター起動時にOllamaを自動起動するか"
        ))

        self.ollama_endpoint = QLineEdit()
        self.ollama_endpoint.setText("http://localhost:11434")
        ol.addWidget(ConfigField(
            L10n.ENDPOINT_LABEL, self.ollama_endpoint,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="Ollama APIのエンドポイントURL"
        ))

        self.ollama_timeout = QDoubleSpinBox()
        self.ollama_timeout.setRange(5.0, 120.0)
        self.ollama_timeout.setSuffix(" 秒")
        self.ollama_timeout.setValue(30.0)
        ol.addWidget(ConfigField(
            "タイムアウト", self.ollama_timeout,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="API応答待ちタイムアウト（秒）"
        ))

        ollama_btns = QHBoxLayout()
        self.ollama_start_btn = ActionButton(f"▶ {L10n.RUNTIME_START}", variant="success")
        self.ollama_start_btn.clicked.connect(self._ollama_start)
        ollama_btns.addWidget(self.ollama_start_btn)

        self.ollama_stop_btn = ActionButton(f"■ {L10n.RUNTIME_STOP}", variant="danger")
        self.ollama_stop_btn.clicked.connect(self._ollama_stop)
        ollama_btns.addWidget(self.ollama_stop_btn)

        ollama_check_btn = ActionButton(f"🔍 {L10n.RUNTIME_CHECK}", variant="ghost")
        ollama_check_btn.clicked.connect(self._ollama_check_status)
        ollama_btns.addWidget(ollama_check_btn)
        ollama_btns.addStretch()
        ol.addLayout(ollama_btns)

        # モデル一覧
        models_label = QLabel(L10n.RUNTIME_MODELS)
        models_label.setStyleSheet(
            f"color: {Colors.TEXT_DIM}; font-weight: bold; margin-top: {Spacing.SM}px;"
        )
        ol.addWidget(models_label)

        self.ollama_model_list = QListWidget()
        self.ollama_model_list.setMaximumHeight(120)
        self.ollama_model_list.setStyleSheet(
            f"QListWidget {{ background: {Colors.SURFACE_0}; color: {Colors.TEXT};"
            f" border: 1px solid {Colors.BORDER}; border-radius: {Radius.MD}px;"
            f" font-size: {Typography.SIZE_SM}px; padding: 4px; }}"
            f" QListWidget::item {{ padding: 4px 8px; }}"
            f" QListWidget::item:selected {{ background: {Colors.SURFACE_4}; }}"
        )
        ol.addWidget(self.ollama_model_list)

        model_btns = QHBoxLayout()
        ollama_refresh = ActionButton(f"🔄 {L10n.OLLAMA_REFRESH}", variant="ghost")
        ollama_refresh.clicked.connect(self._ollama_refresh_models)
        model_btns.addWidget(ollama_refresh)

        self.ollama_pull_btn = ActionButton(f"📥 {L10n.OLLAMA_PULL}", variant="ghost")
        self.ollama_pull_btn.clicked.connect(self._ollama_pull_model)
        model_btns.addWidget(self.ollama_pull_btn)

        ollama_delete = ActionButton(f"🗑️ {L10n.OLLAMA_DELETE}", variant="ghost")
        ollama_delete.clicked.connect(self._ollama_delete_model)
        model_btns.addWidget(ollama_delete)
        model_btns.addStretch()
        ol.addLayout(model_btns)

        self.ollama_progress = QProgressBar()
        self.ollama_progress.setVisible(False)
        self.ollama_progress.setTextVisible(True)
        ol.addWidget(self.ollama_progress)

        layout.addWidget(ollama_card)

        # ── llama.cpp ──
        llamacpp_card = CardWidget("llama.cpp", Colors.ACCENT)
        ll = llamacpp_card.content_layout()

        status_row2 = QHBoxLayout()
        self.llamacpp_status = StatusIndicator(Colors.STATUS_UNKNOWN, "未確認")
        status_row2.addWidget(self.llamacpp_status)
        status_row2.addStretch()
        ll.addLayout(status_row2)

        self.llamacpp_enabled = QCheckBox(L10n.RUNTIME_ENABLED)
        self.llamacpp_enabled.setChecked(False)
        ll.addWidget(ConfigField(
            "", self.llamacpp_enabled,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="オーケストレーター起動時にllama.cppを自動起動するか"
        ))

        self.llamacpp_endpoint = QLineEdit()
        self.llamacpp_endpoint.setText("http://localhost:8080")
        ll.addWidget(ConfigField(
            L10n.ENDPOINT_LABEL, self.llamacpp_endpoint,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="llama.cpp APIのエンドポイントURL"
        ))

        self.llamacpp_timeout = QDoubleSpinBox()
        self.llamacpp_timeout.setRange(5.0, 120.0)
        self.llamacpp_timeout.setSuffix(" 秒")
        self.llamacpp_timeout.setValue(30.0)
        ll.addWidget(ConfigField(
            "タイムアウト", self.llamacpp_timeout,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="API応答待ちタイムアウト（秒）"
        ))

        self.llamacpp_model_path = QLineEdit()
        self.llamacpp_model_path.setPlaceholderText("起動時にロードするGGUFファイルのパス")

        model_path_field = QWidget()
        mpl = QHBoxLayout(model_path_field)
        mpl.setContentsMargins(0, 0, 0, 0)
        mpl.addWidget(self.llamacpp_model_path)
        browse_btn = QPushButton("📂")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self._llamacpp_browse_model)
        mpl.addWidget(browse_btn)

        ll.addWidget(ConfigField(
            L10n.LLAMACPP_BROWSE, model_path_field,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        llamacpp_btns = QHBoxLayout()
        self.llamacpp_start_btn = ActionButton(f"▶ {L10n.RUNTIME_START}", variant="success")
        self.llamacpp_start_btn.clicked.connect(self._llamacpp_start)
        llamacpp_btns.addWidget(self.llamacpp_start_btn)

        self.llamacpp_stop_btn = ActionButton(f"■ {L10n.RUNTIME_STOP}", variant="danger")
        self.llamacpp_stop_btn.clicked.connect(self._llamacpp_stop)
        llamacpp_btns.addWidget(self.llamacpp_stop_btn)

        llamacpp_check = ActionButton(f"🔍 {L10n.RUNTIME_CHECK}", variant="ghost")
        llamacpp_check.clicked.connect(self._llamacpp_check_status)
        llamacpp_btns.addWidget(llamacpp_check)
        llamacpp_btns.addStretch()
        ll.addLayout(llamacpp_btns)

        layout.addWidget(llamacpp_card)

        # スキャンボタン
        scan_card = CardWidget(f"🔍 {L10n.RUNTIME_SCAN}", Colors.PRIMARY)
        scl = scan_card.content_layout()
        scan_desc = QLabel("ローカルLLMランタイムのポートスキャンを実行し、利用可能なモデルを検出します")
        scan_desc.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: {Typography.SIZE_SM}px;")
        scan_desc.setWordWrap(True)
        scl.addWidget(scan_desc)
        scan_btn = ActionButton(f"🔍 {L10n.RUNTIME_SCAN}実行", variant="primary")
        scan_btn.clicked.connect(self._run_scan)
        scl.addWidget(scan_btn)
        layout.addWidget(scan_card)

        layout.addStretch()
        return self._make_scroll_page(page)

    # ════════════════════════════════════════════
    # セクション3: ルーティング設定
    # ════════════════════════════════════════════

    def _create_routing_page(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(SectionHeader(
            L10n.SECTION_ROUTING,
            "モデル選択とフォールバックの動作を設定"
        ))

        # ── デフォルトモデル ──
        model_card = CardWidget(L10n.ROUTING_DEFAULT_MODEL, Colors.PRIMARY)
        ml = model_card.content_layout()

        self.default_model = QComboBox()
        self.default_model.addItem("🧠 自動判定", "auto")
        self.default_model.addItem("💻 ローカル", "local")
        self.default_model.addItem("☁️ クラウド", "cloud")
        ml.addWidget(ConfigField(
            L10n.ROUTING_DEFAULT_MODEL, self.default_model,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="新しい会話で使用するデフォルトのモデル。config.yaml の default: に書き込み"
        ))

        layout.addWidget(model_card)

        # ── 確信度閾値 ──
        conf_card = CardWidget(L10n.ROUTING_CONFIDENCE, Colors.SECONDARY)
        cl = conf_card.content_layout()

        self.confidence_threshold = QDoubleSpinBox()
        self.confidence_threshold.setRange(0.0, 1.0)
        self.confidence_threshold.setSingleStep(0.05)
        self.confidence_threshold.setDecimals(2)
        self.confidence_threshold.setValue(0.75)
        cl.addWidget(ConfigField(
            L10n.ROUTING_CONFIDENCE, self.confidence_threshold,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip=L10n.ROUTING_CONFIDENCE_DESC
        ))

        layout.addWidget(conf_card)

        # ── タイムアウト ──
        timeout_card = CardWidget("タイムアウト", Colors.ACCENT)
        tl = timeout_card.content_layout()

        self.local_timeout = QSpinBox()
        self.local_timeout.setRange(10, 300)
        self.local_timeout.setSuffix(" 秒")
        self.local_timeout.setValue(30)
        tl.addWidget(ConfigField(
            L10n.ROUTING_TIMEOUT_LOCAL, self.local_timeout,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        self.cloud_timeout = QSpinBox()
        self.cloud_timeout.setRange(10, 300)
        self.cloud_timeout.setSuffix(" 秒")
        self.cloud_timeout.setValue(60)
        tl.addWidget(ConfigField(
            L10n.ROUTING_TIMEOUT_CLOUD, self.cloud_timeout,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        layout.addWidget(timeout_card)

        # ── コスト通知 ──
        cost_card = CardWidget(L10n.ROUTING_COST_NOTIFY, Colors.DANGER)
        col = cost_card.content_layout()

        self.cost_notify = QCheckBox(L10n.ROUTING_COST_NOTIFY)
        self.cost_notify.setChecked(True)
        col.addWidget(ConfigField(
            "", self.cost_notify,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        self.cost_threshold = QSpinBox()
        self.cost_threshold.setRange(1, 10000)
        self.cost_threshold.setSuffix(" ¥")
        self.cost_threshold.setValue(50)
        col.addWidget(ConfigField(
            L10n.ROUTING_COST_THRESHOLD, self.cost_threshold,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        layout.addWidget(cost_card)

        # ── フォールバック優先順位 ──
        fb_card = CardWidget(L10n.ROUTING_FALLBACK_TITLE, Colors.CYAN)
        fl = fb_card.content_layout()

        fb_desc = QLabel(L10n.ROUTING_FALLBACK_DESC)
        fb_desc.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: {Typography.SIZE_SM}px;")
        fb_desc.setWordWrap(True)
        fl.addWidget(fb_desc)

        list_row = QHBoxLayout()
        self.priority_list = QListWidget()
        self.priority_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.priority_list.setDefaultDropAction(Qt.MoveAction)
        self.priority_list.setStyleSheet(
            f"QListWidget {{ background: {Colors.SURFACE_0}; color: {Colors.TEXT};"
            f" border: 1px solid {Colors.BORDER}; border-radius: {Radius.MD}px;"
            f" font-size: {Typography.SIZE_MD}px; padding: 4px; }}"
            f" QListWidget::item {{ padding: 6px 8px; border-radius: {Radius.SM}px; }}"
            f" QListWidget::item:selected {{ background: {Colors.SURFACE_4}; }}"
        )
        list_row.addWidget(self.priority_list)

        btn_col = QVBoxLayout()
        btn_col.addStretch()
        up_btn = ActionButton("↑ 上へ", variant="ghost")
        up_btn.setFixedWidth(80)
        up_btn.clicked.connect(self._priority_move_up)
        btn_col.addWidget(up_btn)

        down_btn = ActionButton("↓ 下へ", variant="ghost")
        down_btn.setFixedWidth(80)
        down_btn.clicked.connect(self._priority_move_down)
        btn_col.addWidget(down_btn)

        btn_col.addSpacing(Spacing.LG)

        reset_btn = ActionButton(f"🔄 {L10n.SETTINGS_RESET}", variant="ghost")
        reset_btn.setFixedWidth(80)
        reset_btn.clicked.connect(self._priority_reset)
        btn_col.addWidget(reset_btn)
        btn_col.addStretch()
        list_row.addLayout(btn_col)

        fl.addLayout(list_row)

        self.priority_preview = QLabel("")
        self.priority_preview.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}px;"
            f" padding: {Spacing.SM}px;"
        )
        self.priority_preview.setWordWrap(True)
        fl.addWidget(self.priority_preview)
        self.priority_list.model().rowsMoved.connect(self._update_priority_preview)

        # ソースバッジ
        fb_source = ConfigSourceBadge(ConfigSourceBadge.JSON, live=True)
        fl.addWidget(fb_source)

        layout.addWidget(fb_card)

        layout.addStretch()
        return self._make_scroll_page(page)

    # ════════════════════════════════════════════
    # セクション4: 詳細設定
    # ════════════════════════════════════════════

    def _create_advanced_page(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(SectionHeader(
            L10n.SECTION_ADVANCED,
            "キャッシュ、OpenClaw連携、ログ、Discord Bot"
        ))

        # ── キャッシュ設定 ──
        cache_card = CardWidget(L10n.ADVANCED_CACHE, Colors.PRIMARY)
        cl = cache_card.content_layout()

        self.cache_enabled = QCheckBox(L10n.ADVANCED_CACHE_ENABLED)
        self.cache_enabled.setChecked(True)
        cl.addWidget(ConfigField(
            "", self.cache_enabled,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        self.cache_ttl = QSpinBox()
        self.cache_ttl.setRange(60, 86400)
        self.cache_ttl.setSuffix(" 秒")
        self.cache_ttl.setValue(3600)
        cl.addWidget(ConfigField(
            L10n.ADVANCED_CACHE_TTL, self.cache_ttl,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        self.cache_max = QSpinBox()
        self.cache_max.setRange(100, 100000)
        self.cache_max.setValue(10000)
        cl.addWidget(ConfigField(
            L10n.ADVANCED_CACHE_MAX, self.cache_max,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        layout.addWidget(cache_card)

        # ── OpenClaw連携 ──
        oc_card = CardWidget(L10n.ADVANCED_OPENCLAW, Colors.CYAN)
        ol = oc_card.content_layout()

        self.openclaw_enabled = QCheckBox(L10n.OPENCLAW_ENABLED)
        self.openclaw_enabled.setChecked(True)
        ol.addWidget(ConfigField(
            "", self.openclaw_enabled,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="オーケストレーター起動時にOpenClaw検証を実行するか"
        ))

        self.openclaw_timeout = QDoubleSpinBox()
        self.openclaw_timeout.setRange(5.0, 60.0)
        self.openclaw_timeout.setSuffix(" 秒")
        self.openclaw_timeout.setValue(15.0)
        ol.addWidget(ConfigField(
            "タイムアウト", self.openclaw_timeout,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="OpenClaw検証のタイムアウト（秒）"
        ))

        self.openclaw_auto_sync = QCheckBox(L10n.ADVANCED_OPENCLAW_SYNC)
        ol.addWidget(self.openclaw_auto_sync)

        self.openclaw_fallback_sync = QCheckBox(L10n.ADVANCED_OPENCLAW_FALLBACK)
        ol.addWidget(self.openclaw_fallback_sync)

        self.openclaw_config_path = QLineEdit()
        self.openclaw_config_path.setPlaceholderText("自動検出（~/.openclaw/config.json）")
        ol.addWidget(ConfigField(
            L10n.ADVANCED_OPENCLAW_PATH, self.openclaw_config_path,
            source=ConfigSourceBadge.YAML, live=True,
        ))

        oc_btns = QHBoxLayout()
        detect_btn = ActionButton("📂 検出", variant="ghost")
        detect_btn.clicked.connect(self._detect_openclaw_config)
        oc_btns.addWidget(detect_btn)

        sync_btn = ActionButton("🔄 今すぐ同期", variant="primary")
        sync_btn.clicked.connect(self._sync_openclaw_now)
        oc_btns.addWidget(sync_btn)

        create_btn = ActionButton("📝 デフォルト設定作成", variant="ghost")
        create_btn.clicked.connect(self._create_openclaw_config)
        oc_btns.addWidget(create_btn)
        oc_btns.addStretch()
        ol.addLayout(oc_btns)

        self.openclaw_status = QLabel("")
        self.openclaw_status.setStyleSheet(
            f"color: {Colors.TEXT_DIM}; font-size: {Typography.SIZE_SM}px;"
        )
        self.openclaw_status.setWordWrap(True)
        ol.addWidget(self.openclaw_status)

        layout.addWidget(oc_card)

        # ── ログ設定 ──
        log_card = CardWidget(L10n.ADVANCED_LOGGING, Colors.TEXT_MUTED)
        ll = log_card.content_layout()

        self.log_level = QComboBox()
        self.log_level.addItem("debug", "debug")
        self.log_level.addItem("info", "info")
        self.log_level.addItem("warn", "warn")
        self.log_level.addItem("error", "error")
        ll.addWidget(ConfigField(
            L10n.ADVANCED_LOG_LEVEL, self.log_level,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        layout.addWidget(log_card)

        # ── Discord Bot ──
        discord_card = CardWidget(L10n.ADVANCED_DISCORD, Colors.PRIMARY_LIGHT)
        dl = discord_card.content_layout()

        self.discord_enabled = QCheckBox(L10n.ADVANCED_DISCORD_ENABLED)
        dl.addWidget(ConfigField(
            "", self.discord_enabled,
            source=ConfigSourceBadge.YAML, live=False,
        ))

        self.discord_token = QLineEdit()
        self.discord_token.setEchoMode(QLineEdit.Password)
        self.discord_token.setPlaceholderText("Discord Botトークンを入力")
        dl.addWidget(ConfigField(
            L10n.ADVANCED_DISCORD_TOKEN, self.discord_token,
            source=ConfigSourceBadge.ENV, live=False,
            tooltip="discord-bot.js が読む DISCORD_BOT_TOKEN 環境変数"
        ))

        self.discord_prefix = QLineEdit()
        self.discord_prefix.setText("!")
        self.discord_prefix.setMaximumWidth(100)
        dl.addWidget(ConfigField(
            L10n.ADVANCED_DISCORD_PREFIX, self.discord_prefix,
            source=ConfigSourceBadge.ENV, live=False,
            tooltip="Botコマンドのプレフィックス（例: !help）"
        ))

        self.discord_admin_ids = QLineEdit()
        self.discord_admin_ids.setPlaceholderText("123456789,987654321")
        dl.addWidget(ConfigField(
            L10n.ADVANCED_DISCORD_ADMIN_IDS, self.discord_admin_ids,
            source=ConfigSourceBadge.ENV, live=False,
            tooltip="管理コマンド実行可能なDiscordユーザーID（カンマ区切り）"
        ))

        self.discord_rate_limit = QSpinBox()
        self.discord_rate_limit.setRange(500, 60000)
        self.discord_rate_limit.setSuffix(" ms")
        self.discord_rate_limit.setValue(3000)
        dl.addWidget(ConfigField(
            L10n.ADVANCED_DISCORD_RATE_LIMIT, self.discord_rate_limit,
            source=ConfigSourceBadge.ENV, live=False,
            tooltip="ユーザーごとのレートリミット（ミリ秒）"
        ))

        self.discord_timeout = QDoubleSpinBox()
        self.discord_timeout.setRange(5.0, 60.0)
        self.discord_timeout.setSuffix(" 秒")
        self.discord_timeout.setValue(15.0)
        dl.addWidget(ConfigField(
            "起動タイムアウト", self.discord_timeout,
            source=ConfigSourceBadge.YAML, live=False,
            tooltip="Discord Bot起動のタイムアウト（秒）"
        ))

        layout.addWidget(discord_card)

        layout.addStretch()
        return self._make_scroll_page(page)

    # ════════════════════════════════════════════
    # データ読み込み
    # ════════════════════════════════════════════

    def _load_all(self):
        """全設定を各ソースから読み込み"""
        # APIキー
        self._load_api_keys()

        # config.yaml
        self._load_from_yaml()

        # 優先順位
        self._load_priority_list()

        # OpenClaw
        self._load_openclaw_settings()

        # ランタイムステータスチェック
        self._lmstudio_check_status()
        self._ollama_check_status()
        self._llamacpp_check_status()

    def _load_api_keys(self):
        """APIキー状態を確認"""
        try:
            if self.key_manager.get_api_key('anthropic'):
                self.anthropic_key.setPlaceholderText(f"✅ {L10n.API_KEY_SAVED}（変更する場合のみ入力）")
                self.anthropic_key.clear()
            if self.key_manager.get_api_key('openai'):
                self.openai_key.setPlaceholderText(f"✅ {L10n.API_KEY_SAVED}")
                self.openai_key.clear()
            if self.key_manager.get_api_key('google'):
                self.google_key.setPlaceholderText(f"✅ {L10n.API_KEY_SAVED}")
                self.google_key.clear()
            if self.key_manager.get_api_key('openrouter'):
                self.openrouter_key.setPlaceholderText(f"✅ {L10n.API_KEY_SAVED}")
                self.openrouter_key.clear()

            backend = self.key_manager.get_backend()
            self.backend_label.setText(f"バックエンド: {backend}")
            self.keyring_status.setText("✅ キーストア利用可能")
            self.keyring_status.setStyleSheet(f"color: {Colors.SECONDARY};")
        except Exception:
            self.keyring_status.setText("❌ キーストアエラー")
            self.keyring_status.setStyleSheet(f"color: {Colors.DANGER};")

    def _load_from_yaml(self):
        """config.yaml から設定を読み込み"""
        cfg = self.config

        # デフォルトモデル
        default = cfg.get("default", "local")
        idx = self.default_model.findData(default)
        if idx >= 0:
            self.default_model.setCurrentIndex(idx)

        # 確信度閾値
        threshold = cfg.get("routing.intelligent_routing.confidence_threshold", 0.75)
        self.confidence_threshold.setValue(float(threshold))

        # タイムアウト (config.yaml はミリ秒)
        local_ms = cfg.get("performance.timeout_local", 30000)
        cloud_ms = cfg.get("performance.timeout_cloud", 60000)
        self.local_timeout.setValue(int(local_ms) // 1000)
        self.cloud_timeout.setValue(int(cloud_ms) // 1000)

        # コスト
        self.cost_notify.setChecked(cfg.get("cost.tracking", True))
        self.cost_threshold.setValue(cfg.get("cost.notify_threshold", 50))

        # キャッシュ
        self.cache_enabled.setChecked(cfg.get("cache.enabled", True))
        self.cache_ttl.setValue(cfg.get("cache.sqlite.ttl", 3600))
        self.cache_max.setValue(cfg.get("cache.sqlite.max_entries", 10000))

        # ログ
        log_level = cfg.get("logging.level", "info")
        idx = self.log_level.findData(log_level)
        if idx >= 0:
            self.log_level.setCurrentIndex(idx)

        # Discord (enabled は config.yaml、その他は .env)
        self.discord_enabled.setChecked(cfg.get("launcher.discord.enabled", False))
        env_vars = cfg.load_env()
        discord_token = env_vars.get("DISCORD_BOT_TOKEN", "")
        if discord_token:
            self.discord_token.setPlaceholderText(f"✅ 設定済み（変更する場合のみ入力）")
        self.discord_prefix.setText(env_vars.get("DISCORD_PREFIX", "!"))
        self.discord_admin_ids.setText(env_vars.get("DISCORD_ADMIN_IDS", ""))
        rate_limit_str = env_vars.get("DISCORD_RATE_LIMIT_MS", "3000")
        try:
            self.discord_rate_limit.setValue(int(rate_limit_str))
        except ValueError:
            self.discord_rate_limit.setValue(3000)

        # LM Studio ランタイム
        self.lmstudio_enabled.setChecked(cfg.get("launcher.lmstudio.enabled", True))
        self.lmstudio_endpoint.setText(
            cfg.get("launcher.lmstudio.endpoint", "http://localhost:1234/v1") or "http://localhost:1234/v1"
        )
        self.lmstudio_timeout.setValue(float(cfg.get("launcher.lmstudio.timeout", 60.0)))
        self.lmstudio_retry.setValue(int(cfg.get("launcher.lmstudio.retry", 2)))
        self.lmstudio_model_detect.setChecked(cfg.get("launcher.lmstudio.model_detect", True))
        self.lmstudio_model_detect_timeout.setValue(float(cfg.get("launcher.lmstudio.model_detect_timeout", 30.0)))

        # Ollama ランタイム
        self.ollama_enabled.setChecked(cfg.get("launcher.ollama.enabled", False))
        self.ollama_endpoint.setText(
            cfg.get("launcher.ollama.endpoint", "http://localhost:11434") or "http://localhost:11434"
        )
        self.ollama_timeout.setValue(float(cfg.get("launcher.ollama.timeout", 30.0)))

        # llama.cpp ランタイム
        self.llamacpp_enabled.setChecked(cfg.get("launcher.llamacpp.enabled", False))
        self.llamacpp_endpoint.setText(
            cfg.get("launcher.llamacpp.endpoint", "http://localhost:8080") or "http://localhost:8080"
        )
        self.llamacpp_timeout.setValue(float(cfg.get("launcher.llamacpp.timeout", 30.0)))
        self.llamacpp_model_path.setText(cfg.get("launcher.llamacpp.model", "") or "")

        # OpenClaw
        self.openclaw_enabled.setChecked(cfg.get("launcher.openclaw.enabled", True))
        self.openclaw_timeout.setValue(float(cfg.get("launcher.openclaw.timeout", 15.0)))
        self.openclaw_auto_sync.setChecked(cfg.get("launcher.openclaw.auto_sync", False))
        self.openclaw_fallback_sync.setChecked(cfg.get("launcher.openclaw.fallback_sync", False))
        self.openclaw_config_path.setText(cfg.get("launcher.openclaw.config_path", "") or "")

        # Discord timeout
        self.discord_timeout.setValue(float(cfg.get("launcher.discord.timeout", 15.0)))

    # ════════════════════════════════════════════
    # データ保存
    # ════════════════════════════════════════════

    def _save_all(self):
        """全設定を保存"""
        self._save_btn.setEnabled(False)
        try:
            self._save_api_keys()
            self._save_to_yaml()
            self._save_priority()
            self._save_discord_env()

            QMessageBox.information(self, "保存完了", "設定を保存しました")
            self.settings_changed.emit()
            self.accept()
        except Exception as e:
            logging.getLogger(__name__).error(f"設定保存エラー: {e}", exc_info=True)
            QMessageBox.critical(self, "保存エラー", "設定の保存に失敗しました")
            self._save_btn.setEnabled(True)

    def _save_api_keys(self):
        """APIキーを保存"""
        keys = {
            'anthropic': self.anthropic_key.text().strip(),
            'openai': self.openai_key.text().strip(),
            'google': self.google_key.text().strip(),
            'openrouter': self.openrouter_key.text().strip(),
        }
        for provider, key in keys.items():
            if key:
                self.key_manager.set_api_key(provider, key)

    def _save_to_yaml(self):
        """config.yaml に設定を書き込み"""
        cfg = self.config

        # デフォルトモデル
        cfg.set("default", self.default_model.currentData())

        # 確信度閾値
        cfg.set("routing.intelligent_routing.confidence_threshold",
                self.confidence_threshold.value())

        # タイムアウト (秒→ミリ秒で保存)
        cfg.set("performance.timeout_local", self.local_timeout.value() * 1000)
        cfg.set("performance.timeout_cloud", self.cloud_timeout.value() * 1000)

        # コスト
        cfg.set("cost.tracking", self.cost_notify.isChecked())
        cfg.set("cost.notify_threshold", self.cost_threshold.value())

        # キャッシュ
        cfg.set("cache.enabled", self.cache_enabled.isChecked())
        cfg.set("cache.sqlite.ttl", self.cache_ttl.value())
        cfg.set("cache.sqlite.max_entries", self.cache_max.value())

        # ログ
        cfg.set("logging.level", self.log_level.currentData())

        # Discord
        cfg.set("launcher.discord.enabled", self.discord_enabled.isChecked())
        cfg.set("launcher.discord.timeout", self.discord_timeout.value())

        # LM Studio ランタイム
        cfg.set("launcher.lmstudio.enabled", self.lmstudio_enabled.isChecked())
        lmstudio_ep = self.lmstudio_endpoint.text().strip()
        if lmstudio_ep:
            cfg.set("launcher.lmstudio.endpoint", lmstudio_ep)
        cfg.set("launcher.lmstudio.timeout", self.lmstudio_timeout.value())
        cfg.set("launcher.lmstudio.retry", self.lmstudio_retry.value())
        cfg.set("launcher.lmstudio.model_detect", self.lmstudio_model_detect.isChecked())
        cfg.set("launcher.lmstudio.model_detect_timeout", self.lmstudio_model_detect_timeout.value())

        # Ollama ランタイム
        cfg.set("launcher.ollama.enabled", self.ollama_enabled.isChecked())
        ollama_ep = self.ollama_endpoint.text().strip()
        if ollama_ep:
            cfg.set("launcher.ollama.endpoint", ollama_ep)
        cfg.set("launcher.ollama.timeout", self.ollama_timeout.value())

        # llama.cpp ランタイム
        cfg.set("launcher.llamacpp.enabled", self.llamacpp_enabled.isChecked())
        llamacpp_ep = self.llamacpp_endpoint.text().strip()
        if llamacpp_ep:
            cfg.set("launcher.llamacpp.endpoint", llamacpp_ep)
        cfg.set("launcher.llamacpp.timeout", self.llamacpp_timeout.value())
        llamacpp_model = self.llamacpp_model_path.text().strip()
        if llamacpp_model:
            cfg.set("launcher.llamacpp.model", llamacpp_model)

        # OpenClaw
        cfg.set("launcher.openclaw.enabled", self.openclaw_enabled.isChecked())
        cfg.set("launcher.openclaw.timeout", self.openclaw_timeout.value())
        cfg.set("launcher.openclaw.auto_sync", self.openclaw_auto_sync.isChecked())
        cfg.set("launcher.openclaw.fallback_sync", self.openclaw_fallback_sync.isChecked())
        oc_path = self.openclaw_config_path.text().strip()
        if oc_path:
            cfg.set("launcher.openclaw.config_path", oc_path)

    def _save_discord_env(self):
        """Discord Bot設定を.envに保存"""
        token = self.discord_token.text().strip()
        if token:
            self.config.set_env("DISCORD_BOT_TOKEN", token)
        prefix = self.discord_prefix.text().strip()
        if prefix:
            self.config.set_env("DISCORD_PREFIX", prefix)
        admin_ids = self.discord_admin_ids.text().strip()
        if admin_ids:
            self.config.set_env("DISCORD_ADMIN_IDS", admin_ids)
        rate_limit = self.discord_rate_limit.value()
        self.config.set_env("DISCORD_RATE_LIMIT_MS", str(rate_limit))

    # ════════════════════════════════════════════
    # APIキー操作
    # ════════════════════════════════════════════

    def _toggle_anthropic_visibility(self, checked):
        if checked:
            self.anthropic_key.setEchoMode(QLineEdit.Normal)
            self.show_key_btn.setText(f"🙈 {L10n.API_KEY_HIDE}")
        else:
            self.anthropic_key.setEchoMode(QLineEdit.Password)
            self.show_key_btn.setText(f"👁️ {L10n.API_KEY_SHOW}")

    def _test_anthropic_key(self):
        """Anthropic APIキーのテスト"""
        import requests

        key = self.anthropic_key.text().strip()
        if not key:
            key = self.key_manager.get_api_key('anthropic')
            if not key:
                QMessageBox.warning(self, "エラー", "APIキーを入力してください")
                return

        self.test_key_btn.setEnabled(False)
        self.test_key_btn.setText("🧪 テスト中...")

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-5-20250929",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}]
                },
                timeout=10
            )
            if response.status_code == 200:
                QMessageBox.information(self, "成功", f"✅ {L10n.API_KEY_VALID}")
            else:
                QMessageBox.warning(self, "エラー", f"❌ {L10n.API_KEY_INVALID}")
        except Exception:
            QMessageBox.critical(self, "エラー", f"❌ {L10n.ERROR_CONNECTION_FAILED}")
        finally:
            self.test_key_btn.setEnabled(True)
            self.test_key_btn.setText(f"🧪 {L10n.API_KEY_TEST}")

    def _test_generic_key(self, provider: str):
        """汎用APIキーテスト"""
        key_fields = {"openai": self.openai_key}
        field = key_fields.get(provider)
        if not field:
            return
        key = field.text().strip()
        if not key:
            key = self.key_manager.get_api_key(provider)
        if not key:
            QMessageBox.warning(self, "エラー", "APIキーを入力してください")
            return

        # OpenAIテスト
        import requests
        try:
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=10
            )
            if response.status_code == 200:
                QMessageBox.information(self, "成功", f"✅ {L10n.API_KEY_VALID}")
            else:
                QMessageBox.warning(self, "エラー", f"❌ {L10n.API_KEY_INVALID}")
        except Exception:
            QMessageBox.critical(self, "エラー", f"❌ {L10n.ERROR_CONNECTION_FAILED}")

    def _delete_anthropic_key(self):
        reply = QMessageBox.question(
            self, "確認", L10n.CONFIRM_DELETE,
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.key_manager.delete_api_key('anthropic'):
                QMessageBox.information(self, "成功", "APIキーを削除しました")
                self.anthropic_key.setPlaceholderText("sk-ant-api03-...")
                self.anthropic_key.clear()

    # ════════════════════════════════════════════
    # 優先順位操作
    # ════════════════════════════════════════════

    def _get_project_root(self):
        return Path(__file__).resolve().parent.parent.parent

    def _load_priority_list(self):
        """レジストリとfallback_priority.jsonから優先順位リストを構築"""
        self.priority_list.clear()
        current_priority = self.config.load_fallback()
        available_models = self._get_available_model_refs()
        available_set = set(available_models)

        if current_priority and current_priority != ["local", "cloud"]:
            seen = set()
            for ref in current_priority:
                if ref in available_set and ref not in seen:
                    self._add_priority_item(ref)
                    seen.add(ref)
            for ref in available_models:
                if ref not in seen:
                    self._add_priority_item(ref)
                    seen.add(ref)
        else:
            seen = set()
            for ref in available_models:
                if ref not in seen:
                    self._add_priority_item(ref)
                    seen.add(ref)

        self._update_priority_preview()

    def _get_available_model_refs(self):
        """レジストリから利用可能なモデル参照リストを返す"""
        refs = []
        registry = self.config.load_registry()
        models = registry.get("models", {})
        for key, model_list in models.items():
            if key == "cloud":
                continue
            if isinstance(model_list, list):
                for m in model_list:
                    mid = m.get("id", "")
                    if mid and not mid.startswith("text-embedding"):
                        refs.append(f"local:{mid}")
        refs.append("cloud")
        return refs

    def _add_priority_item(self, model_ref):
        if model_ref.startswith("local:"):
            model_id = model_ref[len("local:"):]
            short = model_id.split("/")[-1] if "/" in model_id else model_id
            display = f"💻 {short}  ({model_id})"
        elif model_ref == "cloud":
            display = "☁️ Claude API"
        else:
            display = model_ref

        item = QListWidgetItem(display)
        item.setData(Qt.UserRole, model_ref)
        self.priority_list.addItem(item)

    def _priority_move_up(self):
        row = self.priority_list.currentRow()
        if row > 0:
            item = self.priority_list.takeItem(row)
            self.priority_list.insertItem(row - 1, item)
            self.priority_list.setCurrentRow(row - 1)
            self._update_priority_preview()

    def _priority_move_down(self):
        row = self.priority_list.currentRow()
        if row < self.priority_list.count() - 1:
            item = self.priority_list.takeItem(row)
            self.priority_list.insertItem(row + 1, item)
            self.priority_list.setCurrentRow(row + 1)
            self._update_priority_preview()

    def _priority_reset(self):
        self._load_priority_list()

    def _update_priority_preview(self):
        refs = self._get_priority_order()
        if not refs:
            self.priority_preview.setText("")
            return
        names = []
        for ref in refs:
            if ref.startswith("local:"):
                mid = ref[len("local:"):]
                short = mid.split("/")[-1] if "/" in mid else mid
                names.append(short)
            elif ref == "cloud":
                names.append("Claude")
            else:
                names.append(ref)
        self.priority_preview.setText(f"フォールバック順: {' → '.join(names)}")

    def _get_priority_order(self):
        refs = []
        for i in range(self.priority_list.count()):
            item = self.priority_list.item(i)
            ref = item.data(Qt.UserRole)
            if ref:
                refs.append(ref)
        return refs

    def _save_priority(self):
        refs = self._get_priority_order()
        if refs:
            self.config.save_fallback(refs)

    # ════════════════════════════════════════════
    # LM Studio ランタイム操作
    # ════════════════════════════════════════════

    def _get_lmstudio_launcher(self):
        from launcher.lmstudio_launcher import LMStudioLauncher
        endpoint = self.lmstudio_endpoint.text().strip() or "http://localhost:1234/v1"
        return LMStudioLauncher(endpoint=endpoint)

    def _lmstudio_check_status(self):
        launcher = self._get_lmstudio_launcher()
        ready = launcher.is_api_ready(timeout=2.0)
        if ready:
            self.lmstudio_status.set_status(Colors.STATUS_ONLINE, L10n.RUNTIME_RUNNING)
        else:
            self.lmstudio_status.set_status(Colors.STATUS_UNKNOWN, L10n.RUNTIME_STOPPED)

    def _lmstudio_start(self):
        launcher = self._get_lmstudio_launcher()
        if launcher.is_api_ready(timeout=2.0):
            QMessageBox.information(self, "LM Studio", "LM Studioは既に起動しています")
            self.lmstudio_status.set_status(Colors.STATUS_ONLINE, L10n.RUNTIME_RUNNING)
            return

        self.lmstudio_start_btn.setEnabled(False)
        self.lmstudio_start_btn.setText("起動中...")
        success = launcher.launch(wait_ready=True, ready_timeout=30.0)
        self.lmstudio_start_btn.setEnabled(True)
        self.lmstudio_start_btn.setText(f"▶ {L10n.RUNTIME_START}")

        if success:
            self.lmstudio_status.set_status(Colors.STATUS_ONLINE, L10n.RUNTIME_RUNNING)
            QMessageBox.information(self, "LM Studio", "LM Studioを起動しました")
        else:
            self.lmstudio_status.set_status(Colors.STATUS_ERROR, L10n.ERROR_CONNECTION_FAILED)
            QMessageBox.warning(self, "LM Studio", "LM Studioの起動に失敗しました")

    def _lmstudio_stop(self):
        launcher = self._get_lmstudio_launcher()
        launcher.stop()
        self.lmstudio_status.set_status(Colors.STATUS_UNKNOWN, L10n.RUNTIME_STOPPED)

    # ════════════════════════════════════════════
    # Ollama ランタイム操作
    # ════════════════════════════════════════════

    def _get_ollama_launcher(self):
        from launcher.ollama_launcher import OllamaLauncher
        endpoint = self.ollama_endpoint.text().strip() or "http://localhost:11434"
        return OllamaLauncher(endpoint=endpoint)

    def _get_ollama_client(self):
        from models.ollama_client import OllamaClient
        endpoint = self.ollama_endpoint.text().strip() or "http://localhost:11434"
        return OllamaClient(base_url=endpoint)

    def _ollama_check_status(self):
        launcher = self._get_ollama_launcher()
        ready = launcher.is_api_ready(timeout=2.0)
        if ready:
            self.ollama_status.set_status(Colors.STATUS_ONLINE, L10n.RUNTIME_RUNNING)
            self._ollama_refresh_models()
        else:
            self.ollama_status.set_status(Colors.STATUS_UNKNOWN, L10n.RUNTIME_STOPPED)

    def _ollama_start(self):
        launcher = self._get_ollama_launcher()
        if launcher.is_api_ready(timeout=2.0):
            QMessageBox.information(self, "Ollama", "Ollamaは既に起動しています")
            self.ollama_status.set_status(Colors.STATUS_ONLINE, L10n.RUNTIME_RUNNING)
            return

        self.ollama_start_btn.setEnabled(False)
        self.ollama_start_btn.setText("起動中...")
        success = launcher.launch(wait_ready=True, ready_timeout=15.0)
        self.ollama_start_btn.setEnabled(True)
        self.ollama_start_btn.setText(f"▶ {L10n.RUNTIME_START}")

        if success:
            self.ollama_status.set_status(Colors.STATUS_ONLINE, L10n.RUNTIME_RUNNING)
            self._ollama_refresh_models()
            QMessageBox.information(self, "Ollama", "Ollamaを起動しました")
        else:
            self.ollama_status.set_status(Colors.STATUS_ERROR, L10n.ERROR_CONNECTION_FAILED)
            QMessageBox.warning(self, "Ollama", "Ollamaの起動に失敗しました")

    def _ollama_stop(self):
        launcher = self._get_ollama_launcher()
        launcher.stop()
        self.ollama_status.set_status(Colors.STATUS_UNKNOWN, L10n.RUNTIME_STOPPED)
        self.ollama_model_list.clear()

    def _ollama_refresh_models(self):
        self.ollama_model_list.clear()
        try:
            client = self._get_ollama_client()
            models = client.list_models(timeout=5.0)
        except Exception:
            models = []
        for m in models:
            name = m.get("name", "unknown")
            size_bytes = m.get("size", 0)
            size_gb = size_bytes / (1024 ** 3) if size_bytes else 0
            display = f"{name}  ({size_gb:.1f} GB)" if size_gb > 0 else name
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, name)
            self.ollama_model_list.addItem(item)

    def _ollama_pull_model(self):
        name, ok = QInputDialog.getText(
            self, L10n.OLLAMA_PULL, "ダウンロードするモデル名を入力:",
            text="tinyllama"
        )
        if not ok or not name.strip():
            return

        name = name.strip()
        client = self._get_ollama_client()
        if not client.is_available():
            QMessageBox.warning(self, "Ollama", "Ollamaが応答していません")
            return

        self.ollama_progress.setVisible(True)
        self.ollama_progress.setFormat(f"Pulling {name}... %p%")
        self.ollama_progress.setValue(0)
        self.ollama_pull_btn.setEnabled(False)

        def on_progress(status, completed, total):
            if total > 0:
                pct = int(completed * 100 / total)
                self.ollama_progress.setValue(pct)
                self.ollama_progress.setFormat(f"{status} %p%")

        def _do_pull():
            success = client.pull_model(name, on_progress=on_progress)
            self.ollama_pull_btn.setEnabled(True)
            self.ollama_progress.setVisible(False)
            if success:
                self._ollama_refresh_models()

        thread = threading.Thread(target=_do_pull, daemon=True)
        thread.start()

    def _ollama_delete_model(self):
        current = self.ollama_model_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Ollama", "削除するモデルを選択してください")
            return

        name = current.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "確認", f"モデル '{name}' を削除しますか？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        client = self._get_ollama_client()
        if client.delete_model(name):
            self._ollama_refresh_models()
            QMessageBox.information(self, "Ollama", f"モデル '{name}' を削除しました")
        else:
            QMessageBox.warning(self, "Ollama", "モデルの削除に失敗しました")

    # ════════════════════════════════════════════
    # llama.cpp ランタイム操作
    # ════════════════════════════════════════════

    def _get_llamacpp_launcher(self):
        from launcher.llamacpp_launcher import LlamaCppLauncher
        endpoint = self.llamacpp_endpoint.text().strip() or "http://localhost:8080"
        model_path = self.llamacpp_model_path.text().strip() or None
        return LlamaCppLauncher(endpoint=endpoint, model_path=model_path)

    def _llamacpp_check_status(self):
        launcher = self._get_llamacpp_launcher()
        ready = launcher.is_api_ready(timeout=2.0)
        if ready:
            self.llamacpp_status.set_status(Colors.STATUS_ONLINE, L10n.RUNTIME_RUNNING)
        else:
            self.llamacpp_status.set_status(Colors.STATUS_UNKNOWN, L10n.RUNTIME_STOPPED)

    def _llamacpp_start(self):
        launcher = self._get_llamacpp_launcher()
        if launcher.is_api_ready(timeout=2.0):
            QMessageBox.information(self, "llama.cpp", "llama-serverは既に起動しています")
            self.llamacpp_status.set_status(Colors.STATUS_ONLINE, L10n.RUNTIME_RUNNING)
            return

        self.llamacpp_start_btn.setEnabled(False)
        self.llamacpp_start_btn.setText("起動中...")
        success = launcher.launch(wait_ready=True, ready_timeout=15.0)
        self.llamacpp_start_btn.setEnabled(True)
        self.llamacpp_start_btn.setText(f"▶ {L10n.RUNTIME_START}")

        if success:
            self.llamacpp_status.set_status(Colors.STATUS_ONLINE, L10n.RUNTIME_RUNNING)
            QMessageBox.information(self, "llama.cpp", "llama-serverを起動しました")
        else:
            self.llamacpp_status.set_status(Colors.STATUS_ERROR, L10n.ERROR_CONNECTION_FAILED)
            QMessageBox.warning(self, "llama.cpp", "llama-serverの起動に失敗しました")

    def _llamacpp_stop(self):
        launcher = self._get_llamacpp_launcher()
        launcher.stop()
        self.llamacpp_status.set_status(Colors.STATUS_UNKNOWN, L10n.RUNTIME_STOPPED)

    def _llamacpp_browse_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, L10n.LLAMACPP_BROWSE, "",
            "GGUF Files (*.gguf);;All Files (*)"
        )
        if path:
            self.llamacpp_model_path.setText(path)

    # ════════════════════════════════════════════
    # スキャン操作
    # ════════════════════════════════════════════

    def _run_scan(self):
        """モデルスキャン実行"""
        try:
            import asyncio
            from scanner.scanner import MultiRuntimeScanner

            scanner = MultiRuntimeScanner()
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(scanner.scan_all())
            finally:
                loop.close()

            # 優先順位リストを更新
            self._load_priority_list()
            QMessageBox.information(self, L10n.RUNTIME_SCAN, "スキャン完了。モデル一覧を更新しました")
        except Exception as e:
            QMessageBox.warning(self, "スキャンエラー", f"スキャンに失敗しました:\n{e}")

    # ════════════════════════════════════════════
    # OpenClaw操作
    # ════════════════════════════════════════════

    def _load_openclaw_settings(self):
        # config.yaml から読み込み済み (_load_from_yaml で設定)
        self._check_openclaw_status()

    def _check_openclaw_status(self):
        try:
            from openclaw.config_manager import OpenClawConfigManager

            custom_path = self.openclaw_config_path.text().strip()
            manager = OpenClawConfigManager(
                config_path=custom_path if custom_path else None
            )

            if manager.exists():
                llm_config = manager.get_current_llm()
                model = llm_config.get('model', '不明')
                endpoint = llm_config.get('endpoint', '不明')
                self.openclaw_status.setText(
                    f"✅ OpenClaw設定検出\n"
                    f"モデル: {model} | エンドポイント: {endpoint}"
                )
            else:
                self.openclaw_status.setText("⚠️ OpenClaw設定ファイルが見つかりません")
        except ImportError:
            self.openclaw_status.setText("❌ OpenClawモジュールが利用できません")
        except Exception as e:
            self.openclaw_status.setText(f"エラー: {e}")

    def _detect_openclaw_config(self):
        try:
            from openclaw.config_manager import OpenClawConfigManager

            manager = OpenClawConfigManager()
            if manager.config_path:
                self.openclaw_config_path.setText(str(manager.config_path))
                self._check_openclaw_status()
                QMessageBox.information(
                    self, "検出成功",
                    f"OpenClaw設定ファイルを検出しました:\n{manager.config_path}"
                )
            else:
                QMessageBox.warning(self, "検出失敗", "設定ファイルが見つかりませんでした")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"検出中にエラーが発生しました:\n{e}")

    def _sync_openclaw_now(self):
        try:
            from scanner.registry import ModelRegistry
            from openclaw.config_manager import OpenClawConfigManager

            project_root = self._get_project_root()
            registry = ModelRegistry(
                cache_path=str(project_root / "data" / "model_registry.json")
            )

            local_models = registry.get_local_models()
            if not local_models:
                QMessageBox.warning(
                    self, "同期失敗",
                    "ローカルモデルが検出されていません。\n先にモデルスキャンを実行してください。"
                )
                return

            custom_path = self.openclaw_config_path.text().strip()
            manager = OpenClawConfigManager(
                config_path=custom_path if custom_path else None
            )

            if not manager.exists():
                reply = QMessageBox.question(
                    self, "設定ファイル未検出",
                    "OpenClaw設定ファイルが見つかりません。\nデフォルト設定を作成しますか？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    manager.create_default_config()
                else:
                    return

            models_dict = [m.to_dict() for m in local_models]
            manager.update_available_models(models_dict)

            first_model = local_models[0]
            endpoint = first_model.runtime.endpoint if first_model.runtime else "http://localhost:1234/v1"
            manager.update_llm_endpoint(endpoint, first_model.id)

            self._check_openclaw_status()
            QMessageBox.information(
                self, "同期完了",
                f"デフォルトモデル: {first_model.id}\n登録モデル数: {len(local_models)}"
            )
        except Exception as e:
            QMessageBox.critical(self, "同期エラー", f"同期中にエラーが発生しました:\n{e}")

    def _create_openclaw_config(self):
        try:
            from openclaw.config_manager import OpenClawConfigManager

            manager = OpenClawConfigManager()
            if manager.create_default_config():
                self.openclaw_config_path.setText(str(manager.config_path))
                self._check_openclaw_status()
                QMessageBox.information(
                    self, "作成完了",
                    f"OpenClawデフォルト設定を作成しました:\n{manager.config_path}"
                )
            else:
                QMessageBox.warning(self, "作成失敗", "設定ファイルの作成に失敗しました")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"作成中にエラーが発生しました:\n{e}")


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    dialog = SettingsDialog()
    dialog.show()

    sys.exit(app.exec())
