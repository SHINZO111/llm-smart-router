"""
LM Studio Model Detector Tests
LM Studioモデル検出機能の単体テスト
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from pathlib import Path

# yamlはオプション
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None

# テスト対象のインポート
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# 非推奨パッケージのテストなのでDeprecationWarningを抑制
import warnings
warnings.filterwarnings("ignore", message="lmstudio パッケージは非推奨です", category=DeprecationWarning)

# テスト対象のインポート
try:
    from lmstudio.model_detector import (
        LMStudioModelDetector,
        ModelInfo,
        ModelDetector  # 後方互換性テスト用
    )
    CAN_IMPORT = True
except ImportError as e:
    CAN_IMPORT = False
    IMPORT_ERROR = str(e)
    # ダミークラス定義
    class ModelInfo:
        pass
    class LMStudioModelDetector:
        pass
    class ModelDetector:
        pass


class TestModelInfo(unittest.TestCase):
    """ModelInfoデータクラスのテスト"""
    
    @classmethod
    def setUpClass(cls):
        if not CAN_IMPORT:
            raise unittest.SkipTest(f"lmstudioモジュールのインポートに失敗: {IMPORT_ERROR}")
    
    def test_from_dict_basic(self):
        """基本的な辞書からの変換テスト"""
        data = {
            "id": "test-model",
            "object": "model",
            "created": 1234567890,
            "owned_by": "test-owner"
        }
        model = ModelInfo.from_dict(data)
        
        self.assertEqual(model.id, "test-model")
        self.assertEqual(model.object, "model")
        self.assertEqual(model.created, 1234567890)
        self.assertEqual(model.owned_by, "test-owner")
    
    def test_from_dict_with_optional(self):
        """オプションフィールド付きの変換テスト"""
        data = {
            "id": "test-model",
            "object": "model",
            "created": 1234567890,
            "owned_by": "test-owner",
            "name": "Test Model",
            "size": 4294967296,
            "description": "A test model"
        }
        model = ModelInfo.from_dict(data)
        
        self.assertEqual(model.name, "Test Model")
        self.assertEqual(model.size, 4294967296)
        self.assertEqual(model.description, "A test model")
    
    def test_to_dict(self):
        """辞書への変換テスト"""
        model = ModelInfo(
            id="test-model",
            object="model",
            created=1234567890,
            owned_by="test-owner",
            name="Test Model"
        )
        data = model.to_dict()
        
        self.assertEqual(data["id"], "test-model")
        self.assertEqual(data["name"], "Test Model")
    
    def test_str_representation(self):
        """文字列表現のテスト"""
        model_without_name = ModelInfo("model-id", "model", 0, "owner")
        self.assertEqual(str(model_without_name), "model-id")
        
        model_with_name = ModelInfo("model-id", "model", 0, "owner", name="Model Name")
        self.assertEqual(str(model_with_name), "model-id (Model Name)")


# requestsが利用可能かチェック
try:
    import requests
    HAS_REQUESTS_TEST = True
except ImportError:
    HAS_REQUESTS_TEST = False


class TestLMStudioModelDetector(unittest.TestCase):
    """LMStudioModelDetectorのテスト"""
    
    @classmethod
    def setUpClass(cls):
        if not CAN_IMPORT:
            raise unittest.SkipTest(f"lmstudioモジュールのインポートに失敗: {IMPORT_ERROR}")
        if not HAS_REQUESTS_TEST:
            raise unittest.SkipTest("requestsモジュールがインストールされていません")
    
    def setUp(self):
        """テスト前のセットアップ"""
        self.detector = LMStudioModelDetector(endpoint="http://localhost:1234/v1")
    
    @patch('lmstudio.model_detector.requests.get')
    def test_is_running_success(self, mock_get):
        """is_running成功時のテスト"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = self.detector.is_running()
        
        self.assertTrue(result)
        mock_get.assert_called_once_with(
            "http://localhost:1234/v1/models",
            timeout=5
        )
    
    @patch('lmstudio.model_detector.requests.get')
    def test_is_running_connection_error(self, mock_get):
        """is_running接続エラー時のテスト"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        result = self.detector.is_running()
        
        self.assertFalse(result)
    
    @patch('lmstudio.model_detector.requests.get')
    def test_is_running_timeout(self, mock_get):
        """is_runningタイムアウト時のテスト"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        result = self.detector.is_running()
        
        self.assertFalse(result)
    
    @patch('lmstudio.model_detector.requests.get')
    def test_get_loaded_models_success(self, mock_get):
        """get_loaded_models成功時のテスト"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [
                {
                    "id": "model-1",
                    "object": "model",
                    "created": 1234567890,
                    "owned_by": "owner-1",
                    "name": "Model One"
                },
                {
                    "id": "model-2",
                    "object": "model",
                    "created": 1234567891,
                    "owned_by": "owner-2"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        models = self.detector.get_loaded_models()
        
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].id, "model-1")
        self.assertEqual(models[0].name, "Model One")
        self.assertEqual(models[1].id, "model-2")
    
    @patch('lmstudio.model_detector.requests.get')
    def test_get_loaded_models_empty(self, mock_get):
        """get_loaded_models空リスト時のテスト"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": []
        }
        mock_get.return_value = mock_response
        
        models = self.detector.get_loaded_models()
        
        self.assertEqual(len(models), 0)
    
    @patch('lmstudio.model_detector.requests.get')
    def test_get_loaded_models_connection_error(self, mock_get):
        """get_loaded_models接続エラー時のテスト"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        with self.assertRaises(ConnectionError) as context:
            self.detector.get_loaded_models()
        
        self.assertIn("LM Studioに接続できません", str(context.exception))
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_get_default_model_success(self, mock_get_models):
        """get_default_model成功時のテスト"""
        mock_get_models.return_value = [
            ModelInfo("default-model", "model", 0, "owner"),
            ModelInfo("other-model", "model", 0, "owner")
        ]
        
        default = self.detector.get_default_model()
        
        self.assertEqual(default, "default-model")
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_get_default_model_empty(self, mock_get_models):
        """get_default_model空リスト時のテスト"""
        mock_get_models.return_value = []
        
        default = self.detector.get_default_model()
        
        self.assertIsNone(default)
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_get_default_model_error(self, mock_get_models):
        """get_default_modelエラー時のテスト"""
        mock_get_models.side_effect = ConnectionError("Test error")
        
        default = self.detector.get_default_model()
        
        self.assertIsNone(default)
    
    def test_update_config_models(self):
        """_update_config_modelsのテスト"""
        config = {
            "models": {
                "local": {
                    "endpoint": "http://old-endpoint",
                    "model": "old-model",
                    "temperature": 0.5,
                    "max_tokens": 1024
                }
            }
        }
        
        models = [
            ModelInfo("new-model", "model", 0, "owner", name="New Model"),
            ModelInfo("second-model", "model", 0, "owner", name="Second Model")
        ]
        
        updated = self.detector._update_config_models(config, models)
        
        # ローカルモデルが更新されている
        self.assertEqual(updated["models"]["local"]["model"], "new-model")
        # 既存の設定は保持されている
        self.assertEqual(updated["models"]["local"]["temperature"], 0.5)
        self.assertEqual(updated["models"]["local"]["max_tokens"], 1024)
        # 新しいモデルが追加されている
        self.assertIn("lmstudio", updated["models"])
        self.assertIn("lmstudio_1", updated["models"])
        self.assertEqual(updated["models"]["lmstudio_1"]["model"], "second-model")
        # メタデータが追加されている
        self.assertIn("lmstudio_meta", updated)
        self.assertEqual(updated["lmstudio_meta"]["last_detected"], "new-model")
    
    @unittest.skipUnless(HAS_YAML, "PyYAML not installed")
    def test_load_config_existing(self):
        """既存設定ファイル読み込みテスト"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({"models": {"local": {"model": "test"}}}, f)
            temp_path = f.name
        
        try:
            config = self.detector._load_config(Path(temp_path))
            self.assertEqual(config["models"]["local"]["model"], "test")
        finally:
            os.unlink(temp_path)
    
    def test_load_config_default(self):
        """デフォルト設定生成テスト"""
        config = self.detector._load_config(Path("/nonexistent/path.yaml"))
        
        self.assertIn("models", config)
        self.assertIn("local", config["models"])
        self.assertIn("cloud", config["models"])
        self.assertIn("fallback_chain", config)
    
    @unittest.skipUnless(HAS_YAML, "PyYAML not installed")
    def test_save_config(self):
        """設定ファイル保存テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yaml"
            config = {"models": {"local": {"model": "test-model"}}}
            
            self.detector._save_config(config_path, config)
            
            self.assertTrue(config_path.exists())
            with open(config_path, 'r') as f:
                loaded = yaml.safe_load(f)
            self.assertEqual(loaded["models"]["local"]["model"], "test-model")
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_detect_and_update_config_success(self, mock_get_models):
        """detect_and_update_config成功時のテスト"""
        mock_get_models.return_value = [
            ModelInfo("detected-model", "model", 0, "owner")
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            
            result = self.detector.detect_and_update_config(config_path)
            
            self.assertTrue(result["success"])
            self.assertTrue(result["config_updated"])
            self.assertEqual(result["models_detected"], 1)
            self.assertEqual(result["default_model"], "detected-model")
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_detect_and_update_config_no_models(self, mock_get_models):
        """detect_and_update_configモデルなし時のテスト"""
        mock_get_models.return_value = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            
            result = self.detector.detect_and_update_config(config_path)
            
            self.assertFalse(result["success"])
            self.assertFalse(result["config_updated"])
            self.assertIn("モデルが検出されませんでした", result["errors"])
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_detect_and_update_config_connection_error(self, mock_get_models):
        """detect_and_update_config接続エラー時のテスト"""
        mock_get_models.side_effect = ConnectionError("Test error")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            
            result = self.detector.detect_and_update_config(config_path)
            
            self.assertFalse(result["success"])
            self.assertFalse(result["config_updated"])
            self.assertTrue(len(result["errors"]) > 0)
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_get_model_details_found(self, mock_get_models):
        """get_model_details見つかる場合のテスト"""
        mock_get_models.return_value = [
            ModelInfo("model-1", "model", 0, "owner"),
            ModelInfo("model-2", "model", 0, "owner")
        ]
        
        details = self.detector.get_model_details("model-2")
        
        self.assertIsNotNone(details)
        self.assertEqual(details.id, "model-2")
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_get_model_details_not_found(self, mock_get_models):
        """get_model_details見つからない場合のテスト"""
        mock_get_models.return_value = [
            ModelInfo("model-1", "model", 0, "owner")
        ]
        
        details = self.detector.get_model_details("nonexistent")
        
        self.assertIsNone(details)
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_format_models_table(self, mock_get_models):
        """format_models_tableのテスト"""
        mock_get_models.return_value = [
            ModelInfo("model-1", "model", 0, "owner", name="First Model"),
            ModelInfo("model-2", "model", 0, "owner", name="Second Model")
        ]
        
        table = self.detector.format_models_table()
        
        self.assertIn("model-1", table)
        self.assertIn("First Model", table)
        self.assertIn("デフォルト", table)
        self.assertIn("model-2", table)
    
    @patch.object(LMStudioModelDetector, 'get_loaded_models')
    def test_format_models_table_empty(self, mock_get_models):
        """format_models_table空リスト時のテスト"""
        mock_get_models.return_value = []
        
        table = self.detector.format_models_table()
        
        self.assertIn("モデルが読み込まれていません", table)
    
    def test_backward_compatibility(self):
        """後方互換性のテスト"""
        # ModelDetectorエイリアスが機能すること
        detector = ModelDetector()
        self.assertIsInstance(detector, LMStudioModelDetector)


class TestIntegrationWithoutLMStudio(unittest.TestCase):
    """
    LM Studioがない環境での動作テスト
    （実際の接続は行わないモックテスト）
    """
    
    @classmethod
    def setUpClass(cls):
        if not CAN_IMPORT:
            raise unittest.SkipTest(f"lmstudioモジュールのインポートに失敗: {IMPORT_ERROR}")
        if not HAS_REQUESTS_TEST:
            raise unittest.SkipTest("requestsモジュールがインストールされていません")
    
    @patch('lmstudio.model_detector.requests.get')
    def test_graceful_degradation(self, mock_get):
        """LM Studioがない場合の適切なエラーハンドリング"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        detector = LMStudioModelDetector()
        
        # is_running()はFalseを返すべき
        self.assertFalse(detector.is_running())
        
        # get_loaded_models()はConnectionErrorを投げるべき
        with self.assertRaises(ConnectionError):
            detector.get_loaded_models()
        
        # get_default_model()はNoneを返すべき（例外を投げない）
        default = detector.get_default_model()
        self.assertIsNone(default)


if __name__ == "__main__":
    unittest.main()
