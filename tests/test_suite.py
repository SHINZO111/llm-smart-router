#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Smart Router GUI v2.0 総合テストスイート

テスト項目:
1. APIキー暗号化テスト
2. GUI起動テスト
3. ダッシュボード機能テスト
4. プリセット管理テスト
5. OpenClaw連携テスト
6. モデル切り替え機能テスト

使用方法:
    python test_suite.py [test_name]
    python test_suite.py all  # 全テスト実行

作者: しんぞう
バージョン: 2.0.0
"""

import sys
import os
import time
import json
import tempfile
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# テスト対象モジュールのパス設定
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

# テストフレームワーク
import unittest
from unittest.mock import Mock, patch, MagicMock

# Qtテスト用
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QTimer

# テスト対象モジュール
try:
    from security.key_manager import SecureKeyManager, APIKeyMetadata
    from gui.dashboard import StatisticsDashboard, CircularProgress, BarChart
    from gui.main_window import MainWindow, PresetManager, LLMWorker
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"[!] モジュール読み込みエラー: {e}")
    MODULES_AVAILABLE = False


# ============================================================
# テスト結果クラス
# ============================================================

class TestResult:
    """テスト結果を管理するクラス"""
    
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category
        self.status = "PENDING"  # PENDING, PASS, FAIL, SKIP
        self.duration = 0.0
        self.message = ""
        self.details = {}
        self.error = None
        
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'category': self.category,
            'status': self.status,
            'duration': self.duration,
            'message': self.message,
            'details': self.details,
            'error': str(self.error) if self.error else None
        }


class TestReport:
    """テストレポート生成クラス"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = datetime.now()
        
    def add_result(self, result: TestResult):
        self.results.append(result)
        
    def get_summary(self) -> dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        skipped = sum(1 for r in self.results if r.status == "SKIP")
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'duration': (datetime.now() - self.start_time).total_seconds()
        }
    
    def generate_report(self) -> str:
        summary = self.get_summary()
        
        report = []
        report.append("=" * 80)
        report.append("🧪 LLM Smart Router GUI v2.0 テストレポート")
        report.append("=" * 80)
        report.append(f"実行時刻: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"総テスト数: {summary['total']}")
        report.append(f"✅ 成功数: {summary['passed']}")
        report.append(f"❌ 失敗数: {summary['failed']}")
        report.append(f"⏭️  スキップ: {summary['skipped']}")
        report.append(f"📊 成功率: {summary['pass_rate']:.1f}%")
        report.append(f"⏱️  総実行時間: {summary['duration']:.2f}秒")
        report.append("=" * 80)
        report.append("")
        
        # カテゴリ別にグループ化
        categories = {}
        for result in self.results:
            cat = result.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(result)
        
        for category, results in categories.items():
            report.append(f"\n【{category}】")
            report.append("-" * 80)
            
            for r in results:
                icon = {
                    "PASS": "✅",
                    "FAIL": "❌",
                    "SKIP": "⏭️",
                    "PENDING": "⏳"
                }.get(r.status, "❌")
                
                report.append(f"  {icon} {r.name} ({r.duration:.2f}s)")
                if r.message:
                    report.append(f"     📝 {r.message}")
                if r.error:
                    report.append(f"     📝 エラー: {r.error}")
        
        report.append("\n" + "=" * 80)
        report.append("詳細ログは test_results.json を確認")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_json(self, path: str = "test_results.json"):
        data = {
            'summary': self.get_summary(),
            'results': [r.to_dict() for r in self.results]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# テストランナー
# ============================================================

class TestRunner:
    """テスト実行エンジン"""
    
    def __init__(self):
        self.report = TestReport()
        
    def run_test(self, name: str, category: str, test_func) -> TestResult:
        """個別テストを実行"""
        result = TestResult(name, category)
        start = time.time()
        
        try:
            test_func(result)
            if result.status == "PENDING":
                result.status = "PASS"
        except Exception as e:
            result.status = "FAIL"
            result.error = e
            result.message = str(e)
        finally:
            result.duration = time.time() - start
            self.report.add_result(result)
        
        return result
    
    def run_all_tests(self):
        """すべてのテストを実行"""
        print("🚀 テストスイート起動...\n")
        
        # 1. APIキー暗号化テスト
        self._run_security_tests()
        
        # 2. GUI起動テスト
        self._run_gui_tests()
        
        # 3. ダッシュボード機能テスト
        self._run_dashboard_tests()
        
        # 4. プリセット管理テスト
        self._run_preset_tests()
        
        # 5. OpenClaw連携テスト
        self._run_openclaw_tests()
        
        # 6. モデル切り替えテスト
        self._run_model_switch_tests()
        
        # レポート出力
        print("\n" + self.report.generate_report())
        self.report.save_json()
        
    def _run_security_tests(self):
        """セキュリティ関連テスト"""
        print("🔒 セキュリティテスト実行中...")
        
        def test_key_encryption(result):
            if not MODULES_AVAILABLE:
                result.status = "SKIP"
                result.message = "モジュールが読み込めません"
                return
                
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    key_file = Path(tmpdir) / "test_keys.db"
                    km = SecureKeyManager(str(key_file))
                    
                    # キー保存テスト
                    km.save_key("test-provider", "test-api-key-12345", "Test Key")
                    
                    # キー取得テスト
                    key = km.get_key("test-provider")
                    assert key == "test-api-key-12345", "復号化されたキーが一致しません"
                    
                    result.message = "キーの暗号化・復号化に成功"
                    result.details['key_file'] = str(key_file)
            except Exception as e:
                raise e
        
        self.run_test("APIキー暗号化テスト", "セキュリティ", test_key_encryption)
        
        def test_key_metadata(result):
            if not MODULES_AVAILABLE:
                result.status = "SKIP"
                return
                
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    key_file = Path(tmpdir) / "test_keys.db"
                    km = SecureKeyManager(str(key_file))
                    
                    km.save_key("anthropic", "sk-ant-xxx", "Anthropic Key")
                    metadata = km.get_key_metadata("anthropic")
                    
                    assert metadata is not None, "メタデータが取得できません"
                    assert metadata.provider == "anthropic"
                    
                    result.message = "キーメタデータ管理に成功"
            except Exception as e:
                raise e
        
        self.run_test("キーメタデータテスト", "セキュリティ", test_key_metadata)
    
    def _run_gui_tests(self):
        """GUI関連テスト"""
        print("🖥️  GUIテスト実行中...")
        
        def test_app_initialization(result):
            try:
                # QApplicationは1つだけ作成可能
                app = QApplication.instance() or QApplication(sys.argv)
                result.message = "QApplication初期化成功"
                result.details['qt_version'] = Qt.QT_VERSION_STR
            except Exception as e:
                raise e
        
        self.run_test("アプリ初期化テスト", "GUI", test_app_initialization)
        
        def test_main_window(result):
            if not MODULES_AVAILABLE:
                result.status = "SKIP"
                return
                
            try:
                app = QApplication.instance() or QApplication(sys.argv)
                window = MainWindow()
                assert window is not None, "メインウィンドウが作成できません"
                result.message = "メインウィンドウ作成成功"
                window.close()
            except Exception as e:
                raise e
        
        self.run_test("メインウィンドウテスト", "GUI", test_main_window)
    
    def _run_dashboard_tests(self):
        """ダッシュボード機能テスト"""
        print("📊 ダッシュボードテスト実行中...")
        
        def test_circular_progress(result):
            if not MODULES_AVAILABLE:
                result.status = "SKIP"
                return
                
            try:
                app = QApplication.instance() or QApplication(sys.argv)
                widget = CircularProgress()
                widget.set_value(75)
                assert widget.value == 75, "値が設定できません"
                result.message = "CircularProgress動作確認"
            except Exception as e:
                raise e
        
        self.run_test("円形プログレスバーテスト", "ダッシュボード", test_circular_progress)
    
    def _run_preset_tests(self):
        """プリセット管理テスト"""
        print("💾 プリセットテスト実行中...")
        
        def test_preset_save_load(result):
            if not MODULES_AVAILABLE:
                result.status = "SKIP"
                return
                
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    preset_file = Path(tmpdir) / "presets.json"
                    pm = PresetManager(str(preset_file))
                    
                    # プリセット保存
                    test_preset = {
                        "name": "テストプリセット",
                        "model": "claude-3-opus",
                        "temperature": 0.7,
                        "max_tokens": 2000
                    }
                    pm.save_preset("test", test_preset)
                    
                    # プリセット読み込み
                    loaded = pm.load_preset("test")
                    assert loaded["name"] == "テストプリセット", "プリセットが一致しません"
                    
                    result.message = "プリセット保存・読み込み成功"
            except Exception as e:
                raise e
        
        self.run_test("プリセット保存読み込みテスト", "プリセット", test_preset_save_load)
    
    def _run_openclaw_tests(self):
        """OpenClaw連携テスト"""
        print("🤖 OpenClaw連携テスト実行中...")
        
        def test_openclaw_detection(result):
            try:
                # OpenClawがインストールされているか確認
                result_code = subprocess.run(
                    ["openclaw", "--version"],
                    capture_output=True,
                    shell=True
                ).returncode
                
                if result_code == 0:
                    result.message = "OpenClawが検出されました"
                    result.details['detected'] = True
                else:
                    result.status = "SKIP"
                    result.message = "OpenClawがインストールされていません"
                    result.details['detected'] = False
            except Exception as e:
                result.status = "SKIP"
                result.message = f"OpenClaw検出エラー: {e}"
        
        self.run_test("OpenClaw検出テスト", "OpenClaw連携", test_openclaw_detection)
    
    def _run_model_switch_tests(self):
        """モデル切り替えテスト"""
        print("🔄 モデル切り替えテスト実行中...")
        
        def test_model_provider_switch(result):
            if not MODULES_AVAILABLE:
                result.status = "SKIP"
                return
                
            try:
                # モックテスト
                worker = LLMWorker()
                worker.set_provider("anthropic")
                assert worker.current_provider == "anthropic", "プロバイダー切り替えに失敗"
                
                worker.set_provider("openai")
                assert worker.current_provider == "openai", "プロバイダー切り替えに失敗"
                
                result.message = "モデルプロバイダー切り替え成功"
            except Exception as e:
                raise e
        
        self.run_test("プロバイダー切り替えテスト", "モデル切り替え", test_model_provider_switch)


# ============================================================
# メインエントリーポイント
# ============================================================

def run_specific_test(test_name: str):
    """特定のテストのみ実行"""
    runner = TestRunner()
    
    test_map = {
        "security": runner._run_security_tests,
        "gui": runner._run_gui_tests,
        "dashboard": runner._run_dashboard_tests,
        "preset": runner._run_preset_tests,
        "openclaw": runner._run_openclaw_tests,
        "model": runner._run_model_switch_tests,
    }
    
    if test_name in test_map:
        test_map[test_name]()
        print("\n" + runner.report.generate_report())
        runner.report.save_json()
    else:
        print(f"不明なテスト名: {test_name}")
        print(f"利用可能: {', '.join(test_map.keys())}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            runner = TestRunner()
            runner.run_all_tests()
        else:
            run_specific_test(sys.argv[1])
    else:
        # デフォルトですべて実行
        runner = TestRunner()
        runner.run_all_tests()
