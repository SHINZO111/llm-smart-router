# OpenClaw モデル切り替え手順書

## 概要

OpenClawで使用するLLMを **Kimi → Claude → ローカルLLM** の優先順位で切り替える際の設定手順。

---

## 関連ファイル一覧

| # | ファイル | 役割 |
|---|---------|------|
| 1 | `~\.openclaw\openclaw.json` | グローバル設定（プライマリモデル・フォールバック順） |
| 2 | `~\.openclaw\agents\main\agent\agent.json` | エージェント固有のモデル指定（**これが最優先**） |
| 3 | `~\.openclaw\agents\main\agent\models.json` | 利用可能モデルのレジストリ（モデル定義） |
| 4 | `~\.openclaw\agents\main\agent\auth-profiles.json` | APIキー・使用統計・クールダウン状態 |
| 5 | `~\.openclaw\lmstudio-config.json` | LM Studio用の簡易設定 |
| 6 | `~\.openclaw\restart-openclaw.bat` | 再起動バッチ |

> `~` = `C:\Users\sawas`

---

## 設定の優先順位

```
agent.json (エージェント固有) > openclaw.json (グローバルデフォルト)
```

**両方を変更しないとモデルが切り替わらない。**

---

## 手順

### Step 1: `agent.json` を編集（最優先設定）

**ファイル:** `~\.openclaw\agents\main\agent\agent.json`

#### Kimi を使う場合

```json
{
  "name": "localrnj",
  "llm": {
    "model": "kimi-k2-0905-preview",
    "provider": "moonshot",
    "endpoint": "https://api.moonshot.ai/v1"
  }
}
```

#### Claude を使う場合

```json
{
  "name": "localrnj",
  "llm": {
    "model": "claude-haiku-4-5-20251001",
    "provider": "anthropic",
    "endpoint": "https://api.anthropic.com/v1"
  }
}
```

#### ローカルLLM（qwen3-vl-8b）を使う場合

```json
{
  "name": "localrnj",
  "llm": {
    "model": "qwen/qwen3-vl-8b",
    "provider": "synthetic",
    "endpoint": "http://127.0.0.1:1234/api/v1"
  }
}
```

---

### Step 2: `openclaw.json` のフォールバック順を編集

**ファイル:** `~\.openclaw\openclaw.json`

`agents.defaults.model` セクションを編集する。

#### Kimi優先の場合

```json
"model": {
  "primary": "moonshot/kimi-k2-0905-preview",
  "fallbacks": [
    "anthropic/claude-haiku-4-5-20251001",
    "synthetic/qwen/qwen3-vl-8b",
    "synthetic/qwen/qwen3-4b-thinking-2507",
    "synthetic/deepseek/deepseek-r1-0528-qwen3-8b"
  ]
}
```

#### Claude優先の場合

```json
"model": {
  "primary": "anthropic/claude-haiku-4-5-20251001",
  "fallbacks": [
    "moonshot/kimi-k2-0905-preview",
    "synthetic/qwen/qwen3-vl-8b",
    "synthetic/qwen/qwen3-4b-thinking-2507",
    "synthetic/deepseek/deepseek-r1-0528-qwen3-8b"
  ]
}
```

#### ローカルLLM優先の場合

```json
"model": {
  "primary": "synthetic/qwen/qwen3-vl-8b",
  "fallbacks": [
    "synthetic/qwen/qwen3-4b-thinking-2507",
    "synthetic/deepseek/deepseek-r1-0528-qwen3-8b",
    "synthetic/essentialai/rnj-1",
    "kimi-coding/k2p5",
    "moonshot/kimi-k2-0905-preview"
  ]
}
```

---

### Step 3: 使用制限のリセット（必要な場合）

**ファイル:** `~\.openclaw\agents\main\agent\auth-profiles.json`

レート制限やクールダウンでプロバイダが無効化されている場合、`usageStats` を手動リセットする。

#### Kimiのレート制限を解除

`usageStats` 内の該当プロバイダのエントリを以下に書き換え:

```json
"kimi-coding:default": {
  "lastUsed": 0,
  "errorCount": 0
},
"moonshot:default": {
  "errorCount": 0
}
```

#### Claudeの課金制限を解除

```json
"anthropic:default": {
  "lastUsed": 0,
  "errorCount": 0
}
```

> `disabledUntil`, `disabledReason`, `failureCounts`, `cooldownUntil` を削除すればOK。

---

### Step 4: OpenClaw を再起動

```bat
# 方法1: バッチファイル（推奨）
~\.openclaw\restart-openclaw.bat

# 方法2: PowerShellで手動
Get-CimInstance Win32_Process -Filter "name='node.exe'" |
  Where-Object { $_.CommandLine -like '*openclaw*gateway*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 2
openclaw gateway --port 18789
```

---

## プロバイダ別 接続情報

| プロバイダ | エンドポイント | APIキー場所 |
|-----------|---------------|------------|
| **synthetic** (ローカル) | `http://127.0.0.1:1234/v1` | `lm-studio` (固定) |
| **moonshot** (Kimi) | `https://api.moonshot.ai/v1` | `auth-profiles.json` |
| **kimi-coding** (Kimi) | Kimi内蔵 | `auth-profiles.json` |
| **anthropic** (Claude) | `https://api.anthropic.com/v1` | `auth-profiles.json` |

---

## ローカルLLM 利用可能モデル一覧（LM Studio）

| モデルID | 名前 | VL | Reasoning |
|---------|------|----|-----------|
| `qwen/qwen3-vl-8b` | Qwen3 VL 8B | Yes | No |
| `qwen/qwen3-vl-4b` | Qwen3 VL 4B | Yes | No |
| `qwen/qwen3-4b-2507` | Qwen3 4B | No | No |
| `qwen/qwen3-4b-thinking-2507` | Qwen3 4B Thinking | No | Yes |
| `deepseek/deepseek-r1-0528-qwen3-8b` | DeepSeek R1 8B | No | Yes |
| `essentialai/rnj-1` | RNJ-1 | No | No |
| `mistralai/ministral-3-3b` | Ministral 3 3B | No | No |
| `liquid/lfm2.5-1.2b` | LFM 2.5 1.2B | No | No |

---

## クイックリファレンス

```
Kimiに切り替え:
  1. agent.json     → model: "kimi-k2-0905-preview", provider: "moonshot"
  2. openclaw.json  → primary: "moonshot/kimi-k2-0905-preview"
  3. 再起動

Claudeに切り替え:
  1. agent.json     → model: "claude-haiku-4-5-20251001", provider: "anthropic"
  2. openclaw.json  → primary: "anthropic/claude-haiku-4-5-20251001"
  3. 再起動

ローカルに切り替え:
  1. agent.json     → model: "qwen/qwen3-vl-8b", provider: "synthetic"
  2. openclaw.json  → primary: "synthetic/qwen/qwen3-vl-8b"
  3. 再起動
```
