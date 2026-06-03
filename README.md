# WeChat MCP Server

**让 AI 读写微信消息** — 通过 Model Context Protocol (MCP) 标准协议，AI 助手可以直接搜索联系人、读取聊天、发送消息。

AI agents can read and write WeChat messages through the Model Context Protocol (MCP).

---

## ✨ 功能 Features

| 功能 | 说明 |
|------|------|
| 📥 **读聊天** | 截取聊天窗口 → Qwen-VL 识别文字 → 返回结构化消息 |
| 📤 **发消息** | 搜索联系人 → 截图验证 → 粘贴发送 |
| 🔍 **搜联系人** | Cmd+F 搜索 → 自动验证是否打开正确聊天 |
| 🟡 **红点检测** | OpenCV 检测未读消息红点位置 |
| 👁️ **视觉分析** | 使用阿里云 DashScope Qwen-VL-Plus 理解截图内容 |

## 📋 需求 Requirements

- **macOS** (WeChat for Mac)
- **Python** 3.10+
- **WeChat** 已登录且主窗口可见
- **cua-driver** — 快捷键自动化层（[GitHub](https://github.com/nousresearch/cua-driver)）
- **DashScope API Key** — 阿里云百炼视觉模型（[免费额度](https://dashscope.aliyun.com)）

## 🚀 快速开始 Quick Start

### 1. 安装

```bash
pip install wx-mcp-server
```

或者从源码安装：

```bash
git clone https://github.com/jp7454yv4f-sudo/WeChat-mcp.git
cd WeChat-mcp
pip install -e .
```

### 2. 配置 API Key

```bash
# 方式一：环境变量（推荐）
export WEIXIN_MCP_API_KEY='sk-...'

# 方式二：配置文件
# 创建 ~/.wechat_mcp/config.json:
# {"dashscope_api_key": "sk-..."}
```

> API Key 获取：https://dashscope.aliyun.com → 模型广场 → Qwen-VL-Plus

### 3. 启动

```bash
wechat-mcp
```

### 4. 配置 MCP 客户端

**Claude Desktop:**
```json
{
  "mcpServers": {
    "wechat": {
      "command": "wechat-mcp"
    }
  }
}
```

**Cursor / Windsurf:**
```
MCP Server → Add → Command: wechat-mcp
```

## 🛠️ 可用工具 Available Tools

| 工具 | 参数 | 说明 |
|------|------|------|
| `search_contact` | `name` | 搜索并打开联系人聊天 |
| `send_message` | `contact, text` | 发送消息（自动验证） |
| `read_chat` | `contact?` | 读取当前/指定聊天内容 |
| `reply_message` | `contact, text` | 发送消息 + 语气迭代记录 |
| `list_contacts` | — | 列出所有有过对话的联系人 |
| `detect_new_messages` | `interval_seconds` | 红点检测循环 |

## 🔧 技术栈 Tech Stack

| 组件 | 技术 |
|------|------|
| 协议 | Model Context Protocol (MCP) |
| 自动化驱动 | cua-driver / osascript 快捷键 |
| 截图 | macOS screencapture |
| 红点检测 | OpenCV HSV 颜色空间 |
| 视觉理解 | Qwen-VL-Plus (DashScope) |

## 💰 运营成本

每次 API 调用约 **0.002元**（Qwen-VL-Plus），完整读写一次约 **0.01元**。
红点检测为本地 OpenCV，零成本。

## 💳 定价 Pricing

| 版本 | 价格 | 说明 |
|------|------|------|
| **个人版** | **免费** | AGPL v3 开源，个人/内部使用 |
| **商业版** | **¥499/项目** | 闭源商用，含 1 年更新 |
| **企业版** | **¥2999/年** | 无限项目、优先支持、定制开发 |

**购买方式：**
- 支付宝转账（备注 wx-mcp）或联系微信
- 商业授权咨询：jp7454yv4f-sudo@users.noreply.github.com

## 📄 许可 License

**GNU AGPL v3** — 开源但保护作者权益。
- ✅ 个人/内部使用免费
- ✅ 修改后自用免费
- ❌ 修改后作为 SaaS/网络服务提供须开源修改内容
- ❌ 闭源的商业分发需要购买商业版授权

## 🧑‍💻 作者 Author

**Lozzi** — built for AI-powered WeChat automation.
