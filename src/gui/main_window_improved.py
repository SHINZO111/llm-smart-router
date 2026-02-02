#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Smart Router GUI v2.0 改良版メインウィンドウ

【改善点】
1. パフォーマンス最適化
   - 大規模テキストの非同期処理
   - UI更新のバッチ処理
   - メモリ使用量最適化

2. エラーハンドリング強化
   - ユーザーフレンドリーなエラーメッセージ
   - カテゴリ別エラー対処法提案
   - 詳細ログ表示

3. キーボードショートカット拡張
   - Ctrl+M: モデル切替
   - Ctrl+Shift+C: 出力コピー
   - Ctrl++/Ctrl+-: フォントサイズ調整
   - F1: クイックヘルプ

4. ログ機能
   - アプリケーション動作ログ
   - エラーログ
   - 統計ログ

【作者】クラ for 新さん
【バージョン】2.0.1-improved
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
    QTableWidgetItem, QHeaderView, QSystemTrayIcon, QPlainTextEdit
)
from PySide6.QtCore import (
    Qt, QThread, Signal, Slot, QTimer, QSize, QSettings,
    QRunnable, QThreadPool, QMetaObject, Q_ARG
)
from PySide6.QtGui import (
    QAction, QIcon, QFont, QPalette, QColor, QKeySequence,
    QShortcut, QFontDatabase
)

# 自作モジュール
sys.path.insert(0, str(Path(__file__).parent.parent))
from security.key_manager import SecureKeyManager
from gui.dashboard import StatisticsDashboard
from gui.settings_dialog import SettingsDialog

# 改善モジュール
try:
    from gui.performance_optimizer import (
        PerformanceOptimizer, ErrorHandler, ShortcutManager, ApplicationLogger
    )
    IMPROVED_MODULES_AVAILABLE = True
except ImportError:
    IMPROVED_MODULES_AVAILABLE = False
    print("⚠️ 改善モジュールが読み込めません。基本機能のみ使用します。")


# ============================================================
# ワーカースレッド（改善版）
# ============================================================

class LLMWorker(QThread):
    """
    LLMリクエストをバックグラウンドで実行するワーカースレッド（改善版）
    
    改善点:
    - プログレス更新の最適化
    - キャンセル対応の強化
    - エラーハンドリングの改善
    """
    
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)
    partial_result = Signal(str)  # ストリーミング対応
    
    def __init__(self, router_path, input_text, model_type=None, config=None, 
                 streaming=False, parent=None):
        super().__init__(parent)
        self.router_path = router_path
        self.input_text = input_text
        self.model_type = model_type
        self.config = config or {}
        self.streaming = streaming
        self._is_cancelled = False
        self._process = None
        
    def cancel(self):
        """実行をキャンセル"""
        self._is_cancelled = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        self.wait(1000)
        
    def run(self):
        try:
            self.progress.emit("🔄 リクエスト準備中...")
            
            # Node.js経由でrouter.jsを実行
            cmd = ['node', os.path.join(self.router_path, 'openclaw-integration.js')]
            
            if self.model_type:
                cmd.append(self.model_type)
            
            cmd.append(self.input_text)
            
            # 環境変数設定
            env = os.environ.copy()
            key_manager = SecureKeyManager()
            api_key = key_manager.get_api_key('anthropic')
            if api_key:
                env['ANTHROPIC_API_KEY'] = api_key
            
            if self._is_cancelled:
                return
            
            self.progress.emit("🚀 LLMに問い合わせ中...")
            
            # サブプロセス実行
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                env=env
            )
            
            # タイムアウト監視しながら出力取得
            start_time = datetime.now()
            timeout = self.config.get('timeout', 120)
            
            stdout_lines = []
            
            while True:
                if self._is_cancelled:
                    self._process.terminate()
                    return
                
                # タイムアウトチェック
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    self._process.terminate()
                    self.error.emit(f"⏱️ タイムアウト: リクエストが{timeout}秒を超えました")
                    return
                
                # 出力読み取り
                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    break
                
                if line:
                    stdout_lines.append(line)
                    if self.streaming:
                        self.partial_result.emit(line)
                
                self.msleep(10)  # 短時間スリープでCPU負荷軽減
            
            # 終了コード確認
            return_code = self._process.poll()
            stderr = self._process.stderr.read()
            
            if return_code == 0:
                result_text = ''.join(stdout_lines)
                self.finished.emit({
                    'success': True,
                    'response': result_text,
                    'model': self.model_type or 'auto',
                    'duration': elapsed
                })
            else:
                error_msg = stderr or "不明なエラーが発生しました"
                self.error.emit(f"❌ エラー (コード {return_code}): {error_msg}")
                
        except subprocess.TimeoutExpired:
            self.error.emit("⏱️ タイムアウト: リクエストが時間を超えました")
        except Exception as e:
            self.error.emit(f"❌ エラー: {str(e)}")


# ============================================================
# 改良版メインウィンドウ
# ============================================================

class ImprovedMainWindow(QMainWindow):
    """改良版メインウィンドウ"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Smart Router Pro v2.1")
        self.setMinimumSize(1400, 900)
        
        # 設定
        self.settings = QSettings('LLMSmartRouter', 'Pro')
        self.router_path = self.settings.value('router_path', str(Path(__file__).parent.parent.parent))
        
        # ワーカー参照
        self.worker = None
        
        # 統計
        self.session_stats = {
            'requests': 0,
            'local': 0,
            'cloud': 0,
            'tokens_in': 0,
            'tokens_out': 0,
            'cost': 0.0,
            'start_time': datetime.now()
        }
        
        # 改善モジュール
        if IMPROVED_MODULES_AVAILABLE:
            self.optimizer = PerformanceOptimizer(self)
            self.error_handler = ErrorHandler(self)
            self.shortcut_manager = ShortcutManager(self)
            self.logger = ApplicationLogger()
        else:
            self.optimizer = None
            self.error_handler = None
            self.shortcut_manager = None
            self.logger = None
        
        self.init_ui()
        self.init_menu()
        self.init_shortcuts()
        self.init_timer()
        
        # APIキーチェック
        QTimer.singleShot(500, self.check_api_key)
        
        if self.logger:
            self.logger.info("アプリケーション起動完了")
    
    def init_ui(self):
        """UI初期化（改良版）"""
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # スプリッター
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左パネル（入力・制御）
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # 中央パネル（出力）
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)
        
        # 右パネル（ダッシュボード）
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # スプリッターの比率設定
        splitter.setSizes([400, 600, 400])
        
        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("✅ 準備完了")
        
        # プログレスバー
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress)
        
        # メモリ使用量表示（改良版）
        self.memory_label = QLabel("💾 -- MB")
        self.memory_label.setStyleSheet("color: #9ca3af;")
        self.status_bar.addPermanentWidget(self.memory_label)
    
    def create_left_panel(self):
        """左パネル（入力・制御）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        
        # === モデル選択セクション ===
        model_group = QGroupBox("🎯 モデル選択")
        model_layout = QVBoxLayout(model_group)
        
        # モデル選択コンボ
        self.model_combo = QComboBox()
        self.model_combo.addItem("🧠 自動判定（推奨）", "auto")
        self.model_combo.addItem("🏠 ローカルLLM", "local")
        self.model_combo.addItem("☁️ Claude (Claude Sonnet)", "claude")
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        model_layout.addWidget(self.model_combo)
        
        # モデル状態表示
        self.model_status = QLabel("🟢 自動判定モード")
        self.model_status.setObjectName("status")
        model_layout.addWidget(self.model_status)
        
        layout.addWidget(model_group)
        
        # === プリセットセクション ===
        preset_group = QGroupBox("📋 用途プリセット")
        preset_layout = QVBoxLayout(preset_group)
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("✨ 自動検出", None)
        for preset_id, preset in PresetManager.get_all_presets().items():
            self.preset_combo.addItem(f"{preset['icon']} {preset['name']}", preset_id)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        preset_layout.addWidget(self.preset_combo)
        
        # プリセット説明
        self.preset_desc = QLabel("AIが用途を自動判定します")
        self.preset_desc.setWordWrap(True)
        self.preset_desc.setObjectName("text_secondary")
        preset_layout.addWidget(self.preset_desc)
        
        layout.addWidget(preset_group)
        
        # === 入力セクション ===
        input_group = QGroupBox("📝 入力")
        input_layout = QVBoxLayout(input_group)
        
        # 入力欄
        self.input_text = QPlainTextEdit()
        self.input_text.setPlaceholderText(
            "ここに質問やタスクを入力してください...\n\n"
            "例：\n"
            "• この工事のコスト見積をレビューしてください\n"
            "• 推しの配信スケジュール最適化を手伝って\n"
            "• このPythonコードのバグを直して"
        )
        self.input_text.setMaximumHeight(200)
        input_layout.addWidget(self.input_text)
        
        # 入力文字数カウンタ（改良版）
        self.input_counter = QLabel("文字数: 0")
        self.input_counter.setStyleSheet("color: #9ca3af; font-size: 11px;")
        self.input_text.textChanged.connect(self.update_input_counter)
        input_layout.addWidget(self.input_counter)
        
        # クイックアクション
        quick_layout = QHBoxLayout()
        
        self.clear_btn = QPushButton("🗑️ クリア")
        self.clear_btn.setToolTip("入力をクリア (Ctrl+L)")
        self.clear_btn.clicked.connect(self.clear_input)
        quick_layout.addWidget(self.clear_btn)
        
        self.paste_btn = QPushButton("📋 貼り付け")
        self.paste_btn.clicked.connect(self.paste_clipboard)
        quick_layout.addWidget(self.paste_btn)
        
        self.load_btn = QPushButton("📁 ファイル読込")
        self.load_btn.setToolTip("ファイルを開く (Ctrl+O)")
        self.load_btn.clicked.connect(self.load_file)
        quick_layout.addWidget(self.load_btn)
        
        input_layout.addLayout(quick_layout)
        
        layout.addWidget(input_group)
        
        # === システムプロンプト ===
        prompt_group = QGroupBox("⚙️ システムプロンプト（任意）")
        prompt_layout = QVBoxLayout(prompt_group)
        
        self.system_prompt = QPlainTextEdit()
        self.system_prompt.setPlaceholderText("特定の役割や制約を指定できます...")
        self.system_prompt.setMaximumHeight(100)
        prompt_layout.addWidget(self.system_prompt)
        
        layout.addWidget(prompt_group)
        
        # === 実行ボタン ===
        self.execute_btn = QPushButton("🚀 実行 (Ctrl+Enter)")
        self.execute_btn.setObjectName("primary")
        self.execute_btn.setMinimumHeight(50)
        self.execute_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.execute_btn.clicked.connect(self.execute)
        layout.addWidget(self.execute_btn)
        
        # ストップボタン
        self.stop_btn = QPushButton("⏹️ 停止 (Esc)")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.clicked.connect(self.stop_execution)
        self.stop_btn.setVisible(False)
        layout.addWidget(self.stop_btn)
        
        layout.addStretch()
        
        return panel
    
    def create_center_panel(self):
        """中央パネル（出力）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        
        # === 出力タブ ===
        self.output_tabs = QTabWidget()
        
        # メイン出力タブ
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("実行結果がここに表示されます...")
        output_layout.addWidget(self.output_text)
        
        # 出力アクション
        output_actions = QHBoxLayout()
        
        self.copy_btn = QPushButton("📋 コピー")
        self.copy_btn.setToolTip("出力をコピー (Ctrl+Shift+C)")
        self.copy_btn.clicked.connect(self.copy_output)
        output_actions.addWidget(self.copy_btn)
        
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.setToolTip("結果を保存 (Ctrl+S)")
        self.save_btn.clicked.connect(self.save_output)
        output_actions.addWidget(self.save_btn)
        
        self.clear_output_btn = QPushButton("🗑️ クリア")
        self.clear_output_btn.clicked.connect(lambda: self.output_text.clear())
        output_actions.addWidget(self.clear_output_btn)
        
        output_actions.addStretch()
        output_layout.addLayout(output_actions)
        
        self.output_tabs.addTab(output_widget, "📄 出力")
        
        # 生ログタブ
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("詳細ログがここに表示されます...")
        log_layout.addWidget(self.log_text)
        
        self.output_tabs.addTab(log_widget, "🔍 ログ")
        
        layout.addWidget(self.output_tabs)
        
        # === メタデータ表示 ===
        meta_group = QGroupBox("📊 実行情報")
        meta_layout = QHBoxLayout(meta_group)
        
        self.meta_model = QLabel("モデル: -")
        meta_layout.addWidget(self.meta_model)
        
        self.meta_time = QLabel("時間: -")
        meta_layout.addWidget(self.meta_time)
        
        self.meta_tokens = QLabel("トークン: -")
        meta_layout.addWidget(self.meta_tokens)
        
        self.meta_cost = QLabel("コスト: -")
        meta_layout.addWidget(self.meta_cost)
        
        meta_layout.addStretch()
        
        layout.addWidget(meta_group)
        
        return panel
    
    def create_right_panel(self):
        """右パネル（ダッシュボード）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        
        # === 統計ダッシュボード ===
        self.dashboard = StatisticsDashboard()
        layout.addWidget(self.dashboard)
        
        # === クイック統計 ===
        stats_group = QGroupBox("📈 セッション統計")
        stats_layout = QGridLayout(stats_group)
        
        self.stat_requests = QLabel("リクエスト: 0")
        stats_layout.addWidget(self.stat_requests, 0, 0)
        
        self.stat_local = QLabel("🟢 ローカル: 0")
        stats_layout.addWidget(self.stat_local, 0, 1)
        
        self.stat_cloud = QLabel("🔵 クラウド: 0")
        stats_layout.addWidget(self.stat_cloud, 1, 0)
        
        self.stat_cost = QLabel("💰 コスト: ¥0")
        stats_layout.addWidget(self.stat_cost, 1, 1)
        
        layout.addWidget(stats_group)
        
        # === 最近の履歴 ===
        history_group = QGroupBox("🕐 最近の履歴")
        history_layout = QVBoxLayout(history_group)
        
        self.history_list = QTableWidget()
        self.history_list.setColumnCount(4)
        self.history_list.setHorizontalHeaderLabels(["時間", "モデル", "トークン", "コスト"])
        self.history_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_list.setMaximumHeight(200)
        history_layout.addWidget(self.history_list)
        
        layout.addWidget(history_group)
        
        layout.addStretch()
        
        return panel
    
    def init_menu(self):
        """メニューバー初期化"""
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu("📁 ファイル")
        
        load_action = QAction("📂 ファイルを開く", self)
        load_action.setShortcut(QKeySequence.Open)
        load_action.triggered.connect(self.load_file)
        file_menu.addAction(load_action)
        
        save_action = QAction("💾 結果を保存", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_output)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("🚪 終了", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 編集メニュー
        edit_menu = menubar.addMenu("✏️ 編集")
        
        clear_action = QAction("🗑️ 入力クリア", self)
        clear_action.setShortcut("Ctrl+L")
        clear_action.triggered.connect(self.clear_input)
        edit_menu.addAction(clear_action)
        
        copy_output_action = QAction("📋 出力コピー", self)
        copy_output_action.setShortcut("Ctrl+Shift+C")
        copy_output_action.triggered.connect(self.copy_output)
        edit_menu.addAction(copy_output_action)
        
        # 表示メニュー（新規）
        view_menu = menubar.addMenu("👁️ 表示")
        
        zoom_in_action = QAction("🔍 拡大", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("🔍 縮小", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        zoom_reset_action = QAction("🔄 リセット", self)
        zoom_reset_action.setShortcut("Ctrl+0")
        zoom_reset_action.triggered.connect(self.zoom_reset)
        view_menu.addAction(zoom_reset_action)
        
        view_menu.addSeparator()
        
        dashboard_action = QAction("📊 ダッシュボード", self)
        dashboard_action.setShortcut("Ctrl+D")
        dashboard_action.triggered.connect(self.show_full_stats)
        view_menu.addAction(dashboard_action)
        
        # 設定メニュー
        settings_menu = menubar.addMenu("⚙️ 設定")
        
        api_action = QAction("🔐 APIキー設定", self)
        api_action.setShortcut("Ctrl+T")
        api_action.triggered.connect(self.open_settings)
        settings_menu.addAction(api_action)
        
        config_action = QAction("📋 ルーター設定", self)
        config_action.triggered.connect(self.open_router_config)
        settings_menu.addAction(config_action)
        
        # ツールメニュー
        tools_menu = menubar.addMenu("🛠️ ツール")
        
        stats_action = QAction("📊 統計表示", self)
        stats_action.triggered.connect(self.show_full_stats)
        tools_menu.addAction(stats_action)
        
        clear_stats_action = QAction("🗑️ 統計リセット", self)
        clear_stats_action.triggered.connect(self.reset_stats)
        tools_menu.addAction(clear_stats_action)
        
        tools_menu.addSeparator()
        
        # ログメニュー（新規）
        view_logs_action = QAction("📜 ログ表示", self)
        view_logs_action.triggered.connect(self.show_logs)
        tools_menu.addAction(view_logs_action)
        
        # ヘルプメニュー
        help_menu = menubar.addMenu("❓ ヘルプ")
        
        shortcuts_action = QAction("⌨️ キーボードショートカット", self)
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        about_action = QAction("ℹ️ バージョン情報", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def init_shortcuts(self):
        """キーボードショートカット（改良版）"""
        # 基本ショートカット
        self.execute_shortcut = QShortcut(
            QKeySequence("Ctrl+Return"), self
        )
        self.execute_shortcut.activated.connect(self.execute)
        
        self.stop_shortcut = QShortcut(
            QKeySequence("Escape"), self
        )
        self.stop_shortcut.activated.connect(self.stop_execution)
        
        # 拡張ショートカット
        if self.shortcut_manager:
            self.shortcut_manager.register_all()
    
    def init_timer(self):
        """タイマー初期化"""
        # メモリ使用量更新タイマー
        self.memory_timer = QTimer(self)
        self.memory_timer.timeout.connect(self.update_memory_usage)
        self.memory_timer.start(5000)  # 5秒間隔
    
    # === イベントハンドラ ===
    
    def update_input_counter(self):
        """入力文字数を更新"""
        count = len(self.input_text.toPlainText())
        self.input_counter.setText(f"文字数: {count}")
        
        # 大規模テキスト警告
        if count > 50000:
            self.input_counter.setStyleSheet("color: #ef4444; font-size: 11px;")
        elif count > 10000:
            self.input_counter.setStyleSheet("color: #f59e0b; font-size: 11px;")
        else:
            self.input_counter.setStyleSheet("color: #9ca3af; font-size: 11px;")
    
    def update_memory_usage(self):
        """メモリ使用量を更新"""
        try:
            import psutil
            process = psutil.Process()
            mem_mb = process.memory_info().rss / 1024 / 1024
            self.memory_label.setText(f"💾 {mem_mb:.0f} MB")
        except:
            pass
    
    def on_model_changed(self, index):
        model = self.model_combo.currentData()
        if model == "auto":
            self.model_status.setText("🟢 自動判定モード")
            self.model_status.setObjectName("status")
        elif model == "local":
            self.model_status.setText("🏠 ローカルLLM固定")
            self.model_status.setObjectName("warning")
        else:
            self.model_status.setText("☁️ Claude固定")
            self.model_status.setObjectName("status")
        self.model_status.style().unpolish(self.model_status)
        self.model_status.style().polish(self.model_status)
    
    def on_preset_changed(self, index):
        preset_id = self.preset_combo.currentData()
        if preset_id:
            preset = PresetManager.get_preset(preset_id)
            self.preset_desc.setText(preset['description'])
            self.system_prompt.setPlainText(preset['system_prompt'])
        else:
            self.preset_desc.setText("AIが用途を自動判定します")
            self.system_prompt.clear()
    
    def execute(self):
        """実行（改良版）"""
        input_text = self.input_text.toPlainText().strip()
        if not input_text:
            QMessageBox.warning(self, "入力エラー", "入力欄が空です")
            return
        
        # 大規模テキスト警告
        if len(input_text) > 50000:
            reply = QMessageBox.question(
                self,
                "大規模テキスト",
                "入力テキストが大きいため処理に時間がかかる可能性があります。\n続行しますか？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # プリセット自動検出
        preset_id = self.preset_combo.currentData()
        if not preset_id:
            detected = PresetManager.detect_preset(input_text)
            if detected:
                preset = PresetManager.get_preset(detected)
                self.log_text.appendPlainText(f"📋 自動検出: {preset['name']}")
                if self.logger:
                    self.logger.info(f"プリセット自動検出: {preset['name']}")
        
        # モデル選択
        model = self.model_combo.currentData()
        
        # UI更新
        self.execute_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 無限ループ
        self.status_bar.showMessage("🔄 処理中...")
        self.output_text.clear()
        
        # 実行開始時刻
        self._execution_start = datetime.now()
        
        # ワーカースレッド開始（改良版）
        self.worker = LLMWorker(
            self.router_path,
            input_text,
            None if model == "auto" else model,
            config={'timeout': 120}
        )
        self.worker.finished.connect(self.on_execution_finished)
        self.worker.error.connect(self.on_execution_error)
        self.worker.progress.connect(self.on_execution_progress)
        self.worker.start()
    
    def stop_execution(self):
        """実行停止（改良版）"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_bar.showMessage("⏹️ 停止しました")
            if self.logger:
                self.logger.info("実行を停止")
            self.reset_ui_state()
    
    def on_execution_finished(self, result):
        """実行完了時（改良版）"""
        # 大規模テキストは最適化処理
        response = result['response']
        
        if self.optimizer and len(response) > self.optimizer.LARGE_TEXT_THRESHOLD:
            # 非同期で設定
            self.optimizer.optimize_text_edit(self.output_text, response)
        else:
            self.output_text.setPlainText(response)
        
        self.log_text.appendPlainText(f"✅ 完了: {result['model']}")
        
        # メタデータ更新
        duration = result.get('duration', 0)
        self.meta_model.setText(f"モデル: {result['model']}")
        self.meta_time.setText(f"時間: {duration:.1f}s")
        
        # 統計更新
        self.update_stats(result)
        
        if self.logger:
            self.logger.info("実行完了", model=result['model'], duration=duration)
        
        self.reset_ui_state()
    
    def on_execution_error(self, error_msg):
        """実行エラー時（改良版）"""
        self.output_text.setPlainText(f"❌ エラー:\n{error_msg}")
        self.log_text.appendPlainText(f"❌ エラー: {error_msg}")
        
        # 改良版エラーハンドリング
        if self.error_handler:
            try:
                # エラーメッセージから例外を再構築して処理
                error = Exception(error_msg)
                self.error_handler.handle_error(error, context="LLMリクエスト実行中")
            except Exception:
                pass
        
        if self.logger:
            self.logger.error("実行エラー", error=error_msg)
        
        self.reset_ui_state()
    
    def on_execution_progress(self, message):
        """実行進捗"""
        self.status_bar.showMessage(message)
        self.log_text.appendPlainText(message)
    
    def reset_ui_state(self):
        """UI状態をリセット"""
        self.execute_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.progress.setVisible(False)
        self.status_bar.showMessage("✅ 準備完了")
    
    def update_stats(self, result):
        """統計更新"""
        self.session_stats['requests'] += 1
        
        if result.get('model') == 'local':
            self.session_stats['local'] += 1
        else:
            self.session_stats['cloud'] += 1
        
        # UI更新
        self.stat_requests.setText(f"リクエスト: {self.session_stats['requests']}")
        self.stat_local.setText(f"🟢 ローカル: {self.session_stats['local']}")
        self.stat_cloud.setText(f"🔵 クラウド: {self.session_stats['cloud']}")
        
        # ダッシュボード更新
        self.dashboard.update_stats(self.session_stats)
    
    def check_api_key(self):
        """APIキー確認"""
        key_manager = SecureKeyManager()
        if not key_manager.get_api_key('anthropic'):
            reply = QMessageBox.question(
                self,
                "APIキー未設定",
                "Anthropic APIキーが設定されていません。\n"
                "今すぐ設定しますか？\n\n"
                "※APIキーはWindowsの暗号化ストレージに安全に保存されます。",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.open_settings()
    
    def open_settings(self):
        """設定ダイアログを開く"""
        dialog = SettingsDialog(self)
        dialog.exec()
    
    def open_router_config(self):
        """ルーター設定を開く"""
        config_path = os.path.join(self.router_path, 'config.yaml')
        if os.path.exists(config_path):
            subprocess.Popen(['notepad', config_path])
        else:
            QMessageBox.warning(self, "エラー", "config.yamlが見つかりません")
    
    def show_full_stats(self):
        """詳細統計を表示"""
        self.dashboard.show_full_dialog()
    
    def reset_stats(self):
        """統計をリセット"""
        self.session_stats = {
            'requests': 0,
            'local': 0,
            'cloud': 0,
            'tokens_in': 0,
            'tokens_out': 0,
            'cost': 0.0,
            'start_time': datetime.now()
        }
        self.stat_requests.setText("リクエスト: 0")
        self.stat_local.setText("🟢 ローカル: 0")
        self.stat_cloud.setText("🔵 クラウド: 0")
        self.stat_cost.setText("💰 コスト: ¥0")
        self.dashboard.reset()
        QMessageBox.information(self, "統計リセット", "セッション統計をリセットしました")
    
    def clear_input(self):
        """入力をクリア"""
        self.input_text.clear()
    
    def paste_clipboard(self):
        """クリップボードから貼り付け"""
        clipboard = QApplication.clipboard()
        self.input_text.setPlainText(clipboard.text())
    
    def load_file(self):
        """ファイルを読み込む"""
        path, _ = QFileDialog.getOpenFileName(
            self, "ファイルを開く", "",
            "テキストファイル (*.txt);;Markdown (*.md);;すべて (*.*)"
        )
        if path:
            try:
                # 大規模ファイル警告
                size = os.path.getsize(path)
                if size > 1024 * 1024:  # 1MB超
                    reply = QMessageBox.question(
                        self, "大きなファイル",
                        f"ファイルサイズが {size/1024/1024:.1f}MB です。\n読み込みますか？",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return
                
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 大規模テキストは最適化処理
                if self.optimizer and len(content) > self.optimizer.LARGE_TEXT_THRESHOLD:
                    self.optimizer.optimize_text_edit(self.input_text, content)
                else:
                    self.input_text.setPlainText(content)
                
                self.status_bar.showMessage(f"📂 読み込み完了: {path}")
                if self.logger:
                    self.logger.info(f"ファイル読み込み: {path}")
                    
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"読み込み失敗: {str(e)}")
                if self.error_handler:
                    self.error_handler.handle_error(e, context="ファイル読み込み中")
    
    def copy_output(self):
        """出力をコピー"""
        QApplication.clipboard().setText(self.output_text.toPlainText())
        self.status_bar.showMessage("📋 コピーしました", 2000)
    
    def save_output(self):
        """出力を保存"""
        path, _ = QFileDialog.getSaveFileName(
            self, "保存", f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "テキストファイル (*.txt);;Markdown (*.md)"
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.toPlainText())
                self.status_bar.showMessage(f"💾 保存完了: {path}", 3000)
                if self.logger:
                    self.logger.info(f"出力保存: {path}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"保存失敗: {str(e)}")
    
    def zoom_in(self):
        """フォント拡大"""
        if self.shortcut_manager:
            self.shortcut_manager._increase_font()
    
    def zoom_out(self):
        """フォント縮小"""
        if self.shortcut_manager:
            self.shortcut_manager._decrease_font()
    
    def zoom_reset(self):
        """フォントリセット"""
        if self.shortcut_manager:
            self.shortcut_manager._reset_font()
    
    def show_shortcuts(self):
        """ショートカット一覧を表示"""
        if self.shortcut_manager:
            from gui.performance_optimizer import QuickHelpDialog
            dialog = QuickHelpDialog(self)
            dialog.exec()
    
    def show_logs(self):
        """ログを表示"""
        if not self.logger:
            QMessageBox.information(self, "ログ", "ログ機能が有効になっていません")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("📜 アプリケーションログ")
        dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        
        logs = self.logger.get_memory_logs(limit=100)
        for log in logs:
            line = f"[{log['timestamp']}] {log['level']}: {log['message']}"
            log_text.append(line)
        
        layout.addWidget(log_text)
        
        buttons = QHBoxLayout()
        
        export_btn = QPushButton("📤 エクスポート")
        export_btn.clicked.connect(lambda: self.export_logs(dialog))
        buttons.addWidget(export_btn)
        
        buttons.addStretch()
        
        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(dialog.accept)
        buttons.addWidget(close_btn)
        
        layout.addLayout(buttons)
        
        dialog.exec()
    
    def export_logs(self, parent_dialog):
        """ログをエクスポート"""
        if self.logger:
            path = self.logger.export_logs()
            QMessageBox.information(parent_dialog, "エクスポート完了", f"ログを保存しました:\n{path}")
    
    def show_about(self):
        """バージョン情報"""
        QMessageBox.about(
            self,
            "LLM Smart Router Pro",
            """<h2>LLM Smart Router Pro v2.1</h2>
            <p>ローカルLLMとClaudeをシームレスに切り替える<br>
            インテリジェントルーティングシステム</p>
            <p><b>作者:</b> クラ for 新さん</p>
            <p><b>特徴:</b></p>
            <ul>
                <li>✨ ワンクリックモデル切替</li>
                <li>🔐 APIキー暗号化保存</li>
                <li>📋 用途別プリセット</li>
                <li>📊 統計ダッシュボード</li>
                <li>⚡ パフォーマンス最適化</li>
                <li>🛡️ 強化されたエラーハンドリング</li>
                <li>⌨️ 拡張キーボードショートカット</li>
            </ul>"""
        )
    
    def closeEvent(self, event):
        """終了処理"""
        if self.logger:
            self.logger.info("アプリケーション終了")
        event.accept()


# ============================================================
# PresetManager（元のコードと同じ）
# ============================================================

class PresetManager:
    """用途別プリセット管理"""
    
    PRESETS = {
        'cm_work': {
            'name': '🏗️ CM業務',
            'description': '建設業のコスト管理・見積・工事関連',
            'system_prompt': '''あなたは建設業のプロフェッショナルアシスタントです。
以下の観点で回答してください：
- 建設コストの適正性
- 工事進捗の管理
- 品質管理の観点
- 法令・規制への対応
- 安全衛生管理''',
            'icon': '🏗️',
            'default_model': 'cloud',
            'keywords': ['コスト', '見積', '工事', '施主', '建設']
        },
        'oshi_support': {
            'name': '💎 推し活',
            'description': 'KONO・mina・りぃなど推しのサポート',
            'system_prompt': '''あなたは熱心なファンをサポートするアシスタントです。
以下の観点で回答してください：
- 配信スケジュールの最適化
- 応援コメントの作成
- SNSマーケティング
- ファンコミュニティ運営
- コンテンツ企画''',
            'icon': '💎',
            'default_model': 'cloud',
            'keywords': ['配信', 'ライブ', '推し', 'ファン', '応援']
        },
        'coding': {
            'name': '💻 コーディング',
            'description': 'コード生成・レビュー・デバッグ',
            'system_prompt': '''あなたはエキスパートプログラマーです。
以下の基準で回答してください：
- クリーンコードの原則
- セキュリティベストプラクティス
- パフォーマンス最適化
- 可読性と保守性
- 適切なコメント''',
            'icon': '💻',
            'default_model': 'auto',
            'keywords': ['コード', 'バグ', 'エラー', '関数', 'API']
        },
        'writing': {
            'name': '✍️ 文章作成',
            'description': 'ビジネス文書・SNS投稿・ブログ',
            'system_prompt': '''あなたはプロのライターです。
以下の観点で文章を作成してください：
- 明確で簡潔な表現
- 適切なトーンとスタイル
- 論理的な構成
- 読者を引き込む導入
- 具体的な事例の活用''',
            'icon': '✍️',
            'default_model': 'local',
            'keywords': ['文章', '作成', 'ブログ', 'SNS', '投稿']
        },
        'analysis': {
            'name': '📊 データ分析',
            'description': 'データの分析・可視化・レポート',
            'system_prompt': '''あなたはデータアナリストです。
以下の観点で分析してください：
- 統計的な洞察
- データの可視化提案
- トレンド分析
- 異常値の検出
- ビジネスへの示唆''',
            'icon': '📊',
            'default_model': 'cloud',
            'keywords': ['データ', '分析', 'グラフ', '統計', 'レポート']
        },
        'learning': {
            'name': '📚 学習支援',
            'description': '新しい知識の習得・解説・要約',
            'system_prompt': '''あなたは親しみやすい教師です。
以下の方法で教えてください：
- 段階的な説明
- 具体例の活用
- 類似概念との比較
- 実践的な演習
- 理解度確認の質問''',
            'icon': '📚',
            'default_model': 'local',
            'keywords': ['学習', '教えて', '説明', '理解', 'まとめ']
        }
    }
    
    @classmethod
    def get_preset(cls, preset_id):
        return cls.PRESETS.get(preset_id)
    
    @classmethod
    def get_all_presets(cls):
        return cls.PRESETS
    
    @classmethod
    def detect_preset(cls, text):
        """テキストから適切なプリセットを自動検出"""
        text_lower = text.lower()
        scores = {}
        
        for preset_id, preset in cls.PRESETS.items():
            score = 0
            for keyword in preset['keywords']:
                if keyword.lower() in text_lower:
                    score += 1
            if score > 0:
                scores[preset_id] = score
        
        if scores:
            return max(scores, key=scores.get)
        return None


# ============================================================
# ダークテーマ（元のコードと同じ）
# ============================================================

class DarkTheme:
    """ダークテーマ定義"""
    
    COLORS = {
        'background': '#1e1e1e',
        'surface': '#2d2d2d',
        'surface_light': '#3d3d3d',
        'primary': '#6366f1',
        'primary_light': '#818cf8',
        'secondary': '#10b981',
        'accent': '#f59e0b',
        'danger': '#ef4444',
        'text_primary': '#f9fafb',
        'text_secondary': '#9ca3af',
        'border': '#404040'
    }
    
    @classmethod
    def apply(cls, app):
        """アプリ全体にダークテーマを適用"""
        app.setStyle('Fusion')
        
        palette = QPalette()
        colors = cls.COLORS
        
        palette.setColor(QPalette.Window, QColor(colors['background']))
        palette.setColor(QPalette.WindowText, QColor(colors['text_primary']))
        palette.setColor(QPalette.Base, QColor(colors['surface']))
        palette.setColor(QPalette.AlternateBase, QColor(colors['surface_light']))
        palette.setColor(QPalette.ToolTipBase, QColor(colors['surface']))
        palette.setColor(QPalette.ToolTipText, QColor(colors['text_primary']))
        palette.setColor(QPalette.Text, QColor(colors['text_primary']))
        palette.setColor(QPalette.Button, QColor(colors['surface']))
        palette.setColor(QPalette.ButtonText, QColor(colors['text_primary']))
        palette.setColor(QPalette.BrightText, QColor(colors['primary']))
        palette.setColor(QPalette.Highlight, QColor(colors['primary']))
        palette.setColor(QPalette.HighlightedText, QColor(colors['text_primary']))
        
        app.setPalette(palette)
        
        app.setStyleSheet(f'''
            QMainWindow {{ background-color: {colors['background']}; }}
            QGroupBox {{ font-weight: bold; border: 1px solid {colors['border']}; 
                        border-radius: 8px; margin-top: 12px; padding: 12px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 8px; 
                               color: {colors['primary_light']}; }}
            QPushButton {{ background-color: {colors['surface_light']}; color: {colors['text_primary']}; 
                          border: 1px solid {colors['border']}; border-radius: 6px; 
                          padding: 8px 16px; font-weight: 500; }}
            QPushButton:hover {{ background-color: {colors['surface']}; border-color: {colors['primary']}; }}
            QPushButton:pressed {{ background-color: {colors['primary']}; }}
            QPushButton#primary {{ background-color: {colors['primary']}; border: none; }}
            QPushButton#primary:hover {{ background-color: {colors['primary_light']}; }}
            QPushButton#danger {{ background-color: {colors['danger']}; border: none; }}
            QComboBox, QLineEdit {{ background-color: {colors['surface']}; color: {colors['text_primary']}; 
                                   border: 1px solid {colors['border']}; border-radius: 6px; padding: 6px; }}
            QTextEdit, QPlainTextEdit {{ background-color: {colors['surface']}; color: {colors['text_primary']}; 
                                        border: 1px solid {colors['border']}; border-radius: 6px; 
                                        padding: 8px; selection-background-color: {colors['primary']}; }}
            QLabel#status {{ color: {colors['secondary']}; font-weight: 500; }}
        ''')


# ============================================================
# メイン
# ============================================================

def main():
    app = QApplication(sys.argv)
    
    # ダークテーマ適用
    DarkTheme.apply(app)
    
    # メインウィンドウ（改良版）
    window = ImprovedMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
