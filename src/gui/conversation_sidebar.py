#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Smart Router - 会話サイドバー
会話一覧の表示、検索、フィルタ機能を提供
"""

from datetime import datetime, timedelta
from typing import Callable, List, Optional
from dataclasses import dataclass, field

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QScrollArea, QFrame, QMenu,
    QMessageBox, QInputDialog, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QFont, QColor


# ============================================================
# データモデル
# ============================================================

@dataclass
class ConversationItem:
    """会話アイテムのデータモデル"""
    id: str
    title: str
    date: datetime
    model: str
    message_count: int = 0
    is_pinned: bool = False
    is_archived: bool = False
    tags: List[str] = field(default_factory=list)
    
    @property
    def model_icon(self) -> str:
        """モデルアイコンを返す"""
        icons = {
            'claude': '🌐',
            'cloud': '🌐',
            'local': '💻',
            'auto': '🤖',
            'gpt4': '🌐',
            'gpt3': '🌐',
        }
        return icons.get(self.model.lower(), '🤖')
    
    @property
    def display_title(self) -> str:
        """表示用タイトル（空の場合はUntitled）"""
        return self.title if self.title.strip() else "Untitled"
    
    @property
    def date_display(self) -> str:
        """表示用日付"""
        today = datetime.now().date()
        item_date = self.date.date()
        
        if item_date == today:
            return self.date.strftime("%H:%M")
        elif item_date == today - timedelta(days=1):
            return "Yesterday"
        elif item_date > today - timedelta(days=7):
            return self.date.strftime("%a")
        else:
            return self.date.strftime("%m/%d")


# ============================================================
# 会話リストアイテムウィジェット
# ============================================================

class ConversationListItem(QFrame):
    """会話リストの個別アイテム"""
    clicked = Signal(str)  # conversation_id
    doubleClicked = Signal(str)
    contextMenuRequested = Signal(str, object)  # conversation_id, position
    
    def __init__(self, conversation: ConversationItem, parent=None):
        super().__init__(parent)
        self.conversation_id = conversation.id
        self.conversation = conversation
        self._is_selected = False
        
        self._setup_ui()
        self._update_style()
    
    def _setup_ui(self):
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.NoFrame)
        
        # メインレイアウト
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # モデルアイコン
        self.icon_label = QLabel(self.conversation.model_icon)
        self.icon_label.setStyleSheet("font-size: 14px;")
        self.icon_label.setFixedWidth(24)
        layout.addWidget(self.icon_label)
        
        # 中央コンテンツ
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # タイトル行
        title_layout = QHBoxLayout()
        title_layout.setSpacing(4)
        
        self.title_label = QLabel(self.conversation.display_title)
        self.title_label.setStyleSheet("font-weight: 500; font-size: 13px;")
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        title_layout.addWidget(self.title_label)
        
        # ピン表示
        if self.conversation.is_pinned:
            pin_label = QLabel("📌")
            pin_label.setStyleSheet("font-size: 10px;")
            title_layout.addWidget(pin_label)
        
        content_layout.addLayout(title_layout)
        
        # サブ情報行
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)
        
        date_label = QLabel(f"{self.conversation.date_display} • {self.conversation.message_count} msgs")
        date_label.setStyleSheet("color: #64748b; font-size: 11px;")
        info_layout.addWidget(date_label)
        
        # モデル名
        model_label = QLabel(self.conversation.model.capitalize())
        model_label.setStyleSheet("color: #6366f1; font-size: 10px; background: #6366f120; padding: 1px 6px; border-radius: 4px;")
        info_layout.addWidget(model_label)
        
        info_layout.addStretch()
        content_layout.addLayout(info_layout)
        
        layout.addLayout(content_layout, 1)
    
    def _update_style(self):
        """スタイルを更新"""
        if self._is_selected:
            bg = "#6366f1"
            border = "#6366f1"
            title_color = "#ffffff"
        else:
            bg = "transparent"
            border = "transparent"
            title_color = "#eef2ff"
        
        self.setStyleSheet(f"""
            ConversationListItem {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            ConversationListItem:hover {{
                background-color: {'#6366f130' if not self._is_selected else bg};
                border-color: {'#6366f1' if not self._is_selected else border};
            }}
        """)
        self.title_label.setStyleSheet(f"font-weight: 500; font-size: 13px; color: {title_color};")
    
    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._update_style()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.conversation_id)
    
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(self.conversation_id)
    
    def contextMenuEvent(self, event):
        self.contextMenuRequested.emit(self.conversation_id, event.globalPos())


# ============================================================
# 会話サイドバー
# ============================================================

class ConversationSidebar(QWidget):
    """会話一覧サイドバー"""
    
    # シグナル
    conversation_selected = Signal(str)  # conversation_id
    conversation_double_clicked = Signal(str)  # conversation_id
    conversation_new_requested = Signal()
    conversation_delete_requested = Signal(str)  # conversation_id
    conversation_rename_requested = Signal(str, str)  # conversation_id, new_title
    conversation_pin_requested = Signal(str, bool)  # conversation_id, is_pinned
    conversation_archive_requested = Signal(str, bool)  # conversation_id, is_archived
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conversations: List[ConversationItem] = []
        self.filtered_conversations: List[ConversationItem] = []
        self.selected_id: Optional[str] = None
        self.item_widgets: dict[str, ConversationListItem] = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ── ヘッダー ──
        header = QWidget()
        header.setStyleSheet("background-color: #161625; border-bottom: 1px solid #252540;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(10)
        
        # タイトル行
        title_row = QHBoxLayout()
        title_label = QLabel("💬 Conversations")
        title_label.setStyleSheet("color: #818cf8; font-size: 14px; font-weight: 700;")
        title_row.addWidget(title_label)
        title_row.addStretch()
        
        # 新規会話ボタン
        self.new_btn = QPushButton("+ New")
        self.new_btn.setToolTip("新しい会話を作成（Ctrl+N）")
        self.new_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #818cf8;
            }
        """)
        self.new_btn.setCursor(Qt.PointingHandCursor)
        self.new_btn.clicked.connect(self.conversation_new_requested.emit)
        title_row.addWidget(self.new_btn)
        header_layout.addLayout(title_row)
        
        # ── 検索ボックス ──
        search_container = QFrame()
        search_container.setStyleSheet("""
            QFrame {
                background-color: #12121f;
                border: 1px solid #252540;
                border-radius: 8px;
            }
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(8, 4, 8, 4)
        search_layout.setSpacing(6)
        
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("color: #64748b;")
        search_layout.addWidget(search_icon)
        
        self.search_input = QLineEdit()
        self.search_input.setToolTip("会話タイトルで検索")
        self.search_input.setPlaceholderText("Search conversations...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #eef2ff;
                font-size: 13px;
                padding: 4px 0;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input, 1)
        
        self.clear_search_btn = QPushButton("✕")
        self.clear_search_btn.setToolTip("検索をクリア")
        self.clear_search_btn.setFixedSize(20, 20)
        self.clear_search_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #64748b;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #ef4444;
            }
        """)
        self.clear_search_btn.setVisible(False)
        self.clear_search_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self.clear_search_btn)
        
        header_layout.addWidget(search_container)
        
        # ── フィルター ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        
        # 日付フィルター
        self.date_filter = QComboBox()
        self.date_filter.setToolTip("期間で会話をフィルタ")
        self.date_filter.addItems(["All Time", "Today", "Yesterday", "This Week", "This Month"])
        self.date_filter.setStyleSheet("""
            QComboBox {
                background-color: #12121f;
                color: #94a3b8;
                border: 1px solid #252540;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background-color: #161625;
                color: #eef2ff;
                border: 1px solid #252540;
            }
        """)
        self.date_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.date_filter)
        
        # モデルフィルター
        self.model_filter = QComboBox()
        self.model_filter.setToolTip("使用モデルで会話をフィルタ")
        self.model_filter.addItems(["All Models", "Claude", "Local", "Auto"])
        self.model_filter.setStyleSheet(self.date_filter.styleSheet())
        self.model_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.model_filter)
        
        filter_row.addStretch()
        header_layout.addLayout(filter_row)
        
        # 会話カウント
        self.count_label = QLabel("0 conversations")
        self.count_label.setStyleSheet("color: #64748b; font-size: 11px;")
        header_layout.addWidget(self.count_label)
        
        layout.addWidget(header)
        
        # ── 会話リスト ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #10101a;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #252540;
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6366f1;
            }
        """)
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(8, 8, 8, 8)
        self.list_layout.setSpacing(4)
        self.list_layout.addStretch()
        
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll, 1)
        
        self.setMinimumWidth(220)
        self.setMaximumWidth(400)
    
    def _on_search_changed(self, text: str):
        """検索テキスト変更時"""
        self.clear_search_btn.setVisible(bool(text))
        self._apply_filters()
    
    def _clear_search(self):
        """検索をクリア"""
        self.search_input.clear()
        self.clear_search_btn.setVisible(False)
    
    def _apply_filters(self):
        """フィルターを適用"""
        search_text = self.search_input.text().lower()
        date_filter = self.date_filter.currentText()
        model_filter = self.model_filter.currentText()
        
        filtered = self.conversations.copy()
        
        # 検索フィルター
        if search_text:
            filtered = [c for c in filtered if search_text in c.title.lower()]
        
        # 日付フィルター
        today = datetime.now().date()
        if date_filter == "Today":
            filtered = [c for c in filtered if c.date.date() == today]
        elif date_filter == "Yesterday":
            filtered = [c for c in filtered if c.date.date() == today - timedelta(days=1)]
        elif date_filter == "This Week":
            filtered = [c for c in filtered if c.date.date() >= today - timedelta(days=7)]
        elif date_filter == "This Month":
            filtered = [c for c in filtered if c.date.date().month == today.month]
        
        # モデルフィルター
        if model_filter != "All Models":
            filtered = [c for c in filtered if model_filter.lower() in c.model.lower()]
        
        # ピン留めを先頭に
        filtered.sort(key=lambda c: (not c.is_pinned, c.date), reverse=True)
        
        self.filtered_conversations = filtered
        self._refresh_list()
    
    def _refresh_list(self):
        """リスト表示を更新"""
        # 既存のアイテムを削除
        for widget in self.item_widgets.values():
            widget.deleteLater()
        self.item_widgets.clear()
        
        # アイテムを再作成（stretchを残して先頭から順に除去）
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        
        for conv in self.filtered_conversations:
            item_widget = ConversationListItem(conv)
            item_widget.clicked.connect(self._on_item_clicked)
            item_widget.doubleClicked.connect(self._on_item_double_clicked)
            item_widget.contextMenuRequested.connect(self._show_context_menu)
            
            if conv.id == self.selected_id:
                item_widget.set_selected(True)
            
            self.item_widgets[conv.id] = item_widget
            self.list_layout.insertWidget(self.list_layout.count() - 1, item_widget)
        
        # カウント更新
        self.count_label.setText(f"{len(self.filtered_conversations)} conversations")
    
    def _on_item_clicked(self, conversation_id: str):
        """アイテムクリック時"""
        self.select_conversation(conversation_id)
        self.conversation_selected.emit(conversation_id)
    
    def _on_item_double_clicked(self, conversation_id: str):
        """アイテムダブルクリック時"""
        self.conversation_double_clicked.emit(conversation_id)
    
    def _show_context_menu(self, conversation_id: str, position):
        """コンテキストメニュー表示"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161625;
                color: #eef2ff;
                border: 1px solid #252540;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #6366f1;
            }
        """)
        
        # 会話を探す
        conv = next((c for c in self.conversations if c.id == conversation_id), None)
        if not conv:
            return
        
        # アクション追加
        open_action = QAction("📂 Open", self)
        open_action.triggered.connect(lambda: self.conversation_selected.emit(conversation_id))
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        pin_action = QAction("📌 Unpin" if conv.is_pinned else "📌 Pin", self)
        pin_action.triggered.connect(lambda: self.conversation_pin_requested.emit(conversation_id, not conv.is_pinned))
        menu.addAction(pin_action)
        
        rename_action = QAction("✏️ Rename", self)
        rename_action.triggered.connect(lambda: self._rename_conversation(conversation_id))
        menu.addAction(rename_action)
        
        menu.addSeparator()
        
        delete_action = QAction("🗑️ Delete", self)
        delete_action.triggered.connect(lambda: self._confirm_delete(conversation_id))
        menu.addAction(delete_action)
        
        menu.exec(position)
    
    def _rename_conversation(self, conversation_id: str):
        """会話名を変更"""
        conv = next((c for c in self.conversations if c.id == conversation_id), None)
        if not conv:
            return
        
        new_title, ok = QInputDialog.getText(
            self, "Rename Conversation", "New title:",
            text=conv.title
        )
        if ok and new_title:
            self.conversation_rename_requested.emit(conversation_id, new_title)
    
    def _confirm_delete(self, conversation_id: str):
        """削除確認"""
        reply = QMessageBox.question(
            self, "Delete Conversation",
            "Are you sure you want to delete this conversation?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.conversation_delete_requested.emit(conversation_id)
    
    # ── パブリックメソッド ──
    
    def set_conversations(self, conversations: List[ConversationItem]):
        """会話リストを設定"""
        self.conversations = conversations
        self._apply_filters()
    
    def add_conversation(self, conversation: ConversationItem):
        """会話を追加"""
        self.conversations.append(conversation)
        self._apply_filters()
    
    def update_conversation(self, conversation_id: str, **kwargs):
        """会話を更新"""
        conv = next((c for c in self.conversations if c.id == conversation_id), None)
        if conv:
            for key, value in kwargs.items():
                if hasattr(conv, key):
                    setattr(conv, key, value)
            self._apply_filters()
    
    def remove_conversation(self, conversation_id: str):
        """会話を削除"""
        self.conversations = [c for c in self.conversations if c.id != conversation_id]
        if self.selected_id == conversation_id:
            self.selected_id = None
        self._apply_filters()
    
    def select_conversation(self, conversation_id: str):
        """会話を選択"""
        # 前の選択を解除
        if self.selected_id and self.selected_id in self.item_widgets:
            self.item_widgets[self.selected_id].set_selected(False)
        
        self.selected_id = conversation_id
        
        # 新しい選択を設定
        if conversation_id in self.item_widgets:
            self.item_widgets[conversation_id].set_selected(True)
    
    def get_selected_conversation(self) -> Optional[ConversationItem]:
        """選択中の会話を取得"""
        if not self.selected_id:
            return None
        return next((c for c in self.conversations if c.id == self.selected_id), None)
    
    def clear_selection(self):
        """選択をクリア"""
        if self.selected_id and self.selected_id in self.item_widgets:
            self.item_widgets[self.selected_id].set_selected(False)
        self.selected_id = None


# ============================================================
# テスト用
# ============================================================

if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # テストデータ
    sidebar = ConversationSidebar()
    
    test_conversations = [
        ConversationItem("1", "Python Code Review", datetime.now(), "claude", 12, is_pinned=True),
        ConversationItem("2", "Cost Analysis Q1", datetime.now() - timedelta(hours=2), "local", 8),
        ConversationItem("3", "Untitled", datetime.now() - timedelta(days=1), "auto", 3),
        ConversationItem("4", "Blog Post Ideas", datetime.now() - timedelta(days=2), "claude", 25),
        ConversationItem("5", "API Documentation", datetime.now() - timedelta(days=3), "cloud", 15),
        ConversationItem("6", "Debug Session", datetime.now() - timedelta(days=5), "local", 42, is_pinned=True),
        ConversationItem("7", "Meeting Notes", datetime.now() - timedelta(days=10), "claude", 7),
    ]
    
    sidebar.set_conversations(test_conversations)
    sidebar.show()
    
    sys.exit(app.exec())
