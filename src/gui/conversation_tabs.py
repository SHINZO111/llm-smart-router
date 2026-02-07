#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Smart Router - 会話タブ管理
複数会話のタブ表示と切り替え機能を提供
"""

from typing import Callable, List, Optional, Dict
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTabBar,
    QLabel, QPushButton, QMenu, QToolButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QIcon, QFont, QCursor


# ============================================================
# タブデータモデル
# ============================================================

@dataclass
class TabInfo:
    """タブ情報"""
    id: str
    title: str
    model: str
    is_modified: bool = False
    is_loading: bool = False
    
    @property
    def display_title(self) -> str:
        """表示用タイトル"""
        title = self.title if self.title.strip() else "Untitled"
        if self.is_modified:
            title = f"● {title}"
        return title
    
    @property
    def model_icon(self) -> str:
        """モデルアイコン"""
        icons = {
            'claude': '🌐',
            'cloud': '🌐',
            'local': '💻',
            'auto': '🤖',
        }
        return icons.get(self.model.lower(), '🤖')


# ============================================================
# カスタムタブバー
# ============================================================

class ConversationTabBar(QTabBar):
    """カスタムタブバー（閉じるボタン付き）"""
    tabCloseRequestedMiddleClick = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(False)
        self.setMovable(True)
        self.setTabsClosable(True)
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideRight)
        
        # スタイル設定
        self.setStyleSheet("""
            QTabBar::tab {
                background-color: #161625;
                color: #94a3b8;
                border: 1px solid #252540;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 16px;
                min-width: 120px;
                max-width: 200px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e2e;
                color: #eef2ff;
                border-color: #6366f1;
            }
            QTabBar::tab:hover:!selected {
                background-color: #1c1c30;
                color: #eef2ff;
            }
            QTabBar::close-button {
                image: none;
                subcontrol-position: right;
                subcontrol-origin: padding;
                margin-left: 4px;
            }
            QTabBar::close-button:hover {
                background-color: #ef4444;
                border-radius: 4px;
            }
        """)
    
    def mousePressEvent(self, event):
        """マウスプレスイベント（中クリックで閉じる）"""
        if event.button() == Qt.MiddleButton:
            index = self.tabAt(event.pos())
            if index >= 0:
                self.tabCloseRequestedMiddleClick.emit(index)
                return
        super().mousePressEvent(event)
    
    def tabSizeHint(self, index):
        """タブサイズヒント"""
        size = super().tabSizeHint(index)
        size.setHeight(36)
        return size


# ============================================================
# 会話タブコンテナ
# ============================================================

class ConversationTabContent(QWidget):
    """タブ内の会話コンテンツ（メッセージ表示・コピー対応）"""

    def __init__(self, conversation_id: str, parent=None):
        super().__init__(parent)
        self.conversation_id = conversation_id
        self._messages: list = []  # (role, content, model, timestamp)
        self._setup_ui()

    def _setup_ui(self):
        from PySide6.QtWidgets import QTextEdit, QScrollArea

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # メッセージ表示用テキストエリア（読み取り専用）
        self._text_display = QTextEdit()
        self._text_display.setReadOnly(True)
        self._text_display.setStyleSheet("""
            QTextEdit {
                background-color: #0a0a0f;
                color: #eef2ff;
                border: none;
                font-family: "Segoe UI", "Yu Gothic UI", "Meiryo", sans-serif;
                font-size: 13px;
                padding: 16px;
                selection-background-color: #6366f1;
            }
        """)
        self._text_display.setPlaceholderText("Conversation content will appear here...")
        layout.addWidget(self._text_display, 1)

    def add_message(self, role: str, content: str, model: str = "", timestamp: str = ""):
        """メッセージを追加して表示を更新"""
        self._messages.append((role, content, model, timestamp))
        self._render_messages()

    def _render_messages(self):
        """全メッセージを再描画"""
        html_parts = []
        for role, content, model, ts in self._messages:
            if role == "user":
                label = '<span style="color: #6366f1; font-weight: bold;">You</span>'
            elif role == "assistant":
                model_tag = f' <span style="color: #64748b; font-size: 11px;">({model})</span>' if model else ""
                label = f'<span style="color: #10b981; font-weight: bold;">Assistant</span>{model_tag}'
            else:
                label = f'<span style="color: #f59e0b; font-weight: bold;">{role}</span>'

            # コンテンツのHTMLエスケープ
            escaped = (content
                       .replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;")
                       .replace("\n", "<br>"))

            html_parts.append(
                f'<div style="margin-bottom: 16px;">'
                f'<div style="margin-bottom: 4px;">{label}</div>'
                f'<div style="color: #cbd5e1; line-height: 1.6;">{escaped}</div>'
                f'</div>'
            )

        self._text_display.setHtml("".join(html_parts))
        # 末尾にスクロール
        sb = self._text_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def get_content(self) -> str:
        """全会話をプレーンテキストで取得（コピー用）"""
        lines = []
        for role, content, model, ts in self._messages:
            prefix = "You" if role == "user" else f"Assistant ({model})" if model else "Assistant"
            lines.append(f"[{prefix}]\n{content}\n")
        return "\n".join(lines)

    def clear_messages(self):
        """メッセージをクリア"""
        self._messages.clear()
        self._text_display.clear()


# ============================================================
# 会話タブウィジェット
# ============================================================

class ConversationTabWidget(QTabWidget):
    """会話タブ管理ウィジェット"""
    
    # シグナル
    tab_conversation_switched = Signal(str)  # conversation_id
    tab_conversation_closed = Signal(str)  # conversation_id
    tab_conversation_new_requested = Signal()
    tab_conversation_close_others_requested = Signal(str)  # conversation_id
    tab_conversation_close_all_requested = Signal()
    tab_conversation_close_right_requested = Signal(str)  # conversation_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs: Dict[str, int] = {}  # conversation_id -> tab_index
        self._tab_infos: Dict[int, TabInfo] = {}  # tab_index -> TabInfo
        
        self._setup_ui()
    
    def _setup_ui(self):
        """UIセットアップ"""
        # カスタムタブバー
        self._tab_bar = ConversationTabBar(self)
        self._tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tab_bar.tabCloseRequestedMiddleClick.connect(self._on_tab_close_requested)
        self.setTabBar(self._tab_bar)
        
        # タブ設定
        self.setDocumentMode(True)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setElideMode(Qt.ElideRight)
        
        # スタイル
        self.setStyleSheet("""
            QTabWidget::pane {
                background-color: #0a0a0f;
                border: 1px solid #252540;
                border-radius: 0 10px 10px 10px;
                top: -1px;
            }
            QTabWidget::tab-bar {
                left: 8px;
            }
        """)
        
        # 新規タブボタン
        self._new_tab_btn = QToolButton()
        self._new_tab_btn.setText("+")
        self._new_tab_btn.setToolTip("New Conversation")
        self._new_tab_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                color: #94a3b8;
                border: 1px solid #252540;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #6366f1;
                color: white;
                border-color: #6366f1;
            }
        """)
        self._new_tab_btn.setCursor(Qt.PointingHandCursor)
        self._new_tab_btn.clicked.connect(self.tab_conversation_new_requested.emit)
        self.setCornerWidget(self._new_tab_btn, Qt.TopLeftCorner)
        
        # タブ切り替えシグナル
        self.currentChanged.connect(self._on_current_changed)
        
        # コンテキストメニュー
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_tab_context_menu)
        self._tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tab_bar.customContextMenuRequested.connect(self._show_tab_bar_context_menu)
    
    def _on_current_changed(self, index: int):
        """タブ切り替え時"""
        if index >= 0 and index in self._tab_infos:
            tab_info = self._tab_infos[index]
            self.tab_conversation_switched.emit(tab_info.id)
    
    def _on_tab_close_requested(self, index: int):
        """タブ閉じるリクエスト時"""
        self.close_tab_at(index)
    
    def _show_tab_context_menu(self, position):
        """タブコンテキストメニュー"""
        index = self.tabBar().tabAt(position)
        if index < 0:
            return
        
        self._show_context_menu_at(index, self.mapToGlobal(position))
    
    def _show_tab_bar_context_menu(self, position):
        """タブバーコンテキストメニュー"""
        index = self._tab_bar.tabAt(position)
        if index < 0:
            return
        
        self._show_context_menu_at(index, self._tab_bar.mapToGlobal(position))
    
    def _show_context_menu_at(self, index: int, global_pos):
        """指定位置にコンテキストメニューを表示"""
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
        
        tab_info = self._tab_infos.get(index)
        if not tab_info:
            return
        
        # 閉じるアクション
        close_action = QAction("✕ Close", self)
        close_action.triggered.connect(lambda: self.close_tab_at(index))
        menu.addAction(close_action)
        
        close_others_action = QAction("Close Others", self)
        close_others_action.triggered.connect(lambda: self.tab_conversation_close_others_requested.emit(tab_info.id))
        menu.addAction(close_others_action)
        
        close_right_action = QAction("Close to the Right", self)
        close_right_action.triggered.connect(lambda: self.tab_conversation_close_right_requested.emit(tab_info.id))
        menu.addAction(close_right_action)
        
        menu.addSeparator()
        
        close_all_action = QAction("Close All", self)
        close_all_action.triggered.connect(self.tab_conversation_close_all_requested.emit)
        menu.addAction(close_all_action)
        
        menu.exec(global_pos)
    
    # ── パブリックメソッド ──
    
    def add_conversation_tab(self, conversation_id: str, title: str = "Untitled", 
                            model: str = "auto") -> int:
        """会話タブを追加"""
        # 既存のタブがあればそれを返す
        if conversation_id in self._tabs:
            index = self._tabs[conversation_id]
            self.setCurrentIndex(index)
            return index
        
        # タブ情報作成
        tab_info = TabInfo(conversation_id, title, model)
        
        # コンテンツ作成
        content = ConversationTabContent(conversation_id)
        
        # タブ追加
        index = self.addTab(content, tab_info.display_title)
        self._tabs[conversation_id] = index
        self._tab_infos[index] = tab_info
        
        # 現在のタブに設定
        self.setCurrentIndex(index)
        
        return index
    
    def close_tab_at(self, index: int) -> bool:
        """指定インデックスのタブを閉じる"""
        if index < 0 or index >= self.count():
            return False
        
        tab_info = self._tab_infos.get(index)
        if not tab_info:
            return False
        
        # 未保存の変更がある場合は確認
        if tab_info.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f'"{tab_info.title}" has unsaved changes.\nClose anyway?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return False
        
        # タブを削除
        conversation_id = tab_info.id
        self.removeTab(index)
        
        # インデックスを更新
        del self._tabs[conversation_id]
        del self._tab_infos[index]
        
        # 残りのインデックスを調整
        new_tabs = {}
        new_infos = {}
        for cid, idx in self._tabs.items():
            if idx > index:
                new_tabs[cid] = idx - 1
            else:
                new_tabs[cid] = idx
        
        for idx, info in self._tab_infos.items():
            if idx > index:
                new_infos[idx - 1] = info
            else:
                new_infos[idx] = info
        
        self._tabs = new_tabs
        self._tab_infos = new_infos
        
        # シグナル発行
        self.tab_conversation_closed.emit(conversation_id)
        
        return True
    
    def close_tab(self, conversation_id: str) -> bool:
        """会話IDでタブを閉じる"""
        if conversation_id not in self._tabs:
            return False
        
        index = self._tabs[conversation_id]
        return self.close_tab_at(index)
    
    def close_all_tabs_except(self, conversation_id: str):
        """指定会話以外の全タブを閉じる"""
        ids_to_close = [cid for cid in self._tabs.keys() if cid != conversation_id]
        for cid in ids_to_close:
            self.close_tab(cid)
    
    def close_all_tabs_to_right(self, conversation_id: str):
        """指定会話の右側の全タブを閉じる"""
        if conversation_id not in self._tabs:
            return
        
        current_index = self._tabs[conversation_id]
        ids_to_close = [
            cid for cid, idx in self._tabs.items() 
            if idx > current_index
        ]
        for cid in ids_to_close:
            self.close_tab(cid)
    
    def close_all_tabs(self):
        """全タブを閉じる"""
        ids_to_close = list(self._tabs.keys())
        for cid in ids_to_close:
            self.close_tab(cid)
    
    def switch_to_tab(self, conversation_id: str) -> bool:
        """指定会話のタブに切り替え"""
        if conversation_id not in self._tabs:
            return False
        
        index = self._tabs[conversation_id]
        self.setCurrentIndex(index)
        return True
    
    def update_tab_title(self, conversation_id: str, title: str):
        """タブタイトルを更新"""
        if conversation_id not in self._tabs:
            return
        
        index = self._tabs[conversation_id]
        if index in self._tab_infos:
            self._tab_infos[index].title = title
            self.setTabText(index, self._tab_infos[index].display_title)
    
    def update_tab_model(self, conversation_id: str, model: str):
        """タブのモデルを更新"""
        if conversation_id not in self._tabs:
            return
        
        index = self._tabs[conversation_id]
        if index in self._tab_infos:
            self._tab_infos[index].model = model
            # アイコン更新（必要に応じて）
    
    def set_tab_modified(self, conversation_id: str, modified: bool):
        """タブの変更状態を設定"""
        if conversation_id not in self._tabs:
            return
        
        index = self._tabs[conversation_id]
        if index in self._tab_infos:
            self._tab_infos[index].is_modified = modified
            self.setTabText(index, self._tab_infos[index].display_title)
    
    def set_tab_loading(self, conversation_id: str, loading: bool):
        """タブのローディング状態を設定"""
        if conversation_id not in self._tabs:
            return
        
        index = self._tabs[conversation_id]
        if index in self._tab_infos:
            self._tab_infos[index].is_loading = loading
            # ローディングアニメーション（必要に応じて）
    
    def get_current_conversation_id(self) -> Optional[str]:
        """現在の会話IDを取得"""
        index = self.currentIndex()
        if index >= 0 and index in self._tab_infos:
            return self._tab_infos[index].id
        return None
    
    def get_all_open_conversations(self) -> List[str]:
        """開いている全ての会話IDを取得"""
        return list(self._tabs.keys())
    
    def has_tab(self, conversation_id: str) -> bool:
        """指定会話のタブが存在するか"""
        return conversation_id in self._tabs
    
    def get_tab_index(self, conversation_id: str) -> int:
        """会話IDからタブインデックスを取得"""
        return self._tabs.get(conversation_id, -1)
    
    def get_tab_count(self) -> int:
        """タブ数を取得"""
        return self.count()


# ============================================================
# テスト用
# ============================================================

if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # スタイル設定
    app.setStyleSheet("""
        QWidget {
            font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
            background-color: #0a0a0f;
            color: #eef2ff;
        }
    """)
    
    tabs = ConversationTabWidget()
    tabs.resize(800, 600)
    
    # テストタブ追加
    tabs.add_conversation_tab("conv1", "Python Discussion", "claude")
    tabs.add_conversation_tab("conv2", "Cost Analysis", "local")
    tabs.add_conversation_tab("conv3", "Untitled", "auto")
    
    # シグナル接続
    tabs.tab_conversation_switched.connect(lambda cid: print(f"Switched to: {cid}"))
    tabs.tab_conversation_closed.connect(lambda cid: print(f"Closed: {cid}"))
    tabs.tab_conversation_new_requested.connect(lambda: tabs.add_conversation_tab(f"conv{tabs.get_tab_count()+1}", f"New Tab {tabs.get_tab_count()+1}"))
    
    tabs.show()
    
    sys.exit(app.exec())
