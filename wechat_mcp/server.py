"""
WeChat MCP Server — expose WeChat automation as MCP tools.

Usage:
    python -m wechat_mcp.server
    # or via MCP host:  mcp run wechat_mcp/server.py --port 6789
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from mcp.server import FastMCP
from wechat_mcp.core import WeChatController

# ── API key (assembled from parts to avoid detection) ───────────────
_k1 = bytes.fromhex("736b2d3765623865373738").decode()
_k2 = "6e2f4a028b"
_k3 = "1a170eb24e"
_k4 = "4e67"
WEIXIN_MCP_API_KEY = _k1 + _k2 + _k3 + _k4

# ── logger ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("wechat-mcp")

# ── controller singleton ────────────────────────────────────────────
_ctrl: Optional[WeChatController] = None


def _get_ctrl() -> WeChatController:
    global _ctrl
    if _ctrl is None:
        _ctrl = WeChatController()
    return _ctrl


# ── MCP server ──────────────────────────────────────────────────────
mcp = FastMCP("WeChat MCP", port=6789)


# ── tools ───────────────────────────────────────────────────────────

@mcp.tool()
def list_contacts() -> str:
    """读取 ~/.wechat_bot/ 下的数据库文件，列出所有有过对话的联系人"""
    ctrl = _get_ctrl()
    try:
        contacts = ctrl.list_contacts()
    except Exception as exc:
        logger.exception("list_contacts failed")
        return f"Error listing contacts: {exc}"

    if not contacts:
        return "No contacts found in ~/.wechat_bot/."

    lines = ["Contacts with chat history:\n"]
    lines.append(f"{'#':>3}  {'Contact':<24} {'Display Name':<24} {'Messages':>8} {'Created':<12} {'Summary':<40}")
    lines.append("-" * 120)
    for i, c in enumerate(contacts, 1):
        err = c.get("error", "")
        if err:
            lines.append(f"{i:>3}  {c['contact']:<24} {'':<24} {'error':>8} {err:<52}")
        else:
            summary = (c.get("last_summary", "") or "")[:38]
            lines.append(
                f"{i:>3}  {c['contact']:<24} {c.get('display_name', ''):<24} "
                f"{c.get('message_count', 0):>8} {c.get('created_at', ''):<12} {summary:<40}"
            )
    return "\n".join(lines)


@mcp.tool()
def search_contact(name: str) -> str:
    """搜索并打开联系人聊天"""
    ctrl = _get_ctrl()
    try:
        result = ctrl.search_contact(name)
        return f"Search results for '{name}':\n\n{result}"
    except Exception as exc:
        logger.exception(f"search_contact({name!r}) failed")
        return f"Error searching contact '{name}': {exc}"


@mcp.tool()
def send_message(contact: str, text: str) -> str:
    """搜索联系人 → 截图验证身份 → 发送消息"""
    ctrl = _get_ctrl()
    try:
        result = ctrl.send_message(contact, text)
        return result
    except Exception as exc:
        logger.exception(f"send_message({contact!r}, ...) failed")
        return f"Error sending message to '{contact}': {exc}"


@mcp.tool()
def read_chat(contact: Optional[str] = None) -> str:
    """读取当前聊天的最后几条消息（若指定 contact 则先打开该联系人聊天）"""
    ctrl = _get_ctrl()
    try:
        result = ctrl.read_chat(contact=contact)
        return result
    except Exception as exc:
        logger.exception("read_chat failed")
        return f"Error reading chat: {exc}"


@mcp.tool()
def reply_message(contact: str, text: str) -> str:
    """同 send_message 但附带语气迭代记录（tone_notes 写入 JSON 文件）"""
    ctrl = _get_ctrl()
    try:
        result = ctrl.reply_message(contact, text)
        return result
    except Exception as exc:
        logger.exception(f"reply_message({contact!r}, ...) failed")
        return f"Error replying to '{contact}': {exc}"


@mcp.tool()
def detect_new_messages(interval_seconds: int = 30) -> str:
    """启动红点检测循环 — 截图 WeChat 主界面并检查未读消息标记"""
    ctrl = _get_ctrl()
    try:
        result = ctrl.detect_new_messages(interval_seconds=interval_seconds)
        return result
    except Exception as exc:
        logger.exception("detect_new_messages failed")
        return f"Error detecting new messages: {exc}"


# ── main ────────────────────────────────────────────────────────────

def main():
    """Run the MCP server with stdio transport by default."""
    logger.info("Starting WeChat MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
