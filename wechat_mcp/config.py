"""
WeChat MCP Config — 配置文件加载模块

配置优先级（从高到低）：
  1. 环境变量 WEIXIN_MCP_API_KEY
  2. 环境变量 DASHSCOPE_API_KEY
  3. ~/.wechat_mcp/config.json 中的 dashscope_api_key 字段
"""

import json
import os
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".wechat_mcp"
CONFIG_PATH = CONFIG_DIR / "config.json"
DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def ensure_config_dir() -> None:
    """确保配置目录存在。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def resolve_api_key() -> str:
    """从环境变量 → 配置文件 依次尝试获取 DashScope API Key。"""
    # 1. 环境变量
    env_key = os.environ.get("WEIXIN_MCP_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if env_key:
        return env_key

    # 2. 配置文件
    try:
        if CONFIG_PATH.exists():
            cfg = json.loads(CONFIG_PATH.read_text())
            key = cfg.get("dashscope_api_key", "")
            if key:
                return key
    except (json.JSONDecodeError, OSError):
        pass

    # 3. 提示
    print(
        "\n[!] DashScope API Key 未设置！\n"
        "    请通过以下任一方式配置：\n"
        "\n"
        "    方式一：环境变量\n"
        "      export WEIXIN_MCP_API_KEY='sk-...'\n"
        "\n"
        "    方式二：配置文件\n"
        f"      创建 {CONFIG_PATH}，内容：\n"
        '      {"dashscope_api_key": "sk-..."}\n'
        "\n"
        "    阿里云百炼 DashScope: https://dashscope.aliyun.com\n",
        file=sys.stderr,
    )
    return ""
