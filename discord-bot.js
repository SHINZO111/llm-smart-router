#!/usr/bin/env node
/**
 * Discord Bot - LLM Smart Router 連携
 *
 * OpenClawLLMRouter を使用してDiscordメッセージをルーティングする。
 *
 * コマンド:
 *   !local <text>   - ローカルLLMで処理
 *   !claude <text>   - Claudeで処理
 *   !stats           - セッション統計を表示
 *   !reload          - 設定をリロード
 *   !help            - ヘルプ表示
 *   その他            - 自動判定でルーティング
 *
 * 環境変数:
 *   DISCORD_BOT_TOKEN - Discord Bot トークン（必須）
 *   DISCORD_PREFIX    - コマンドプレフィックス（デフォルト: !）
 */

import { Client, GatewayIntentBits, Partials } from 'discord.js';
import OpenClawLLMRouter from './openclaw-integration.js';

// 設定
const TOKEN = process.env.DISCORD_BOT_TOKEN;
const PREFIX = process.env.DISCORD_PREFIX || '!';
const MAX_MESSAGE_LENGTH = 2000;
const MAX_INPUT_LENGTH = 4000; // ルーティングに渡す最大入力長

// 管理者ID（カンマ区切り）
const ADMIN_IDS = new Set(
  (process.env.DISCORD_ADMIN_IDS || '').split(',').map(id => id.trim()).filter(Boolean)
);

// レート制限: ユーザーごとの最終リクエスト時刻
const rateLimitMap = new Map();
const _rawRateLimit = parseInt(process.env.DISCORD_RATE_LIMIT_MS || '3000', 10);
const RATE_LIMIT_MS = (Number.isFinite(_rawRateLimit) && _rawRateLimit > 0)
  ? _rawRateLimit
  : 3000;

if (!TOKEN) {
  console.error('エラー: DISCORD_BOT_TOKEN 環境変数が設定されていません');
  process.exit(1);
}

// Discord クライアント初期化
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.DirectMessages,
  ],
  partials: [Partials.Channel],
});

// LLM Router 初期化
const router = new OpenClawLLMRouter();

/**
 * メッセージを2000文字ごとに分割して送信
 */
async function sendLongMessage(channel, text) {
  if (text.length <= MAX_MESSAGE_LENGTH) {
    await channel.send(text);
    return;
  }

  // 改行区切りで分割を試みる
  const chunks = [];
  let remaining = text;
  while (remaining.length > 0) {
    if (remaining.length <= MAX_MESSAGE_LENGTH) {
      chunks.push(remaining);
      break;
    }

    let splitIndex = remaining.lastIndexOf('\n', MAX_MESSAGE_LENGTH);
    if (splitIndex <= 0) {
      splitIndex = MAX_MESSAGE_LENGTH;
    }
    chunks.push(remaining.substring(0, splitIndex));
    remaining = remaining.substring(splitIndex).trimStart();
  }

  for (let i = 0; i < chunks.length; i++) {
    try {
      await channel.send(chunks[i]);
    } catch (error) {
      console.error(`メッセージ送信エラー (パート ${i + 1}/${chunks.length}):`, error.message);
      break;
    }
  }
}

/**
 * 管理者かどうかチェック
 */
function isAdmin(userId) {
  // DISCORD_ADMIN_IDS 未設定時は全員許可（後方互換）
  if (ADMIN_IDS.size === 0) return true;
  return ADMIN_IDS.has(userId);
}

/**
 * レート制限チェック
 * @returns {boolean} true = 許可, false = 制限中
 */
function checkRateLimit(userId) {
  const now = Date.now();
  const lastRequest = rateLimitMap.get(userId) || 0;
  if (now - lastRequest < RATE_LIMIT_MS) {
    return false;
  }
  rateLimitMap.set(userId, now);

  // 古いエントリをクリーンアップ（1000件超過時）
  if (rateLimitMap.size > 1000) {
    const cutoff = now - RATE_LIMIT_MS * 10;
    const keysToDelete = [];
    for (const [uid, ts] of rateLimitMap) {
      if (ts < cutoff) keysToDelete.push(uid);
    }
    for (const key of keysToDelete) {
      rateLimitMap.delete(key);
    }
  }

  return true;
}

/**
 * 入力バリデーション + レート制限チェック + ルーティング実行
 */
async function validateAndRoute(message, text) {
  if (text.length > MAX_INPUT_LENGTH) {
    await message.reply(`入力が長すぎます（最大${MAX_INPUT_LENGTH}文字）。`);
    return;
  }

  if (!checkRateLimit(message.author.id)) {
    await message.reply('リクエストが多すぎます。少し待ってからお試しください。');
    return;
  }

  await message.channel.sendTyping();
  try {
    const result = await router.handleDiscordMessage(
      { content: text },
      message.author.id,
    );

    if (result.success) {
      const modelInfo = result.model ? ` *(${result.model})*` : '';
      await sendLongMessage(message.channel, `${result.response}${modelInfo}`);
    } else {
      console.error('ルーティングエラー:', result.error);
      await message.reply('処理中にエラーが発生しました。再度お試しください。');
    }
  } catch (error) {
    console.error('メッセージ処理エラー:', error);
    await message.reply('処理中にエラーが発生しました。');
  }
}

/**
 * ヘルプメッセージを生成
 */
function getHelpMessage() {
  return [
    '**LLM Smart Router - Discord Bot**',
    '',
    `\`${PREFIX}local <テキスト>\` - ローカルLLM (LM Studio) で処理`,
    `\`${PREFIX}claude <テキスト>\` - Claude で処理`,
    `\`${PREFIX}stats\` - セッション統計を表示`,
    `\`${PREFIX}reload\` - 設定をリロード`,
    `\`${PREFIX}help\` - このヘルプを表示`,
    '',
    `プレフィックスなしのメンション/DMは自動判定でルーティングします。`,
  ].join('\n');
}

/**
 * 管理者コマンド定義
 */
const ADMIN_COMMANDS = {
  stats: async (message) => {
    const stats = router.getStats();
    await message.reply(`**セッション統計:**\n\`\`\`json\n${JSON.stringify(stats, null, 2)}\n\`\`\``);
  },
  reload: async (message) => {
    const result = router.reloadConfig();
    await message.reply(`設定リロード: ${result.message}`);
  },
};

// Ready イベント
client.on('ready', () => {
  console.log(`Discord Bot ログイン完了: ${client.user.tag}`);
  console.log(`コマンドプレフィックス: ${PREFIX}`);
  console.log(`参加サーバー数: ${client.guilds.cache.size}`);
});

// メッセージ受信イベント
client.on('messageCreate', async (message) => {
  // Bot自身のメッセージは無視
  if (message.author.bot) return;

  const content = message.content.trim();

  // プレフィックス付きコマンドの処理
  if (content.startsWith(PREFIX)) {
    const commandBody = content.slice(PREFIX.length);

    // !help
    if (commandBody === 'help') {
      await message.reply(getHelpMessage());
      return;
    }

    // 管理者コマンド
    const adminHandler = ADMIN_COMMANDS[commandBody];
    if (adminHandler) {
      if (!isAdmin(message.author.id)) {
        await message.reply('権限がありません。');
        return;
      }
      await adminHandler(message);
      return;
    }

    // !local / !claude / その他 → validateAndRoute に委譲
    await validateAndRoute(message, content);
    return;
  }

  // メンションまたはDMの場合は自動判定
  const isMentioned = message.mentions.has(client.user);
  const isDM = !message.guild;

  if (isMentioned || isDM) {
    // メンション部分を除去
    const cleanContent = content
      .replace(new RegExp(`<@!?${client.user.id}>`, 'g'), '')
      .trim();

    if (!cleanContent) return;

    await validateAndRoute(message, cleanContent);
  }
});

// エラーハンドリング
client.on('error', (error) => {
  console.error('Discord クライアントエラー:', error);
});

// グレースフルシャットダウン
function gracefulShutdown(signal) {
  console.log(`\n${signal} 受信 - シャットダウン中...`);
  client.destroy();
  process.exit(0);
}

process.on('SIGINT', () => gracefulShutdown('SIGINT'));
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));

// ログイン
client.login(TOKEN).catch((error) => {
  const safeMessage = (error.message || '').replaceAll(TOKEN, '[REDACTED]');
  console.error('Discord ログインエラー:', safeMessage);
  process.exit(1);
});
