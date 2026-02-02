#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Smart Router GUI v2.0 改善適用ガイド

このスクリプトは、改善モジュールを既存のコードに適用するための
パッチ適用ツールです。

使用方法:
    python apply_improvements.py [--check] [--backup]

オプション:
    --check     適用前に互換性チェックのみ実行
    --backup    元のファイルをバックアップ
    --restore   バックアップから復元

【作者】クラ for 新さん
【バージョン】1.0.0
"""

import sys
import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime


class ImprovementPatcher:
    """改善パッチ適用クラス"""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or 'F:\\llm-smart-router')
        self.src_path = self.base_path / 'src' / 'gui'
        self.backup_path = self.base_path / 'backups'
        
        # パッチ定義
        self.patches = {
            'performance_optimizer': {
                'source': self.src_path / 'performance_optimizer.py',
                'description': 'パフォーマンス最適化・エラーハンドリング・ショートカット・ログ機能'
            },
            'main_window_improved': {
                'source': self.src_path / 'main_window_improved.py',
                'description': '改良版メインウィンドウ'
            }
        }
    
    def check_prerequisites(self) -> bool:
        """前提条件をチェック"""
        print("🔍 前提条件チェック...")
        
        checks = []
        
        # 1. Pythonバージョン
        py_version = sys.version_info
        checks.append((
            "Pythonバージョン",
            py_version >= (3, 9),
            f"{py_version.major}.{py_version.minor}.{py_version.micro}"
        ))
        
        # 2. 必要ファイルの存在
        main_window = self.src_path / 'main_window.py'
        checks.append((
            "main_window.py",
            main_window.exists(),
            "存在" if main_window.exists() else "不在"
        ))
        
        # 3. PySide6
        try:
            import PySide6
            checks.append(("PySide6", True, PySide6.__version__))
        except ImportError:
            checks.append(("PySide6", False, "未インストール"))
        
        # 結果表示
        all_passed = True
        for name, passed, detail in checks:
            status = "✅" if passed else "❌"
            print(f"  {status} {name}: {detail}")
            if not passed:
                all_passed = False
        
        return all_passed
    
    def backup_original(self) -> bool:
        """元のファイルをバックアップ"""
        print("\n💾 バックアップ作成...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = self.backup_path / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        files_to_backup = [
            self.src_path / 'main_window.py',
            self.src_path / 'dashboard.py',
            self.src_path / 'settings_dialog.py',
        ]
        
        for file_path in files_to_backup:
            if file_path.exists():
                dest = backup_dir / file_path.name
                shutil.copy2(file_path, dest)
                print(f"  ✅ {file_path.name} → {dest}")
        
        # バックアップ情報を保存
        info_file = backup_dir / 'backup_info.txt'
        with open(info_file, 'w', encoding='utf-8') as f:
            f.write(f"Backup created: {timestamp}\n")
            f.write(f"Original path: {self.src_path}\n")
        
        print(f"\n  バックアップ先: {backup_dir}")
        return True
    
    def apply_patches(self) -> bool:
        """パッチを適用"""
        print("\n🔧 改善パッチ適用...")
        
        # 1. performance_optimizer.py はそのまま追加
        perf_opt = self.patches['performance_optimizer']['source']
        if perf_opt.exists():
            print(f"  ✅ {perf_opt.name} は既に存在")
        else:
            print(f"  ⚠️ {perf_opt.name} が見つかりません")
            return False
        
        # 2. main_window.py の置き換え
        main_original = self.src_path / 'main_window.py'
        main_improved = self.patches['main_window_improved']['source']
        
        if main_improved.exists():
            # 元のファイルをリネームして保持
            main_backup = self.src_path / 'main_window_original.py'
            if main_original.exists():
                shutil.copy2(main_original, main_backup)
            
            # 改良版をコピー
            shutil.copy2(main_improved, main_original)
            print(f"  ✅ main_window.py を改良版に置き換え")
        else:
            print(f"  ⚠️ main_window_improved.py が見つかりません")
            return False
        
        return True
    
    def create_launcher(self) -> bool:
        """起動スクリプトを作成"""
        print("\n🚀 起動スクリプト作成...")
        
        # 改良版用バッチファイル
        batch_content = '''@echo off
echo LLM Smart Router GUI v2.1 (Improved)
echo =====================================
echo.

REM 仮想環境があれば有効化
if exist "venv\\Scripts\\activate.bat" (
    call venv\\Scripts\\activate.bat
)

REM 必要なモジュールのチェック
python -c "import PySide6" 2>nul
if errorlevel 1 (
    echo [警告] PySide6がインストールされていません
    echo pip install PySide6 keyring cryptography pyyaml requests psutil
    pause
    exit /b 1
)

REM 改良版を起動
python src\\gui\\main_window.py

pause
'''
        
        batch_path = self.base_path / 'run_gui_improved.bat'
        with open(batch_path, 'w', encoding='utf-8') as f:
            f.write(batch_content)
        
        print(f"  ✅ {batch_path.name} を作成")
        
        # READMEの更新
        readme_path = self.base_path / 'README_IMPROVEMENTS.md'
        readme_content = '''# LLM Smart Router GUI v2.1 改善版

## 🆕 新機能

### 1. パフォーマンス最適化
- 大規模テキスト（50KB+）の非同期処理
- UIスレッドブロック防止
- メモリ使用量モニタリング

### 2. エラーハンドリング強化
- カテゴリ別エラー表示（接続/認証/タイムアウト等）
- 対処法の自動提案
- 詳細ログのワンクリックコピー

### 3. 拡張キーボードショートカット
- `Ctrl+M` - モデル切替
- `Ctrl+Shift+C` - 出力コピー
- `Ctrl++` / `Ctrl+-` - フォントサイズ調整
- `F1` - クイックヘルプ

### 4. ログ機能
- アプリケーション動作ログ
- エラーログの自動記録
- ログエクスポート機能

## 🚀 起動方法

```bash
# 改良版起動
run_gui_improved.bat

# または直接
python src\\gui\\main_window.py
```

## 📚 マニュアル

詳細は `docs/USER_MANUAL.md` を参照してください。

## 🧪 テスト

```bash
# テスト実行
python tests\\test_suite.py all
```

## 📝 変更履歴

### v2.1 (2026-02-03)
- GUIパフォーマンス最適化
- エラーメッセージ改善
- キーボードショートカット追加
- ログ機能追加

### v2.0 (2026-02-02)
- 初回リリース
'''
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"  ✅ {readme_path.name} を作成")
        
        return True
    
    def verify_installation(self) -> bool:
        """インストールを検証"""
        print("\n✅ インストール検証...")
        
        checks = []
        
        # 1. 改善モジュールの存在
        perf_opt = self.src_path / 'performance_optimizer.py'
        checks.append((
            "performance_optimizer.py",
            perf_opt.exists(),
            "存在" if perf_opt.exists() else "不在"
        ))
        
        # 2. メインウィンドウのシンタックスチェック
        main_window = self.src_path / 'main_window.py'
        if main_window.exists():
            try:
                with open(main_window, 'r', encoding='utf-8') as f:
                    compile(f.read(), main_window, 'exec')
                checks.append(("main_window.py 構文", True, "正常"))
            except SyntaxError as e:
                checks.append(("main_window.py 構文", False, str(e)))
        
        # 3. 起動スクリプト
        launcher = self.base_path / 'run_gui_improved.bat'
        checks.append((
            "run_gui_improved.bat",
            launcher.exists(),
            "存在" if launcher.exists() else "不在"
        ))
        
        # 結果表示
        all_passed = True
        for name, passed, detail in checks:
            status = "✅" if passed else "❌"
            print(f"  {status} {name}: {detail}")
            if not passed:
                all_passed = False
        
        return all_passed
    
    def restore_backup(self, timestamp: str = None) -> bool:
        """バックアップから復元"""
        print("\n🔄 バックアップ復元...")
        
        if timestamp:
            backup_dir = self.backup_path / timestamp
        else:
            # 最新のバックアップを探す
            backups = sorted(self.backup_path.glob('*'))
            if not backups:
                print("  ❌ バックアップが見つかりません")
                return False
            backup_dir = backups[-1]
        
        if not backup_dir.exists():
            print(f"  ❌ バックアップが見つかりません: {backup_dir}")
            return False
        
        # ファイルを復元
        for backup_file in backup_dir.glob('*.py'):
            dest = self.src_path / backup_file.name
            shutil.copy2(backup_file, dest)
            print(f"  ✅ {backup_file.name} を復元")
        
        print(f"\n  復元元: {backup_dir}")
        return True
    
    def list_backups(self):
        """バックアップ一覧を表示"""
        print("\n📋 バックアップ一覧:")
        
        if not self.backup_path.exists():
            print("  バックアップはありません")
            return
        
        backups = sorted(self.backup_path.glob('*'))
        if not backups:
            print("  バックアップはありません")
            return
        
        for i, backup in enumerate(backups, 1):
            info_file = backup / 'backup_info.txt'
            if info_file.exists():
                with open(info_file, 'r') as f:
                    first_line = f.readline().strip()
                    print(f"  {i}. {backup.name} - {first_line}")
            else:
                print(f"  {i}. {backup.name}")


def main():
    parser = argparse.ArgumentParser(
        description='LLM Smart Router GUI 改善パッチ適用ツール'
    )
    parser.add_argument(
        '--check', action='store_true',
        help='適用前に互換性チェックのみ実行'
    )
    parser.add_argument(
        '--backup', action='store_true',
        help='元のファイルをバックアップ'
    )
    parser.add_argument(
        '--restore', metavar='TIMESTAMP',
        help='バックアップから復元 (TIMESTAMP指定または最新)'
    )
    parser.add_argument(
        '--list-backups', action='store_true',
        help='バックアップ一覧を表示'
    )
    
    args = parser.parse_args()
    
    patcher = ImprovementPatcher()
    
    if args.list_backups:
        patcher.list_backups()
        return
    
    if args.restore:
        patcher.restore_backup(args.restore if args.restore != 'latest' else None)
        return
    
    # 前提条件チェック
    if not patcher.check_prerequisites():
        print("\n❌ 前提条件を満たしていません")
        sys.exit(1)
    
    if args.check:
        print("\n✅ 互換性チェック完了")
        return
    
    # バックアップ
    if args.backup:
        patcher.backup_original()
    
    # パッチ適用
    if not patcher.apply_patches():
        print("\n❌ パッチ適用に失敗しました")
        sys.exit(1)
    
    # 起動スクリプト作成
    patcher.create_launcher()
    
    # 検証
    if not patcher.verify_installation():
        print("\n⚠️ 検証で問題が見つかりました")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ 改善パッチの適用が完了しました！")
    print("=" * 60)
    print("\n次のステップ:")
    print("  1. run_gui_improved.bat を実行して起動")
    print("  2. docs/USER_MANUAL.md で使い方を確認")
    print("  3. F1キーでキーボードショートカットを確認")
    print("\n問題がある場合:")
    print("  python apply_improvements.py --restore latest")
    print("=" * 60)


if __name__ == '__main__':
    main()
