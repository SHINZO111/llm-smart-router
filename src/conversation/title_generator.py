"""
タイトル生成モジュール - Title Generator

最初のユーザー入力から会話タイトルを自動生成
"""
import re
import logging
from typing import Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class TitleGenerationMethod(Enum):
    """タイトル生成方法"""
    KEYWORD_EXTRACTION = "keyword"  # キーワード抽出（ローカル処理）
    GEMINI_API = "gemini"           # Gemini API使用
    SIMPLE_TRUNCATION = "simple"    # 単純な切り詰め


class TitleGenerator:
    """
    会話タイトルを自動生成するクラス
    
    機能:
    - キーワード抽出によるタイトル生成（デフォルト）
    - Gemini APIを使用したタイトル生成（オプション）
    - 単純な切り詰めによるフォールバック
    """
    
    # 日本語・英語のストップワード
    STOP_WORDS = {
        # 日本語
        "て", "に", "を", "は", "が", "の", "と", "た", "し", "て", "で", "から", "まで",
        "という", "について", "これ", "それ", "あれ", "この", "その", "あの", "です", "ます",
        "ある", "いる", "する", "なる", "られる", "られる", "を", "について", "ください",
        "お願い", "お願いします", "教えて", "教え", "ください", "できる", "する", "たい",
        "あり", "どう", "何", "なに", "どの", "どんな", "なぜ", "どうして", "理由",
        "方法", "やり方", "作り方", "使い方", "場合", "こと", "もの", "わけ", "の",
        # 英語
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "may", "might", "must", "shall", "can", "need", "dare", "ought", "used", "to",
        "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "during", "before", "after", "above", "below", "between", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why", "how",
        "all", "each", "few", "more", "most", "other", "some", "such", "no", "nor",
        "not", "only", "own", "same", "so", "than", "too", "very", "just", "and",
        "but", "if", "or", "because", "until", "while", "this", "that", "these", "those"
    }
    
    # 重要そうな単語を優先するパターン
    PRIORITY_PATTERNS = [
        r"(Python|JavaScript|TypeScript|Java|Go|Rust|C\+\+|C#|Ruby|PHP|Swift|Kotlin)",
        r"(React|Vue|Angular|Next\.js|Node\.js|Django|Flask|FastAPI|Spring)",
        r"(AI|機械学習|ディープラーニング|LLM|ChatGPT|GPT|Claude|Gemini)",
        r"(データベース|DB|SQL|NoSQL|MongoDB|PostgreSQL|MySQL|Redis)",
        r"(Docker|Kubernetes|AWS|Azure|GCP|クラウド|サーバレス)",
        r"(API|REST|GraphQL|gRPC|WebSocket|HTTP)",
        r"(エラー|バグ|問題|トラブル|解決|修正|デバッグ)",
        r"(設計|アーキテクチャ|パターン|ベストプラクティス)",
    ]
    
    def __init__(self, 
                 method: TitleGenerationMethod = TitleGenerationMethod.KEYWORD_EXTRACTION,
                 max_length: int = 30,
                 api_key: Optional[str] = None):
        """
        TitleGeneratorを初期化
        
        Args:
            method: タイトル生成方法
            max_length: タイトルの最大長
            api_key: Gemini APIキー（GEMINI_API使用時）
        """
        self.method = method
        self.max_length = max_length
        self.api_key = api_key
        self._gemini_client = None
    
    def _init_gemini(self):
        """Gemini APIクライアントを初期化（遅延ロード）"""
        if self._gemini_client is None and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._gemini_client = genai.GenerativeModel('gemini-pro')
            except ImportError:
                logger.warning("google-generativeai not installed. Falling back to keyword extraction.")
                self.method = TitleGenerationMethod.KEYWORD_EXTRACTION
            except Exception as e:
                logger.warning("Failed to initialize Gemini: %s", e)
                self.method = TitleGenerationMethod.KEYWORD_EXTRACTION
    
    def generate(self, text: str) -> str:
        """
        テキストからタイトルを生成
        
        Args:
            text: ユーザー入力テキスト
            
        Returns:
            生成されたタイトル
        """
        if not text or not text.strip():
            return "新規会話"
        
        # 改行を空白に置換して一文に
        text = text.replace("\n", " ").strip()
        
        if self.method == TitleGenerationMethod.GEMINI_API:
            return self._generate_with_gemini(text)
        elif self.method == TitleGenerationMethod.KEYWORD_EXTRACTION:
            return self._extract_keywords(text)
        else:
            return self._simple_truncate(text)
    
    def _generate_with_gemini(self, text: str) -> str:
        """Gemini APIを使用してタイトルを生成"""
        self._init_gemini()
        
        if not self._gemini_client:
            # フォールバック
            return self._extract_keywords(text)
        
        try:
            prompt = f"""
以下のテキストに適切な短いタイトルを生成してください。
タイトルは20文字以内で、内容を簡潔に表現してください。

テキスト:
{text[:500]}

タイトル（20文字以内）:"""
            
            response = self._gemini_client.generate_content(prompt)
            title = response.text.strip()
            
            # 引用符を削除
            title = title.strip('"\'「」『』')
            
            # 長さ制限
            if len(title) > self.max_length:
                title = title[:self.max_length] + "..."
            
            return title if title else self._extract_keywords(text)
            
        except Exception as e:
            logger.warning("Gemini API error: %s", e)
            return self._extract_keywords(text)
    
    def _extract_keywords(self, text: str) -> str:
        """キーワード抽出によるタイトル生成"""
        # 優先パターンをチェック
        for pattern in self.PRIORITY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # パターンにマッチしたら、それを含む文を抽出
                start = max(0, match.start() - 10)
                end = min(len(text), match.end() + 20)
                snippet = text[start:end].strip()
                return self._truncate_to_max_length(snippet)
        
        # 名詞っぽい単語を抽出
        words = self._extract_noun_like_words(text)
        
        if words:
            # 重要度でソートして上位を使用
            title = " ".join(words[:4])  # 最大4単語
        else:
            # フォールバック：単純な切り詰め
            title = text[:self.max_length]
        
        return self._truncate_to_max_length(title)
    
    def _extract_noun_like_words(self, text: str) -> List[str]:
        """名詞っぽい単語を抽出"""
        # 日本語と英語の単語を抽出
        # 日本語：2文字以上の連続する漢字・ひらがな・カタカナ
        # 英語：アルファベットの単語
        
        words = []
        
        # 英語単語の抽出
        english_words = re.findall(r'\b[a-zA-Z]+\b', text)
        for word in english_words:
            word_lower = word.lower()
            if word_lower not in self.STOP_WORDS and len(word) > 2:
                words.append(word)
        
        # 日本語の抽出（簡易的）
        # まず記号で分割
        segments = re.split(r'[。！？\.\,\;\:\(\)\"\'\[\]\{\}]', text)
        
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            
            # カタカナの固有名詞を探す（2文字以上）
            katakana_words = re.findall(r'[ァ-ヴ]{2,}', segment)
            words.extend(katakana_words)
            
            # 漢字を含む部分（2〜8文字）
            kanji_segments = re.findall(r'[一-龥ぁ-んァ-ヴ]{2,8}', segment)
            for seg in kanji_segments:
                if seg not in self.STOP_WORDS and len(seg) >= 2:
                    words.append(seg)
        
        # 重複除去と順序保持
        seen = set()
        unique_words = []
        for word in words:
            word_key = word.lower()
            if word_key not in seen:
                seen.add(word_key)
                unique_words.append(word)
        
        return unique_words
    
    def _simple_truncate(self, text: str) -> str:
        """単純な切り詰め"""
        return self._truncate_to_max_length(text)
    
    def _truncate_to_max_length(self, text: str) -> str:
        """最大長に切り詰め"""
        if len(text) <= self.max_length:
            return text
        
        # 単語境界で切る（英語の場合）
        truncated = text[:self.max_length]
        
        # 最後のスペースを探してそこで切る
        last_space = truncated.rfind(' ')
        if last_space > self.max_length * 0.5:  # 半分以上ある場合のみ
            truncated = truncated[:last_space]
        
        return truncated.strip() + "..."
    
    def set_method(self, method: TitleGenerationMethod):
        """生成方法を変更"""
        self.method = method
    
    def set_api_key(self, api_key: str):
        """Gemini APIキーを設定"""
        self.api_key = api_key
        self._gemini_client = None


class SimpleTitleGenerator:
    """
    シンプルなタイトル生成器（軽量版）
    
    キーワード抽出のみを行う軽量な実装
    """
    
    DEFAULT_TITLES = [
        "コードについて", "質問", "相談", "プロジェクト", "調べ物",
        "アイデア", "計画", "設計", "レビュー", "学習"
    ]
    
    def __init__(self, max_length: int = 30):
        self.max_length = max_length
    
    def generate(self, text: str) -> str:
        """テキストからタイトルを生成"""
        if not text or not text.strip():
            import random
            return random.choice(self.DEFAULT_TITLES)
        
        text = text.strip()
        
        # 最初の文を取得
        first_sentence = re.split(r'[。！？\.\n]', text)[0]
        
        # 長さに応じて処理
        if len(first_sentence) <= self.max_length:
            return first_sentence
        
        # 切り詰め
        return first_sentence[:self.max_length - 3] + "..."


# 便利なファクトリ関数
def create_title_generator(method: str = "keyword", 
                          api_key: Optional[str] = None,
                          max_length: int = 30) -> TitleGenerator:
    """
    タイトル生成器を作成
    
    Args:
        method: 生成方法 ("keyword", "gemini", "simple")
        api_key: Gemini APIキー
        max_length: 最大長
        
    Returns:
        TitleGeneratorインスタンス
    """
    method_map = {
        "keyword": TitleGenerationMethod.KEYWORD_EXTRACTION,
        "gemini": TitleGenerationMethod.GEMINI_API,
        "simple": TitleGenerationMethod.SIMPLE_TRUNCATION
    }
    
    gen_method = method_map.get(method, TitleGenerationMethod.KEYWORD_EXTRACTION)
    return TitleGenerator(method=gen_method, api_key=api_key, max_length=max_length)
