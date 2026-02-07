#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
再利用可能UIコンポーネント

全GUIファイルで共通利用するウィジェット群。
design_tokens.py のトークンを使用して一貫したスタイルを実現。
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import (
    QColor, QPainter, QLinearGradient, QBrush, QPen,
    QRadialGradient, QPainterPath, QFont
)

from gui.design_tokens import Colors, Spacing, Radius, Typography


# ============================================================
# セクションヘッダー
# ============================================================

class SectionHeader(QWidget):
    """統一セクション見出し"""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Spacing.SM, 0, Spacing.SM)
        layout.setSpacing(Spacing.XS)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {Colors.TEXT};"
            f" font-size: {Typography.SIZE_LG}px;"
            f" font-weight: {Typography.WEIGHT_SEMIBOLD};"
            f" letter-spacing: -0.3px;"
        )
        layout.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet(
                f"color: {Colors.TEXT_MUTED};"
                f" font-size: {Typography.SIZE_SM}px;"
            )
            sub_label.setWordWrap(True)
            layout.addWidget(sub_label)


# ============================================================
# ステータスインジケーター
# ============================================================

class StatusIndicator(QWidget):
    """ランタイム状態ドット + ラベル"""

    def __init__(self, color: str = Colors.STATUS_UNKNOWN, label: str = "", parent=None):
        super().__init__(parent)
        self._color = color
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)

        self._dot = QWidget()
        self._dot.setFixedSize(10, 10)
        self._update_dot_style()
        layout.addWidget(self._dot)

        self._label = QLabel(label)
        self._label.setStyleSheet(
            f"color: {Colors.TEXT_DIM};"
            f" font-size: {Typography.SIZE_SM}px;"
        )
        layout.addWidget(self._label)
        layout.addStretch()

    def set_status(self, color: str, label: str = ""):
        self._color = color
        self._update_dot_style()
        if label:
            self._label.setText(label)

    def _update_dot_style(self):
        self._dot.setStyleSheet(
            f"background-color: {self._color};"
            f" border-radius: 5px;"
            f" border: 2px solid {self._color}40;"
        )


# ============================================================
# 設定ソースバッジ
# ============================================================

class ConfigSourceBadge(QWidget):
    """設定の保存先とリロード要否を示すバッジ"""

    # ソースタイプ定数
    YAML = "yaml"
    ENV = "env"
    JSON = "json"
    KEYSTORE = "keystore"

    _SOURCE_CONFIG = {
        "yaml": (Colors.CONFIG_YAML, "YAML", "即時反映"),
        "env": (Colors.CONFIG_ENV, ".env", "要再起動"),
        "json": (Colors.CONFIG_JSON, "JSON", "即時反映"),
        "keystore": (Colors.CONFIG_KEYSTORE, "OS", "即時反映"),
    }

    def __init__(self, source: str, live: bool = True, parent=None):
        super().__init__(parent)
        color, text, reload_text = self._SOURCE_CONFIG.get(
            source, (Colors.TEXT_MUTED, "?", "")
        )
        if not live:
            reload_text = "要再起動"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.XS)

        badge = QLabel(text)
        badge.setStyleSheet(
            f"background-color: {color}20;"
            f" color: {color};"
            f" font-size: {Typography.SIZE_XS}px;"
            f" font-weight: {Typography.WEIGHT_SEMIBOLD};"
            f" padding: 1px 6px;"
            f" border-radius: {Radius.SM}px;"
            f" border: 1px solid {color}40;"
        )
        badge.setFixedHeight(18)
        layout.addWidget(badge)

        if reload_text:
            reload_label = QLabel(reload_text)
            reload_color = Colors.STATUS_ONLINE if live else Colors.STATUS_WARNING
            reload_label.setStyleSheet(
                f"color: {reload_color};"
                f" font-size: {Typography.SIZE_XS}px;"
            )
            layout.addWidget(reload_label)


# ============================================================
# アクションボタン
# ============================================================

class ActionButton(QPushButton):
    """統一スタイルのアクションボタン

    variant:
        'primary' - プライマリアクション (インディゴ背景)
        'danger'  - 危険なアクション (レッド背景)
        'ghost'   - ゴーストボタン (透明背景、ボーダーのみ)
        'success' - 成功アクション (グリーン背景)
    """

    def __init__(self, text: str, variant: str = "primary", icon_text: str = "", parent=None):
        display = f"{icon_text} {text}".strip() if icon_text else text
        super().__init__(display, parent)
        self._variant = variant
        self._apply_style()

    def _apply_style(self):
        styles = {
            "primary": {
                "bg": Colors.PRIMARY,
                "bg_hover": Colors.PRIMARY_LIGHT,
                "text": "#ffffff",
                "border": "none",
            },
            "danger": {
                "bg": Colors.DANGER,
                "bg_hover": "#f87171",
                "text": "#ffffff",
                "border": "none",
            },
            "ghost": {
                "bg": "transparent",
                "bg_hover": f"{Colors.PRIMARY}15",
                "text": Colors.TEXT_DIM,
                "border": f"1px solid {Colors.BORDER}",
            },
            "success": {
                "bg": Colors.SECONDARY,
                "bg_hover": Colors.SECONDARY_LIGHT,
                "text": "#ffffff",
                "border": "none",
            },
        }
        s = styles.get(self._variant, styles["primary"])
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {s['bg']};
                color: {s['text']};
                border: {s['border']};
                border-radius: {Radius.MD}px;
                padding: {Spacing.SM}px {Spacing.LG}px;
                font-size: {Typography.SIZE_MD}px;
                font-weight: {Typography.WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: {s['bg_hover']};
            }}
            QPushButton:pressed {{
                opacity: 0.8;
            }}
            QPushButton:disabled {{
                opacity: 0.4;
            }}
        """)


# ============================================================
# カードウィジェット
# ============================================================

class CardWidget(QFrame):
    """統一カードウィジェット (GlowCard/StatCard を統合)"""

    def __init__(self, title: str = "", accent_color: str = Colors.PRIMARY, parent=None):
        super().__init__(parent)
        self._accent = accent_color
        self._hovered = False

        self.setStyleSheet(
            f"CardWidget {{"
            f"  background-color: {Colors.SURFACE_2};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: {Radius.LG}px;"
            f"  border-left: 3px solid {accent_color};"
            f"}}"
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        self._layout.setSpacing(Spacing.SM)

        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet(
                f"color: {Colors.TEXT};"
                f" font-size: {Typography.SIZE_MD}px;"
                f" font-weight: {Typography.WEIGHT_SEMIBOLD};"
                f" background: transparent;"
                f" border: none;"
            )
            self._layout.addWidget(title_label)

    def content_layout(self) -> QVBoxLayout:
        """カード内にウィジェットを追加するためのレイアウトを返す"""
        return self._layout

    def enterEvent(self, event):
        self._hovered = True
        self.setStyleSheet(
            f"CardWidget {{"
            f"  background-color: {Colors.SURFACE_3};"
            f"  border: 1px solid {self._accent}40;"
            f"  border-radius: {Radius.LG}px;"
            f"  border-left: 3px solid {self._accent};"
            f"}}"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.setStyleSheet(
            f"CardWidget {{"
            f"  background-color: {Colors.SURFACE_2};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: {Radius.LG}px;"
            f"  border-left: 3px solid {self._accent};"
            f"}}"
        )
        super().leaveEvent(event)


# ============================================================
# 設定フィールドラッパー
# ============================================================

class ConfigField(QWidget):
    """フォームフィールド + ラベル + ソースバッジのラッパー"""

    def __init__(
        self,
        label: str,
        widget: QWidget,
        source: str = "",
        live: bool = True,
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Spacing.XS, 0, Spacing.XS)
        layout.setSpacing(Spacing.XS)

        # ヘッダー行: ラベル + ソースバッジ
        header = QHBoxLayout()
        header.setSpacing(Spacing.SM)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {Colors.TEXT_DIM};"
            f" font-size: {Typography.SIZE_SM}px;"
            f" font-weight: {Typography.WEIGHT_MEDIUM};"
        )
        header.addWidget(lbl)
        header.addStretch()

        if source:
            badge = ConfigSourceBadge(source, live=live)
            header.addWidget(badge)

        layout.addLayout(header)

        # ウィジェット本体
        layout.addWidget(widget)

        if tooltip:
            self.setToolTip(tooltip)


# ============================================================
# エンプティステート
# ============================================================

class EmptyState(QWidget):
    """リストが空の時の表示"""

    action_clicked = Signal()

    def __init__(
        self,
        icon: str = "",
        title: str = "",
        description: str = "",
        action_text: str = "",
        parent=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)
        layout.setAlignment(Qt.AlignCenter)

        if icon:
            icon_label = QLabel(icon)
            icon_label.setStyleSheet(f"font-size: 48px; color: {Colors.TEXT_MUTED};")
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)

        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet(
                f"color: {Colors.TEXT_DIM};"
                f" font-size: {Typography.SIZE_LG}px;"
                f" font-weight: {Typography.WEIGHT_SEMIBOLD};"
            )
            title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet(
                f"color: {Colors.TEXT_MUTED};"
                f" font-size: {Typography.SIZE_MD}px;"
            )
            desc_label.setAlignment(Qt.AlignCenter)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        if action_text:
            layout.addSpacing(Spacing.MD)
            btn = ActionButton(action_text, variant="primary")
            btn.clicked.connect(self.action_clicked.emit)
            layout.addWidget(btn, alignment=Qt.AlignCenter)


# ============================================================
# ナビゲーションリストアイテム (設定サイドナビ用)
# ============================================================

class NavListItem(QWidget):
    """サイドナビゲーションのアイテム"""

    clicked = Signal()

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self._selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        layout.setSpacing(Spacing.SM)

        self._icon_label = QLabel(icon)
        self._icon_label.setStyleSheet(f"font-size: 16px; background: transparent; border: none;")
        layout.addWidget(self._icon_label)

        self._text_label = QLabel(label)
        self._text_label.setStyleSheet(
            f"color: {Colors.TEXT_DIM};"
            f" font-size: {Typography.SIZE_MD}px;"
            f" font-weight: {Typography.WEIGHT_MEDIUM};"
            f" background: transparent; border: none;"
        )
        layout.addWidget(self._text_label)
        layout.addStretch()

        self._update_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(
                f"NavListItem {{"
                f"  background-color: {Colors.PRIMARY}15;"
                f"  border-radius: {Radius.MD}px;"
                f"  border-left: 3px solid {Colors.PRIMARY};"
                f"}}"
            )
            self._text_label.setStyleSheet(
                f"color: {Colors.TEXT};"
                f" font-size: {Typography.SIZE_MD}px;"
                f" font-weight: {Typography.WEIGHT_SEMIBOLD};"
                f" background: transparent; border: none;"
            )
        else:
            self.setStyleSheet(
                f"NavListItem {{"
                f"  background-color: transparent;"
                f"  border-radius: {Radius.MD}px;"
                f"  border-left: 3px solid transparent;"
                f"}}"
            )
            self._text_label.setStyleSheet(
                f"color: {Colors.TEXT_DIM};"
                f" font-size: {Typography.SIZE_MD}px;"
                f" font-weight: {Typography.WEIGHT_MEDIUM};"
                f" background: transparent; border: none;"
            )

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        if not self._selected:
            self.setStyleSheet(
                f"NavListItem {{"
                f"  background-color: {Colors.SURFACE_3};"
                f"  border-radius: {Radius.MD}px;"
                f"  border-left: 3px solid transparent;"
                f"}}"
            )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._update_style()
        super().leaveEvent(event)
