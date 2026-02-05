#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
設定ダイアログ
APIキー管理、ルーター設定、プリセット編集
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QFormLayout, QLineEdit, QPushButton,
    QLabel, QMessageBox, QGroupBox, QCheckBox,
    QSpinBox, QDoubleSpinBox, QTextEdit, QFileDialog,
    QDialogButtonBox, QComboBox, QProgressBar,
    QListWidget, QListWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont

# 親ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))
from security.key_manager import SecureKeyManager


class SettingsDialog(QDialog):
    """設定ダイアログ"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 設定")
        self.setMinimumSize(600, 500)
        
        self.key_manager = SecureKeyManager()
        self.settings = QSettings('LLMSmartRouter', 'Pro')
        
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """UI初期化"""
        layout = QVBoxLayout(self)
        
        # タブウィジェット
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # APIキータブ
        self.tabs.addTab(self.create_api_tab(), "🔐 APIキー")
        
        # ルーター設定タブ
        self.tabs.addTab(self.create_router_tab(), "⚙️ ルーター")
        
        # プリセットタブ
        self.tabs.addTab(self.create_preset_tab(), "📋 プリセット")

        # 優先順位タブ
        self.tabs.addTab(self.create_priority_tab(), "📊 優先順位")
        
        # ボタンボックス
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def create_api_tab(self):
        """APIキー設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 説明
        desc = QLabel(
            "🔒 APIキーはWindows/macOSの標準キーストアに\n"
            "暗号化されて安全に保存されます。"
        )
        desc.setStyleSheet("color: #10b981; padding: 10px;")
        layout.addWidget(desc)
        
        # Anthropic APIキー
        anthropic_group = QGroupBox("☁️ Anthropic (Claude)")
        anthropic_layout = QFormLayout(anthropic_group)
        
        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.Password)
        self.anthropic_key.setPlaceholderText("sk-ant-api03-...")
        anthropic_layout.addRow("APIキー:", self.anthropic_key)
        
        # キー確認ボタン
        key_buttons = QHBoxLayout()
        
        self.show_key_btn = QPushButton("👁️ 表示")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self.toggle_key_visibility)
        key_buttons.addWidget(self.show_key_btn)
        
        self.test_key_btn = QPushButton("🧪 接続テスト")
        self.test_key_btn.clicked.connect(self.test_anthropic_key)
        key_buttons.addWidget(self.test_key_btn)
        
        self.delete_key_btn = QPushButton("🗑️ 削除")
        self.delete_key_btn.clicked.connect(self.delete_anthropic_key)
        key_buttons.addWidget(self.delete_key_btn)
        
        key_buttons.addStretch()
        anthropic_layout.addRow("", key_buttons)
        
        layout.addWidget(anthropic_group)
        
        # OpenAI APIキー（将来拡張用）
        openai_group = QGroupBox("🤖 OpenAI (将来拡張)")
        openai_layout = QFormLayout(openai_group)
        
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.Password)
        self.openai_key.setPlaceholderText("sk-...")
        self.openai_key.setEnabled(False)
        openai_layout.addRow("APIキー:", self.openai_key)
        
        self.openai_key.setStyleSheet("background-color: #2d2d2d; color: #666;")
        
        layout.addWidget(openai_group)
        
        # セキュリティ情報
        security_info = QGroupBox("🛡️ セキュリティ情報")
        security_layout = QFormLayout(security_info)
        
        self.keyring_status = QLabel("確認中...")
        security_layout.addRow("キーストア:", self.keyring_status)
        
        self.backend_label = QLabel("-")
        security_layout.addRow("バックエンド:", self.backend_label)
        
        layout.addWidget(security_info)
        
        layout.addStretch()
        
        return widget
    
    def create_router_tab(self):
        """ルーター設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # パス設定
        path_group = QGroupBox("📁 パス設定")
        path_layout = QFormLayout(path_group)
        
        self.router_path = QLineEdit()
        self.router_path.setText(self.settings.value('router_path', 'F:\\llm-smart-router'))
        
        path_buttons = QHBoxLayout()
        path_buttons.addWidget(self.router_path)
        
        browse_btn = QPushButton("📂 参照")
        browse_btn.clicked.connect(self.browse_router_path)
        path_buttons.addWidget(browse_btn)
        
        path_layout.addRow("ルーターパス:", path_buttons)
        
        layout.addWidget(path_group)
        
        # デフォルト設定
        default_group = QGroupBox("⚙️ デフォルト設定")
        default_layout = QFormLayout(default_group)
        
        self.default_model = QComboBox()
        self.default_model.addItem("🧠 自動判定", "auto")
        self.default_model.addItem("🏠 ローカル", "local")
        self.default_model.addItem("☁️ クラウド", "cloud")
        default_layout.addRow("デフォルトモデル:", self.default_model)
        
        self.confidence_threshold = QDoubleSpinBox()
        self.confidence_threshold.setRange(0.0, 1.0)
        self.confidence_threshold.setSingleStep(0.05)
        self.confidence_threshold.setValue(0.75)
        default_layout.addRow("確信度閾値:", self.confidence_threshold)
        
        layout.addWidget(default_group)
        
        # コスト設定
        cost_group = QGroupBox("💰 コスト管理")
        cost_layout = QFormLayout(cost_group)
        
        self.cost_notify = QCheckBox("有効")
        self.cost_notify.setChecked(True)
        cost_layout.addRow("コスト通知:", self.cost_notify)
        
        self.cost_threshold = QSpinBox()
        self.cost_threshold.setRange(1, 1000)
        self.cost_threshold.setSuffix(" ¥")
        self.cost_threshold.setValue(50)
        cost_layout.addRow("通知閾値:", self.cost_threshold)
        
        layout.addWidget(cost_group)
        
        # パフォーマンス設定
        perf_group = QGroupBox("🚀 パフォーマンス")
        perf_layout = QFormLayout(perf_group)
        
        self.local_timeout = QSpinBox()
        self.local_timeout.setRange(10, 300)
        self.local_timeout.setSuffix(" 秒")
        self.local_timeout.setValue(30)
        perf_layout.addRow("ローカルタイムアウト:", self.local_timeout)
        
        self.cloud_timeout = QSpinBox()
        self.cloud_timeout.setRange(10, 300)
        self.cloud_timeout.setSuffix(" 秒")
        self.cloud_timeout.setValue(60)
        perf_layout.addRow("クラウドタイムアウト:", self.cloud_timeout)
        
        layout.addWidget(perf_group)
        
        layout.addStretch()
        
        return widget
    
    def create_preset_tab(self):
        """プリセット設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        desc = QLabel("📋 用途別プリセットのカスタマイズ")
        desc.setStyleSheet("color: #6366f1; padding: 10px;")
        layout.addWidget(desc)
        
        # プリセット選択
        preset_layout = QHBoxLayout()
        
        preset_layout.addWidget(QLabel("プリセット:"))
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("🏗️ CM業務", "cm_work")
        self.preset_combo.addItem("💎 推し活", "oshi_support")
        self.preset_combo.addItem("💻 コーディング", "coding")
        self.preset_combo.addItem("✍️ 文章作成", "writing")
        self.preset_combo.currentIndexChanged.connect(self.load_preset)
        preset_layout.addWidget(self.preset_combo)
        
        preset_layout.addStretch()
        layout.addLayout(preset_layout)
        
        # システムプロンプト編集
        self.preset_prompt = QTextEdit()
        self.preset_prompt.setPlaceholderText("システムプロンプトを入力...")
        layout.addWidget(QLabel("システムプロンプト:"))
        layout.addWidget(self.preset_prompt)
        
        # デフォルトモデル
        self.preset_model = QComboBox()
        self.preset_model.addItem("🧠 自動", "auto")
        self.preset_model.addItem("🏠 ローカル", "local")
        self.preset_model.addItem("☁️ クラウド", "cloud")
        layout.addWidget(QLabel("デフォルトモデル:"))
        layout.addWidget(self.preset_model)
        
        # ボタン
        buttons = QHBoxLayout()
        
        save_preset_btn = QPushButton("💾 保存")
        save_preset_btn.clicked.connect(self.save_preset)
        buttons.addWidget(save_preset_btn)
        
        reset_preset_btn = QPushButton("🔄 リセット")
        reset_preset_btn.clicked.connect(self.reset_preset)
        buttons.addWidget(reset_preset_btn)
        
        buttons.addStretch()
        layout.addLayout(buttons)
        
        layout.addStretch()
        
        # 初期読み込み
        self.load_preset()
        
        return widget
    
    def load_settings(self):
        """設定を読み込み"""
        # APIキー状態確認
        try:
            if self.key_manager.get_api_key('anthropic'):
                self.anthropic_key.setPlaceholderText("✅ 保存済み（変更する場合のみ入力）")
                self.anthropic_key.clear()
            
            backend = self.key_manager.get_backend()
            self.backend_label.setText(backend)
            self.keyring_status.setText("✅ 利用可能")
            self.keyring_status.setStyleSheet("color: #10b981;")
            
        except Exception as e:
            self.keyring_status.setText(f"❌ エラー: {str(e)}")
            self.keyring_status.setStyleSheet("color: #ef4444;")
    
    def toggle_key_visibility(self, checked):
        """APIキー表示切替"""
        if checked:
            self.anthropic_key.setEchoMode(QLineEdit.Normal)
            self.show_key_btn.setText("🙈 隠す")
        else:
            self.anthropic_key.setEchoMode(QLineEdit.Password)
            self.show_key_btn.setText("👁️ 表示")
    
    def test_anthropic_key(self):
        """Anthropic APIキーのテスト"""
        import requests
        
        key = self.anthropic_key.text().strip()
        if not key:
            # 保存済みキーを使用
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
                QMessageBox.information(self, "成功", "✅ APIキーは有効です！")
            else:
                QMessageBox.warning(
                    self, "エラー",
                    f"❌ APIエラー: {response.status_code}\n{response.text[:200]}"
                )
                
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"❌ 接続失敗: {str(e)}")
        
        finally:
            self.test_key_btn.setEnabled(True)
            self.test_key_btn.setText("🧪 接続テスト")
    
    def delete_anthropic_key(self):
        """Anthropic APIキーを削除"""
        reply = QMessageBox.question(
            self, "確認",
            "保存済みのAPIキーを削除しますか？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.key_manager.delete_api_key('anthropic'):
                QMessageBox.information(self, "成功", "APIキーを削除しました")
                self.anthropic_key.setPlaceholderText("sk-ant-api03-...")
                self.anthropic_key.clear()
            else:
                QMessageBox.warning(self, "エラー", "削除に失敗しました")
    
    def browse_router_path(self):
        """ルーターパス参照"""
        path = QFileDialog.getExistingDirectory(
            self, "ルーターディレクトリを選択",
            self.router_path.text()
        )
        if path:
            self.router_path.setText(path)
    
    def load_preset(self):
        """プリセットを読み込み"""
        preset_id = self.preset_combo.currentData()
        
        # デフォルトのプリセット内容
        presets = {
            'cm_work': {
                'prompt': '''あなたは建設業のプロフェッショナルアシスタントです。
以下の観点で回答してください：
- 建設コストの適正性
- 工事進捗の管理
- 品質管理の観点
- 法令・規制への対応
- 安全衛生管理''',
                'model': 'cloud'
            },
            'oshi_support': {
                'prompt': '''あなたは熱心なファンをサポートするアシスタントです。
以下の観点で回答してください：
- 配信スケジュールの最適化
- 応援コメントの作成
- SNSマーケティング
- ファンコミュニティ運営
- コンテンツ企画''',
                'model': 'cloud'
            },
            'coding': {
                'prompt': '''あなたはエキスパートプログラマーです。
以下の基準で回答してください：
- クリーンコードの原則
- セキュリティベストプラクティス
- パフォーマンス最適化
- 可読性と保守性
- 適切なコメント''',
                'model': 'auto'
            },
            'writing': {
                'prompt': '''あなたはプロのライターです。
以下の観点で文章を作成してください：
- 明確で簡潔な表現
- 適切なトーンとスタイル
- 論理的な構成
- 読者を引き込む導入
- 具体的な事例の活用''',
                'model': 'local'
            }
        }
        
        preset = presets.get(preset_id, {})
        self.preset_prompt.setText(preset.get('prompt', ''))
        
        model = preset.get('model', 'auto')
        index = self.preset_model.findData(model)
        if index >= 0:
            self.preset_model.setCurrentIndex(index)
    
    def save_preset(self):
        """プリセットを保存"""
        QMessageBox.information(
            self, "保存",
            "プリセット設定を保存しました（メモリ上）\n"
            "永続化するにはconfig.yamlを編集してください。"
        )
    
    def reset_preset(self):
        """プリセットをリセット"""
        self.load_preset()
        QMessageBox.information(self, "リセット", "デフォルト設定に戻しました")
    
    def _get_project_root(self):
        """プロジェクトルートパスを取得"""
        return Path(__file__).resolve().parent.parent.parent

    def _get_priority_path(self):
        """fallback_priority.json のパス"""
        return self._get_project_root() / "data" / "fallback_priority.json"

    def create_priority_tab(self):
        """優先順位設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        desc = QLabel(
            "Autoモードでモデルが失敗した場合のフォールバック順序を設定します。\n"
            "上から順に試行し、成功したらそのモデルの応答を返します。"
        )
        desc.setStyleSheet("color: #6366f1; padding: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # リストウィジェット + ボタン
        list_row = QHBoxLayout()

        self.priority_list = QListWidget()
        self.priority_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.priority_list.setDefaultDropAction(Qt.MoveAction)
        self.priority_list.setStyleSheet(
            "QListWidget { background: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a;"
            " border-radius: 6px; font-size: 13px; padding: 4px; }"
            " QListWidget::item { padding: 6px 8px; border-radius: 4px; }"
            " QListWidget::item:selected { background: #45475a; }"
        )
        list_row.addWidget(self.priority_list)

        # 上/下/削除ボタン
        btn_col = QVBoxLayout()
        btn_col.addStretch()

        up_btn = QPushButton("↑ 上へ")
        up_btn.setFixedWidth(80)
        up_btn.clicked.connect(self._priority_move_up)
        btn_col.addWidget(up_btn)

        down_btn = QPushButton("↓ 下へ")
        down_btn.setFixedWidth(80)
        down_btn.clicked.connect(self._priority_move_down)
        btn_col.addWidget(down_btn)

        btn_col.addSpacing(20)

        reset_btn = QPushButton("🔄 リセット")
        reset_btn.setFixedWidth(80)
        reset_btn.clicked.connect(self._priority_reset)
        btn_col.addWidget(reset_btn)

        btn_col.addStretch()
        list_row.addLayout(btn_col)

        layout.addLayout(list_row)

        # 現在の優先順位プレビュー
        self.priority_preview = QLabel("")
        self.priority_preview.setStyleSheet("color: #a6adc8; font-size: 12px; padding: 8px;")
        self.priority_preview.setWordWrap(True)
        layout.addWidget(self.priority_preview)
        self.priority_list.model().rowsMoved.connect(self._update_priority_preview)

        # 読み込み
        self._load_priority_list()

        return widget

    def _load_priority_list(self):
        """レジストリとfallback_priority.jsonから優先順位リストを構築"""
        self.priority_list.clear()

        # 現在の優先順位を読み込み
        priority_path = self._get_priority_path()
        current_priority = None
        if priority_path.exists():
            try:
                data = json.loads(priority_path.read_text(encoding="utf-8"))
                if isinstance(data.get("priority"), list):
                    current_priority = data["priority"]
            except (json.JSONDecodeError, OSError):
                pass

        # レジストリからモデル一覧を取得
        available_models = self._get_available_model_refs()

        if current_priority:
            # 保存済み順序で表示し、新しいモデルは末尾に追加
            seen = set()
            for ref in current_priority:
                self._add_priority_item(ref)
                seen.add(ref)
            for ref in available_models:
                if ref not in seen:
                    self._add_priority_item(ref)
                    seen.add(ref)  # 追加したら必ずseenに記録
        else:
            # デフォルト: 全ローカルモデル → cloud（重複排除）
            seen = set()
            for ref in available_models:
                if ref not in seen:
                    self._add_priority_item(ref)
                    seen.add(ref)

        self._update_priority_preview()

    def _get_available_model_refs(self):
        """レジストリから利用可能なモデル参照リストを返す"""
        refs = []
        registry_path = self._get_project_root() / "data" / "model_registry.json"
        if registry_path.exists():
            try:
                data = json.loads(registry_path.read_text(encoding="utf-8"))
                models = data.get("models", {})
                for key, model_list in models.items():
                    if key == "cloud":
                        continue
                    if isinstance(model_list, list):
                        for m in model_list:
                            mid = m.get("id", "")
                            if mid and not mid.startswith("text-embedding"):
                                refs.append(f"local:{mid}")
            except (json.JSONDecodeError, OSError):
                pass
        # cloudを末尾に追加
        refs.append("cloud")
        return refs

    def _add_priority_item(self, model_ref):
        """モデル参照をリストに追加"""
        if model_ref.startswith("local:"):
            model_id = model_ref[len("local:"):]
            # 短い表示名
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
        """選択項目を上に移動"""
        row = self.priority_list.currentRow()
        if row > 0:
            item = self.priority_list.takeItem(row)
            self.priority_list.insertItem(row - 1, item)
            self.priority_list.setCurrentRow(row - 1)
            self._update_priority_preview()

    def _priority_move_down(self):
        """選択項目を下に移動"""
        row = self.priority_list.currentRow()
        if row < self.priority_list.count() - 1:
            item = self.priority_list.takeItem(row)
            self.priority_list.insertItem(row + 1, item)
            self.priority_list.setCurrentRow(row + 1)
            self._update_priority_preview()

    def _priority_reset(self):
        """デフォルト順序にリセット"""
        self._load_priority_list()

    def _update_priority_preview(self):
        """プレビューラベルを更新"""
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
        """リストウィジェットから優先順位のmodel_refリストを取得"""
        refs = []
        for i in range(self.priority_list.count()):
            item = self.priority_list.item(i)
            ref = item.data(Qt.UserRole)
            if ref:
                refs.append(ref)
        return refs

    def _save_priority(self):
        """優先順位をfallback_priority.jsonに保存"""
        refs = self._get_priority_order()
        if not refs:
            return

        priority_path = self._get_priority_path()
        data = {
            "priority": refs,
            "updated_at": datetime.now().isoformat()
        }

        # アトミック書き込み
        try:
            priority_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                dir=str(priority_path.parent), suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, str(priority_path))
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as e:
            QMessageBox.warning(self, "エラー", f"優先順位の保存に失敗: {e}")

    def save_settings(self):
        """設定を保存"""
        # APIキー保存
        anthropic_key = self.anthropic_key.text().strip()
        if anthropic_key:
            try:
                self.key_manager.set_api_key('anthropic', anthropic_key)
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"APIキー保存失敗: {str(e)}")
                return
        
        # ルーターパス保存
        self.settings.setValue('router_path', self.router_path.text())
        
        # デフォルトモデル保存
        self.settings.setValue('default_model', self.default_model.currentData())

        # 優先順位保存
        self._save_priority()

        QMessageBox.information(self, "保存完了", "設定を保存しました")
        self.accept()


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # ダークテーマ適用（簡易版）
    app.setStyle('Fusion')
    
    dialog = SettingsDialog()
    dialog.show()
    
    sys.exit(app.exec())
