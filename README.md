# WeChat MCP Server

让 AI 能读写微信消息的 MCP Server。

AI agents can read and write WeChat messages through the Model Context Protocol (MCP).

---

## Features

- 📥 Read unread / recent WeChat messages
- 📤 Send WeChat messages via shortcut automation
- 🔍 Search contacts and open chats
- 🟡 Detect unread red dots via OpenCV
- 👁️ Visual analysis of chat screenshots via Qwen-VL

## Requirements

- **Python** 3.10+
- **OS** macOS (WeChat for Mac)
- **WeChat** installed and logged in, visible on the desktop
- **cua-driver** — keyboard shortcut automation layer

## Installation

```bash
pip install wechat-mcp
```

## Quick Start

1. Make sure WeChat is **logged in** and the main window is **visible on your desktop**.

2. Start the MCP server:

```bash
python -m wechat_mcp.server
```

3. Add the server to your MCP client configuration (e.g., `claude_desktop_config.json`, `~/.hermes/config.yaml`):

```json
{
  "mcpServers": {
    "wechat": {
      "command": "python",
      "args": ["-m", "wechat_mcp.server"]
    }
  }
}
```

## Configuration

Chat config files live at `~/.wechat_bot/<name>_chat.json`.

Each file defines a contact that the bot can interact with:

```json
{
  "name": "张三",
  "keywords": ["提醒", "通知"],
  "schedule": {
    "enabled": true,
    "interval_minutes": 10
  }
}
```

| Field | Description |
|---|---|
| `name` | WeChat contact display name |
| `keywords` | Trigger keywords for automated responses |
| `schedule` | Optional polling schedule |

## Tech Stack

| Component | Technology |
|---|---|
| Automation driver | [cua-driver](https://github.com/nousresearch/cua-driver) — keyboard shortcuts |
| Red dot detection | OpenCV — unread badge detection |
| Visual understanding | Qwen-VL — screenshot analysis and OCR |
| Server protocol | Model Context Protocol (MCP) |

## Project Structure

```
wechat_mcp/
├── server.py          # MCP server entry point
├── core.py            # WeChatController — main automation interface
├── detector.py        # OpenCV red-dot detection
├── analyzer.py        # Qwen-VL visual analysis
├── config.py          # Config loader
└── __init__.py        # Package exports
```

## License

MIT — see [LICENSE](LICENSE)

## Author

**Lozzi** — built for AI-powered WeChat automation.
