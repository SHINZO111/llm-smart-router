#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統計ダッシュボード
リアルタイム統計表示、グラフ、履歴管理
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QTextEdit, QPushButton,
    QFileDialog, QMessageBox, QGridLayout, QFrame
)
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QPainter, QColor, QFont, QPen

from gui.design_tokens import Colors, Spacing, Radius, Typography, L10n


class CircularProgress(QWidget):
    """円形プログレスバー"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.title = title
        self.value = 0
        self.max_value = 100
        self.color = QColor(Colors.PRIMARY)
        self.setMinimumSize(120, 150)
    
    def set_value(self, value, max_value=100):
        self.value = min(value, max_value)
        self.max_value = max_value
        self.update()
    
    def set_color(self, color):
        self.color = QColor(color)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 外円
        pen = QPen(QColor(Colors.BORDER))
        pen.setWidth(8)
        painter.setPen(pen)
        painter.drawArc(20, 20, 80, 80, 0, 360 * 16)

        # プログレス円
        pen = QPen(self.color)
        pen.setWidth(8)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        angle = int((self.value / self.max_value) * 360 * 16) if self.max_value > 0 else 0
        painter.drawArc(20, 20, 80, 80, 90 * 16, -angle)

        # テキスト
        painter.setPen(QColor(Colors.TEXT))
        font = QFont(Typography.FAMILY.split(',')[0].strip('"'), Typography.SIZE_LG, QFont.Bold)
        painter.setFont(font)

        text = f"{int((self.value / self.max_value) * 100)}%" if self.max_value > 0 else "0%"
        text_rect = painter.boundingRect(0, 0, 0, 0, Qt.AlignCenter, text)
        text_x = (width - text_rect.width()) // 2
        text_y = 70
        painter.drawText(text_x, text_y, text)

        # タイトル
        font.setPointSize(Typography.SIZE_XS)
        font.setBold(False)
        painter.setFont(font)
        title_rect = painter.boundingRect(0, 0, 0, 0, Qt.AlignCenter, self.title)
        title_x = (width - title_rect.width()) // 2
        painter.drawText(title_x, 125, self.title)


class BarChart(QWidget):
    """簡易バーチャート"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.title = title
        self.data = []
        self.colors = [Colors.PRIMARY, Colors.SECONDARY, Colors.ACCENT, Colors.DANGER]
        self.setMinimumSize(200, 150)
    
    def set_data(self, data):
        """
        data: [(label, value, color), ...]
        """
        self.data = data
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # タイトル
        _font_family = Typography.FAMILY.split(',')[0].strip('"')
        painter.setPen(QColor(Colors.TEXT))
        font = QFont(_font_family, Typography.SIZE_XS, QFont.Bold)
        painter.setFont(font)
        painter.drawText(10, 20, self.title)

        if not self.data:
            return

        # バー描画
        max_val = max(d[1] for d in self.data) if self.data else 1
        bar_width = (width - 40) // len(self.data)

        for i, (label, value, color) in enumerate(self.data):
            x = 20 + i * bar_width
            bar_height = (value / max_val) * (height - 80)
            y = height - 40 - bar_height

            # バー
            painter.fillRect(x, y, bar_width - 10, bar_height, QColor(color))

            # 値
            painter.setPen(QColor(Colors.TEXT))
            painter.setFont(QFont(_font_family, Typography.SIZE_XS - 1))
            value_text = str(int(value))
            text_rect = painter.boundingRect(0, 0, 0, 0, Qt.AlignCenter, value_text)
            painter.drawText(x + (bar_width - 10 - text_rect.width()) // 2, y - 5, value_text)

            # ラベル
            painter.setPen(QColor(Colors.TEXT_DIM))
            painter.setFont(QFont(_font_family, Typography.SIZE_XS - 2))
            label_rect = painter.boundingRect(0, 0, 0, 0, Qt.AlignCenter, label)
            painter.drawText(x + (bar_width - 10 - label_rect.width()) // 2, height - 20, label)


class StatisticsDashboard(QWidget):
    """統計ダッシュボードウィジェット"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('LLMSmartRouter', 'Pro')
        self.session_history = []
        
        self.init_ui()
        self.load_history()
    
    def init_ui(self):
        """UI初期化"""
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.MD)

        # タイトル
        title = QLabel(f"📊 {L10n.DASHBOARD_TITLE}")
        title.setStyleSheet(
            f"font-size: {Typography.SIZE_XL}px; font-weight: bold; color: {Colors.PRIMARY_LIGHT};"
        )
        layout.addWidget(title)

        # === 概要カード ===
        cards_layout = QHBoxLayout()

        # 総リクエスト
        self.total_card = self.create_stat_card("📈 総リクエスト", "0", Colors.PRIMARY)
        cards_layout.addWidget(self.total_card)

        # 節約額
        self.saved_card = self.create_stat_card("💰 節約額", "¥0", Colors.SECONDARY)
        cards_layout.addWidget(self.saved_card)

        # 総コスト
        self.cost_card = self.create_stat_card("☁️ クラウドコスト", "¥0", Colors.ACCENT)
        cards_layout.addWidget(self.cost_card)

        layout.addLayout(cards_layout)

        # === モデル使用状況 ===
        usage_group = QGroupBox("🔄 モデル使用状況")
        usage_layout = QHBoxLayout(usage_group)

        # 円形プログレス
        self.local_progress = CircularProgress("ローカル")
        self.local_progress.set_color(Colors.SECONDARY)
        usage_layout.addWidget(self.local_progress)

        self.cloud_progress = CircularProgress("クラウド")
        self.cloud_progress.set_color(Colors.PRIMARY)
        usage_layout.addWidget(self.cloud_progress)
        
        # バーチャート
        self.usage_chart = BarChart("使用分布")
        usage_layout.addWidget(self.usage_chart)
        
        layout.addWidget(usage_group)
        
        # === パフォーマンス ===
        perf_group = QGroupBox("⚡ パフォーマンス")
        perf_layout = QGridLayout(perf_group)
        
        self.avg_time_local = QLabel("🟢 ローカル平均: -")
        perf_layout.addWidget(self.avg_time_local, 0, 0)
        
        self.avg_time_cloud = QLabel("🔵 クラウド平均: -")
        perf_layout.addWidget(self.avg_time_cloud, 0, 1)
        
        self.token_rate = QLabel("📊 トークン効率: -")
        perf_layout.addWidget(self.token_rate, 1, 0)
        
        self.cost_per_req = QLabel("💵 リクエスト単価: -")
        perf_layout.addWidget(self.cost_per_req, 1, 1)
        
        layout.addWidget(perf_group)
    
    def create_stat_card(self, title, value, color):
        """統計カード作成"""
        card = QFrame()
        card.setStyleSheet(f'''
            QFrame {{
                background-color: {Colors.SURFACE_2};
                border-radius: {Radius.MD}px;
                padding: {Spacing.MD}px;
                border-left: 4px solid {color};
            }}
        ''')

        layout = QVBoxLayout(card)
        layout.setSpacing(Spacing.XS)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {Colors.TEXT_DIM}; font-size: {Typography.SIZE_SM}px;"
        )
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"color: {color}; font-size: {Typography.SIZE_XXL}px; font-weight: bold;"
        )
        value_label.setObjectName(f"value_{title}")
        layout.addWidget(value_label)
        
        # 値を保存
        card.value_label = value_label
        
        return card
    
    def update_stats(self, stats):
        """統計を更新"""
        total = stats.get('requests', 0)
        local = stats.get('local', 0)
        cloud = stats.get('cloud', 0)
        cost = stats.get('cost', 0)
        
        # カード更新
        self.total_card.value_label.setText(str(total))
        
        # 節約額計算（クラウド使用の約70%が節約と仮定）
        saved = local * 5  # 1リクエストあたり¥5節約と仮定
        self.saved_card.value_label.setText(f"¥{saved}")
        
        self.cost_card.value_label.setText(f"¥{cost:.2f}")
        
        # プログレス更新
        if total > 0:
            local_pct = (local / total) * 100
            cloud_pct = (cloud / total) * 100
            
            self.local_progress.set_value(local_pct)
            self.cloud_progress.set_value(cloud_pct)
            
            # チャート更新
            self.usage_chart.set_data([
                ("ローカル", local, Colors.SECONDARY),
                ("クラウド", cloud, Colors.PRIMARY)
            ])
        
        # 履歴に追加
        self.add_history_entry(stats)
    
    def add_history_entry(self, stats):
        """履歴にエントリを追加"""
        entry = {
            'timestamp': datetime.now(),
            'requests': stats.get('requests', 0),
            'local': stats.get('local', 0),
            'cloud': stats.get('cloud', 0),
            'cost': stats.get('cost', 0)
        }
        self.session_history.append(entry)
    
    def load_history(self):
        """履歴を読み込み"""
        # 将来の拡張用: ファイルから履歴読み込み
        pass
    
    def save_history(self):
        """履歴を保存"""
        # 将来の拡張用: ファイルに履歴保存
        pass
    
    def reset(self):
        """ダッシュボードをリセット"""
        self.total_card.value_label.setText("0")
        self.saved_card.value_label.setText("¥0")
        self.cost_card.value_label.setText("¥0")
        
        self.local_progress.set_value(0)
        self.cloud_progress.set_value(0)
        
        self.usage_chart.set_data([])
        
        self.avg_time_local.setText("🟢 ローカル平均: -")
        self.avg_time_cloud.setText("🔵 クラウド平均: -")
        self.token_rate.setText("📊 トークン効率: -")
        self.cost_per_req.setText("💵 リクエスト単価: -")
        
        self.session_history.clear()
    
    def show_full_dialog(self):
        """詳細統計ダイアログを表示"""
        dialog = StatisticsDialog(self.session_history, self)
        dialog.exec()


class StatisticsDialog(QDialog):
    """詳細統計ダイアログ"""
    
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 詳細統計")
        self.setMinimumSize(800, 600)
        
        self.history = history
        
        self.init_ui()
        self.calculate_stats()
    
    def init_ui(self):
        """UI初期化"""
        layout = QVBoxLayout(self)
        
        # サマリー
        summary_group = QGroupBox("📈 セッションサマリー")
        summary_layout = QGridLayout(summary_group)
        
        self.summary_labels = {}
        metrics = [
            ("総リクエスト", "0"),
            ("ローカル使用", "0"),
            ("クラウド使用", "0"),
            ("総コスト", "¥0"),
            ("推定節約", "¥0"),
            ("平均応答時間", "-")
        ]
        
        for i, (name, default) in enumerate(metrics):
            row = i // 3
            col = (i % 3) * 2

            label = QLabel(f"{name}:")
            label.setStyleSheet(f"color: {Colors.TEXT_DIM};")
            summary_layout.addWidget(label, row, col)

            value = QLabel(default)
            value.setStyleSheet(f"color: {Colors.PRIMARY}; font-weight: bold;")
            self.summary_labels[name] = value
            summary_layout.addWidget(value, row, col + 1)
        
        layout.addWidget(summary_group)
        
        # 履歴テーブル
        history_group = QGroupBox("🕐 実行履歴")
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "時間", "モデル", "トークン(IN)", "トークン(OUT)", 
            "処理時間", "コスト"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        history_layout.addWidget(self.history_table)
        
        layout.addWidget(history_group)
        
        # ボタン
        buttons = QHBoxLayout()
        
        export_btn = QPushButton("📤 エクスポート")
        export_btn.clicked.connect(self.export_stats)
        buttons.addWidget(export_btn)
        
        buttons.addStretch()
        
        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        
        layout.addLayout(buttons)
    
    def calculate_stats(self):
        """統計を計算"""
        if not self.history:
            return
        
        total_requests = len(self.history)
        total_local = sum(h.get('local', 0) for h in self.history)
        total_cloud = sum(h.get('cloud', 0) for h in self.history)
        total_cost = sum(h.get('cost', 0) for h in self.history)
        
        # 節約計算（仮）
        saved = total_local * 5
        
        # ラベル更新
        self.summary_labels["総リクエスト"].setText(str(total_requests))
        self.summary_labels["ローカル使用"].setText(str(total_local))
        self.summary_labels["クラウド使用"].setText(str(total_cloud))
        self.summary_labels["総コスト"].setText(f"¥{total_cost:.2f}")
        self.summary_labels["推定節約"].setText(f"¥{saved:.2f}")
        
        # 履歴テーブルにデータ追加
        self.history_table.setRowCount(len(self.history))
        for i, entry in enumerate(self.history):
            self.history_table.setItem(i, 0, QTableWidgetItem(
                entry['timestamp'].strftime("%H:%M:%S")
            ))
            model = "ローカル" if entry.get('local', 0) > entry.get('cloud', 0) else "クラウド"
            self.history_table.setItem(i, 1, QTableWidgetItem(model))
            self.history_table.setItem(i, 2, QTableWidgetItem("-"))
            self.history_table.setItem(i, 3, QTableWidgetItem("-"))
            self.history_table.setItem(i, 4, QTableWidgetItem("-"))
            self.history_table.setItem(i, 5, QTableWidgetItem(f"¥{entry.get('cost', 0):.2f}"))
    
    def export_stats(self):
        """統計をエクスポート"""
        path, _ = QFileDialog.getSaveFileName(
            self, "統計をエクスポート",
            f"stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON (*.json);;CSV (*.csv)"
        )
        
        if path:
            try:
                data = {
                    'export_time': datetime.now().isoformat(),
                    'history': [
                        {
                            'timestamp': h['timestamp'].isoformat(),
                            **{k: v for k, v in h.items() if k != 'timestamp'}
                        }
                        for h in self.history
                    ]
                }
                
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "成功", "統計をエクスポートしました")
                
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"エクスポート失敗: {str(e)}")


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # ダークテーマ適用（簡易版）
    app.setStyle('Fusion')
    
    dashboard = StatisticsDashboard()
    dashboard.show()
    
    sys.exit(app.exec())
