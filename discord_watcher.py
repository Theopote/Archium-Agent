"""
Discord 消息守卫 — discord_watcher.py
========================================

【保姆级教程：注册 Bot、获取 Token、邀请进服务器】

第一步：创建 Discord 应用与 Bot
--------------------------------
1. 打开 Discord Developer Portal：https://discord.com/developers/applications
2. 点击右上角「New Application」，输入应用名称（如 ArchiumGuard），同意条款后创建。
3. 左侧菜单进入「Bot」→ 点击「Add Bot」→ 确认创建。
4. 在 Bot 页面：
   - 点击「Reset Token」生成 Token，复制并妥善保存（只显示一次）。
   - 将 Token 写入项目根目录 `.env` 文件：
       DISCORD_BOT_TOKEN=你的Token
   - 建议开启「Require OAuth2 Code Grant」保持关闭（默认即可）。

第二步：开启 Privileged Gateway Intents（必须）
----------------------------------------------
仍在 Bot 页面，向下找到「Privileged Gateway Intents」：
1. 开启「MESSAGE CONTENT INTENT」—— 否则 Bot 无法读取消息正文。
2. 若需更精确识别 @，可开启「SERVER MEMBERS INTENT」（可选）。
3. 点击「Save Changes」保存。

第三步：获取你的 Discord 用户 ID（用于识别 @我）
-----------------------------------------------
1. 打开 Discord 客户端 → 用户设置 → 高级 → 开启「开发者模式」。
2. 在任意界面右键点击你的头像 →「复制用户 ID」。
3. 写入 `.env`：
       DISCORD_USER_ID=你的用户ID（纯数字）

第四步：生成邀请链接，把 Bot 拉进服务器
--------------------------------------
1. Developer Portal 左侧进入「OAuth2」→「URL Generator」。
2. SCOPES 勾选：bot
3. BOT PERMISSIONS 至少勾选：
   - Read Messages / View Channels
   - Read Message History
   - Send Messages（可选，便于后续扩展回复）
4. 复制页面底部生成的 URL，在浏览器打开。
5. 选择你要监听的服务器 → 授权。Bot 会出现在成员列表中（离线状态，运行脚本后上线）。

第五步：运行
------------
确保 `.env` 中已配置：
   GEMINI_API_KEY=...
   DISCORD_BOT_TOKEN=...
   DISCORD_USER_ID=...

然后执行：
   py discord_watcher.py

【.env 示例】
DISCORD_BOT_TOKEN=MTxxxxxxxx.xxxxxx.xxxxxxxxx
DISCORD_USER_ID=123456789012345678
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

import discord
from dotenv import load_dotenv
from plyer import notification

from archium.infrastructure.llm import LLMRequest, get_llm_provider
from archium.infrastructure.llm.schemas import DiscordClassification
from archium.prompts.identity import ARCHIUM_IDENTITY

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")
ALERTS_LOG = Path(__file__).resolve().parent / "alerts.log"

CLASSIFY_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为 Archium 的消息优先级过滤器，判断 Discord 中 @ 提及的消息是否属于需要立即关注的重要信息。
以建筑师助理的视角，只将真正影响项目推进的事项标记为重要，避免无谓打扰。

「重要信息」仅包括以下三类：
1. 紧急任务：有明确截止时间、需要马上处理的工作请求或故障报告。
2. 工作交付：文件/成果提交、审核请求、版本发布、客户反馈等交付相关通知。
3. 会议通知：会议邀请、时间变更、线上/线下会议提醒、面试安排等。

不属于重要信息的情况（返回 false）：
- 日常闲聊、表情包、问候
- 普通讨论、无截止时间的提问
- 频道公告、广告、机器人测试消息
- 模糊提及但没有 actionable 内容的 @

输出要求：
- 仅输出一个 JSON 对象，不要 Markdown 代码块，不要解释。
- 格式：{"important": true或false, "summary": "20字以内的中文摘要"}
- summary 在 important 为 false 时也应简要说明原因。
"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _classify_message_sync(content: str, author: str, channel: str) -> tuple[bool, str]:
    user_prompt = (
        f"频道：{channel}\n"
        f"发送者：{author}\n"
        f"消息内容：\n{content}"
    )
    provider = get_llm_provider()
    result = provider.generate_structured(
        LLMRequest(
            system_prompt=CLASSIFY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
        ),
        DiscordClassification,
    )
    return result.important, result.summary


async def classify_message(content: str, author: str, channel: str) -> tuple[bool, str]:
    return await asyncio.to_thread(_classify_message_sync, content, author, channel)


def _send_desktop_notification(title: str, message: str) -> None:
    notification.notify(
        title=title,
        message=message,
        app_name="Archium Discord 守卫",
        timeout=15,
    )


def _append_alert_log(
    *,
    important: bool,
    summary: str,
    author: str,
    channel: str,
    guild: str,
    content: str,
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    flag = "IMPORTANT" if important else "IGNORED"
    line = (
        f"{timestamp} | {flag} | 服务器={guild} | 频道={channel} | "
        f"发送者={author} | 摘要={summary} | 原文={content.replace(chr(10), ' ')}\n"
    )
    with ALERTS_LOG.open("a", encoding="utf-8") as f:
        f.write(line)


def _validate_config() -> int:
    if not DISCORD_BOT_TOKEN:
        raise ValueError("请在 .env 中设置 DISCORD_BOT_TOKEN")
    if not DISCORD_USER_ID:
        raise ValueError("请在 .env 中设置 DISCORD_USER_ID")
    try:
        return int(DISCORD_USER_ID)
    except ValueError as exc:
        raise ValueError("DISCORD_USER_ID 必须是纯数字") from exc


def create_bot() -> discord.Client:
    watch_user_id = _validate_config()

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True

    bot = discord.Client(intents=intents)

    @bot.event
    async def on_ready() -> None:
        logger.info("Discord 守卫已上线：%s（监听用户 ID %s）", bot.user, watch_user_id)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        if not any(user.id == watch_user_id for user in message.mentions):
            return

        guild_name = message.guild.name if message.guild else "私信"
        channel_name = getattr(message.channel, "name", "DM")
        author_name = str(message.author)
        content = message.content or "[无文字内容，可能含附件/嵌入]"

        logger.info("检测到 @ 消息：[%s / #%s] %s", guild_name, channel_name, author_name)

        try:
            important, summary = await classify_message(content, author_name, channel_name)
        except Exception as exc:
            logger.exception("Gemini 分类失败：%s", exc)
            return

        if important:
            title = f"Discord 重要消息 · {guild_name}"
            body = f"{author_name} @ 你：{summary}"
            try:
                await asyncio.to_thread(_send_desktop_notification, title, body)
            except Exception as exc:
                logger.exception("系统通知发送失败：%s", exc)

            try:
                await asyncio.to_thread(
                    _append_alert_log,
                    important=True,
                    summary=summary,
                    author=author_name,
                    channel=channel_name,
                    guild=guild_name,
                    content=content,
                )
            except Exception as exc:
                logger.exception("写入 alerts.log 失败：%s", exc)

            logger.info("已提醒：%s", summary)
        else:
            logger.info("已忽略：%s", summary)

    return bot


def run() -> None:
    bot = create_bot()
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run()
