"""
WeChat MCP Core — 微信操作核心模块

基于 subprocess + screencapture + OpenCV + DashScope Qwen-VL
不依赖 accessibility 权限，不使用已损坏的 MCP wechat 工具。

关键依赖:
  - subprocess: 调用 cua-driver / osascript 发送快捷键
  - screencapture (macOS): 窗口截图
  - OpenCV (cv2): 红点检测与图片裁剪
  - requests: 调用 DashScope Qwen-VL-Plus/OCR

API Key: 从环境变量 WEIXIN_MCP_API_KEY 或 ~/.wechat_mcp/config.json 读取
DashScope base: https://dashscope.aliyuncs.com/compatible-mode/v1
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import requests

# ── API 配置 ──────────────────────────────────────────────────────────
# 优先从环境变量读取，其次从 ~/.wechat_mcp/config.json 读取
# 绝不硬编码在源码中

from wechat_mcp.config import resolve_api_key, DASHSCOPE_BASE

DASHSCOPE_API_KEY = resolve_api_key()

# ── 常量 ──────────────────────────────────────────────────────────────

LEFT_PANEL_WIDTH = 280   # 左侧联系人/聊天列表宽度（px）
ROW_HEIGHT = 60          # 每个联系人行高估计值（px）
KEY_DELAY = 0.35         # 每次键盘操作后休眠秒数
SUBPROCESS_TIMEOUT = 15  # subprocess 默认超时（秒）
VL_TIMEOUT = 60          # Qwen-VL API 超时（秒）
SCREENSHOT_DIR = Path.home() / ".wechat_mcp" / "screenshots"


# ══════════════════════════════════════════════════════════════════════
#  底层工具函数
# ══════════════════════════════════════════════════════════════════════


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """包装 subprocess.run，自动加 capture_output 和 timeout。"""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("timeout", SUBPROCESS_TIMEOUT)
    kwargs.setdefault("text", True)
    return subprocess.run(cmd, **kwargs)


def _wechat_pid() -> Optional[int]:
    """通过 pgrep 获取微信进程 PID，未运行时返回 None。"""
    try:
        r = _run(["pgrep", "-x", "WeChat"])
        if r.returncode == 0 and r.stdout.strip():
            return int(r.stdout.strip())
    except Exception:
        pass
    return None


def _window_rect() -> Optional[tuple[int, int, int, int]]:
    """
    通过 osascript 获取微信主窗口位置 (x, y, w, h)。
    返回 None 表示获取失败。
    """
    script = (
        'tell application "System Events"\n'
        '    tell process "WeChat"\n'
        '        set win to first window\n'
        '        set {x0, y0} to position of win\n'
        '        set {w0, h0} to size of win\n'
        '        return (x0 as text) & "," & (y0 as text) & "," & (w0 as text) & "," & (h0 as text)\n'
        '    end tell\n'
        'end tell'
    )
    try:
        r = _run(["osascript", "-e", script])
        if r.returncode != 0 or not r.stdout.strip():
            return None
        parts = r.stdout.strip().split(",")
        if len(parts) != 4:
            return None
        return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
    except Exception as e:
        print(f"[WARN] 获取窗口位置失败: {e}", file=sys.stderr)
        return None


def _session_dir() -> Path:
    """创建并返回本次会话的截图目录（按时间戳区分）。"""
    path = SCREENSHOT_DIR / str(int(time.time()))
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── 截图 ──────────────────────────────────────────────────────────────


def _screenshot(path: str | Path) -> bool:
    """全屏截图（降级方案）。"""
    try:
        r = _run(["screencapture", "-x", "-C", str(path)])
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print("[WARN] screencapture 超时", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[WARN] screencapture 失败: {e}", file=sys.stderr)
        return False


def _screenshot_window(path: str | Path) -> bool:
    """截取微信主窗口区域（优先使用 osascript 获取窗口坐标）。"""
    rect = _window_rect()
    if rect is not None:
        x, y, w, h = rect
        region = f"{x},{y},{w},{h}"
        try:
            r = _run(["screencapture", "-x", "-R", region, str(path)])
            if r.returncode == 0:
                return True
        except Exception:
            pass
    # 降级：全屏截图
    return _screenshot(path)


# ── 键盘事件（cua-driver 优先，osascript 降级） ─────────────────────


def _cua_keyboard(payload: dict) -> bool:
    """通过 cua-driver 发送键盘事件。"""
    pid = _wechat_pid()
    if pid is None:
        return False
    payload["pid"] = pid
    try:
        r = _run(
            ["cua-driver", "keyboard", "--json", json.dumps(payload)],
            timeout=5,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False  # cua-driver 不存在，由调用方处理降级
    except Exception as e:
        print(f"[WARN] cua-driver 键盘失败: {e}", file=sys.stderr)
        return False


def _cmd_key(key: str) -> bool:
    """发送 Cmd+Key 组合键（cua-driver 优先）。"""
    payload = {"type": "tap", "key": key, "modifiers": ["cmd"]}
    if _cua_keyboard(payload):
        return True

    # 降级：osascript
    script = (
        f'tell application "System Events"\n'
        f'    tell process "WeChat"\n'
        f'        keystroke "{key}" using command down\n'
        f'    end tell\n'
        f'end tell'
    )
    try:
        r = _run(["osascript", "-e", script], timeout=5)
        return r.returncode == 0
    except Exception as e:
        print(f"[WARN] osascript 组合键失败: {e}", file=sys.stderr)
        return False


def _tap_key(key: str) -> bool:
    """发送单键（cua-driver 优先）。"""
    payload = {"type": "tap", "key": key}
    if _cua_keyboard(payload):
        return True

    # 降级：osascript
    script = (
        f'tell application "System Events"\n'
        f'    tell process "WeChat"\n'
        f'        keystroke "{key}"\n'
        f'    end tell\n'
        f'end tell'
    )
    try:
        r = _run(["osascript", "-e", script], timeout=5)
        return r.returncode == 0
    except Exception as e:
        print(f"[WARN] osascript 按键失败: {e}", file=sys.stderr)
        return False


# ── 剪贴板 ────────────────────────────────────────────────────────────


def _pbcopy(text: str) -> bool:
    """将文本写入系统剪贴板。"""
    try:
        r = _run(["pbcopy"], input=text)
        return r.returncode == 0
    except Exception as e:
        print(f"[WARN] pbcopy 失败: {e}", file=sys.stderr)
        return False


# ── 图片处理 ──────────────────────────────────────────────────────────


def _crop_image(
    src_path: str | Path,
    dst_path: str | Path,
    x: int, y: int, w: int, h: int,
) -> bool:
    """使用 OpenCV 裁剪图片区域。"""
    try:
        img = cv2.imread(str(src_path))
        if img is None:
            print(f"[WARN] OpenCV 无法读取: {src_path}", file=sys.stderr)
            return False
        cropped = img[y : y + h, x : x + w]
        cv2.imwrite(str(dst_path), cropped)
        return True
    except Exception as e:
        print(f"[WARN] 图片裁剪失败: {e}", file=sys.stderr)
        return False


# ── DashScope Qwen-VL 调用 ────────────────────────────────────────────


def _call_qwen_vl(image_path: str | Path, prompt: str) -> Optional[str]:
    """
    调用 DashScope Qwen-VL-Plus 视觉模型。
    图片以 base64 data URI 方式传入。
    返回模型输出文本，失败返回 None。
    """
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "qwen-vl-plus",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 1024,
    }

    try:
        resp = requests.post(
            f"{DASHSCOPE_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=VL_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[WARN] Qwen-VL 调用失败: {e}", file=sys.stderr)
        if "resp" in locals():
            print(f"[DEBUG] status={resp.status_code} body={resp.text[:300]}", file=sys.stderr)
        return None


# ══════════════════════════════════════════════════════════════════════
#  WeChatController
# ══════════════════════════════════════════════════════════════════════


class WeChatController:
    """微信操作核心控制器。

    提供搜索联系人、发送消息、读取聊天、红点检测、按坐标获取联系人名字等功能。
    所有 UI 操作通过 cua-driver → 快捷键完成，截图使用 screencapture，
    视觉理解使用 DashScope Qwen-VL-Plus。
    """

    def __init__(self) -> None:
        self._pid: Optional[int] = _wechat_pid()
        if self._pid is None:
            print("[INFO] 微信尚未运行，等待启动…", file=sys.stderr)

    # ── 进程/窗口管理 ────────────────────────────────────────────────

    @property
    def pid(self) -> Optional[int]:
        """获取微信 PID（每次访问重新检测）。"""
        self._pid = _wechat_pid()
        return self._pid

    def is_running(self) -> bool:
        """微信是否正在运行。"""
        return self.pid is not None

    def bring_to_front(self) -> bool:
        """将微信窗口带到前台并激活。"""
        # 确保微信已打开
        try:
            _run(["open", "-a", "WeChat"], timeout=10)
        except Exception:
            pass

        # osascript 激活
        try:
            r = _run(["osascript", "-e", 'tell application "WeChat" to activate'])
            success = r.returncode == 0
        except Exception as e:
            print(f"[WARN] 激活微信失败: {e}", file=sys.stderr)
            success = False

        time.sleep(0.5)
        return success

    # ── 搜索联系人 ────────────────────────────────────────────────────

    def search_contact(self, name: str) -> bool:
        """搜索并打开联系人聊天。

        流程:
          1. bring_to_front
          2. Cmd+F  打开搜索
          3. Cmd+A  全选已有内容
          4. pbcopy 写入联系人名字
          5. Cmd+V  粘贴
          6. Enter  确认搜索
          7. Escape 关闭搜索框（使聊天区获得焦点）
          8. 截图验证是否显示聊天窗口

        Args:
            name: 联系人名字（支持模糊匹配）。

        Returns:
            True 如果成功打开该联系人的聊天窗口。
        """
        if not self.bring_to_front():
            print("[WARN] 无法激活微信窗口", file=sys.stderr)
            return False

        sess = _session_dir()

        # 1. Cmd+F 打开搜索
        if not _cmd_key("f"):
            print("[WARN] Cmd+F 打开搜索失败", file=sys.stderr)
            return False
        time.sleep(KEY_DELAY)

        # 2. Cmd+A 全选
        _cmd_key("a")
        time.sleep(KEY_DELAY)

        # 3. pbcopy 写入名字
        if not _pbcopy(name):
            print("[WARN] 复制联系人名字到剪贴板失败", file=sys.stderr)
            return False
        time.sleep(0.2)

        # 4. Cmd+V 粘贴
        if not _cmd_key("v"):
            print("[WARN] Cmd+V 粘贴失败", file=sys.stderr)
            return False
        time.sleep(KEY_DELAY)

        # 5. Enter 搜索/进入
        if not _tap_key("return"):
            print("[WARN] Enter 确认搜索失败", file=sys.stderr)
            return False
        time.sleep(KEY_DELAY)

        # 6. Escape 关闭搜索框
        _tap_key("escape")
        time.sleep(KEY_DELAY)

        # 7. 截图验证
        verify_path = sess / "search_verify.png"
        if not _screenshot_window(verify_path):
            print("[WARN] 搜索后截图失败", file=sys.stderr)
            return False

        # 裁剪出聊天区域（去掉左侧面板）
        rect = _window_rect()
        if rect:
            _, _, w, h = rect
            chat_x = LEFT_PANEL_WIDTH
            chat_w = w - LEFT_PANEL_WIDTH
            if chat_w > 0 and h > 0:
                cropped = sess / "search_chat_region.png"
                _crop_image(verify_path, cropped, chat_x, 0, chat_w, h)
                verify_path = cropped

        # 用 Qwen-VL 判断是否是聊天窗口
        ocr = _call_qwen_vl(
            verify_path,
            "这张截图是否显示了一个正在进行的聊天窗口（包含消息气泡或对话内容）？"
            "请只回答「是」或「否」。如果看到的是微信主页面、联系人列表或空页面，回答「否」。",
        )

        if ocr is None:
            # 无法调用 VL，保守假设成功（避免误阻断）
            print("[WARN] 无法调用视觉模型验证，假设搜索成功", file=sys.stderr)
            return True

        is_chat = "是" in ocr and "否" not in ocr
        if not is_chat:
            print(f"[WARN] 搜索联系人 '{name}' 后未检测到聊天窗口（VL: {ocr[:60]}）", file=sys.stderr)

        return is_chat

    # ── 发送消息 ──────────────────────────────────────────────────────

    def send_message(self, text: str) -> bool:
        """在已打开的聊天窗口中发送消息。

        流程:
          1. bring_to_front
          2. pbcopy 写入消息文本
          3. Cmd+V  粘贴到输入框
          4. Enter  发送
          5. 截图验证消息已出现

        Args:
            text: 消息内容。

        Returns:
            True 如果发送成功（或无法验证时乐观返回 True）。
        """
        if not self.bring_to_front():
            return False

        sess = _session_dir()

        # 1. 复制到剪贴板
        if not _pbcopy(text):
            print("[WARN] 复制消息到剪贴板失败", file=sys.stderr)
            return False
        time.sleep(0.2)

        # 2. Cmd+V 粘贴
        if not _cmd_key("v"):
            print("[WARN] Cmd+V 粘贴失败", file=sys.stderr)
            return False
        time.sleep(KEY_DELAY)

        # 3. Enter 发送
        if not _tap_key("return"):
            print("[WARN] Enter 发送失败", file=sys.stderr)
            return False
        time.sleep(KEY_DELAY)

        # 4. 截图验证
        verify_path = sess / "send_verify.png"
        if not _screenshot_window(verify_path):
            return True  # 无法截图，乐观返回成功

        # 裁剪聊天区域
        rect = _window_rect()
        if rect:
            _, _, w, h = rect
            chat_x = LEFT_PANEL_WIDTH
            chat_w = w - LEFT_PANEL_WIDTH
            if chat_w > 0 and h > 0:
                cropped = sess / "send_chat_region.png"
                _crop_image(verify_path, cropped, chat_x, 0, chat_w, h)
                verify_path = cropped

        ocr = _call_qwen_vl(
            verify_path,
            f"聊天窗口中是否包含刚刚发送的消息（或其一部分）？消息内容: \"{text[:80]}\"\n"
            "请只回答「是」或「否」。",
        )

        if ocr is None:
            return True  # 无法调用视觉模型，假设成功
        if "是" in ocr:
            return True

        print(f"[WARN] 消息发送后 VL 验证未通过（VL: {ocr[:60]}）", file=sys.stderr)
        return False

    # ── 读取聊天 ──────────────────────────────────────────────────────

    def read_chat(self) -> str:
        """截取聊天区域并调用 Qwen-VL-Plus 读取文字。

        流程:
          1. bring_to_front
          2. 窗口截图
          3. 裁剪掉左侧 280px
          4. Qwen-VL-Plus 读聊天框文字

        Returns:
            聊天内容文本（多行），空字符串表示失败。
        """
        if not self.bring_to_front():
            return ""

        rect = _window_rect()
        if rect is None:
            print("[WARN] 无法获取窗口位置", file=sys.stderr)
            return ""

        _, _, w, h = rect
        if w <= LEFT_PANEL_WIDTH or h <= 0:
            print("[WARN] 窗口尺寸异常，无法裁剪聊天区域", file=sys.stderr)
            return ""

        sess = _session_dir()
        raw_path = sess / "chat_raw.png"
        if not _screenshot_window(raw_path):
            return ""

        chat_path = sess / "chat_region.png"
        chat_x = LEFT_PANEL_WIDTH
        chat_w = w - LEFT_PANEL_WIDTH
        if not _crop_image(raw_path, chat_path, chat_x, 0, chat_w, h):
            return ""

        # 调用 Qwen-VL-Plus 读取聊天文字
        result = _call_qwen_vl(
            chat_path,
            "请仔细阅读这张聊天截图，逐条提取所有聊天内容。\n"
            "格式要求:\n"
            "- 每条消息一行：「发送者: 消息内容」\n"
            "- 保留时间戳（如果有）\n"
            "- 保持原文语言（中文/英文）\n"
            "- 不要省略内容",
        )

        if result is None:
            return ""
        return result.strip()

    # ── 红点检测 ──────────────────────────────────────────────────────

    def detect_red_dots(self) -> list[int]:
        """检测微信左侧面板的红点（未读消息/提醒）。

        流程:
          1. bring_to_front + 窗口截图
          2. 裁剪左侧 280px 面板
          3. OpenCV HSV 颜色空间识别红色区域
          4. 过滤小面积噪点
          5. 按 y 坐标排序返回

        Returns:
            红点中心的 y 坐标列表（空列表表示无红点或检测失败）。
        """
        if not self.bring_to_front():
            return []

        rect = _window_rect()
        if rect is None:
            return []

        _, _, w, h = rect
        if w <= 0 or h <= 0:
            return []

        sess = _session_dir()
        raw_path = sess / "reddot_raw.png"
        if not _screenshot_window(raw_path):
            return []

        left_path = sess / "left_panel.png"
        if not _crop_image(raw_path, left_path, 0, 0, LEFT_PANEL_WIDTH, h):
            return []

        # ── OpenCV HSV 红点检测 ──
        try:
            img = cv2.imread(str(left_path))
            if img is None:
                print("[WARN] 无法读取左侧面板截图", file=sys.stderr)
                return []

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # 红色在 HSV 中跨越 0° 边界，需要两个范围
            lower_red1 = np.array([0, 70, 50], dtype=np.uint8)
            upper_red1 = np.array([10, 255, 255], dtype=np.uint8)
            lower_red2 = np.array([170, 70, 50], dtype=np.uint8)
            upper_red2 = np.array([180, 255, 255], dtype=np.uint8)

            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            mask = cv2.bitwise_or(mask1, mask2)

            # 形态学去噪
            kernel = np.ones((3, 3), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            y_coords: list[int] = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < 15:  # 过滤微小噪点
                    continue
                _, cy, _, _ = cv2.boundingRect(cnt)
                y_coords.append(cy)

            y_coords.sort()
            return y_coords

        except Exception as e:
            print(f"[WARN] OpenCV 红点检测失败: {e}", file=sys.stderr)
            return []

    # ── 按 y 坐标获取联系人名字 ──────────────────────────────────────

    def get_contact_name_at_y(self, y: int) -> str:
        """根据红点 y 坐标，读取左侧列表中对应行的联系人名字。

        流程:
          1. bring_to_front + 窗口截图
          2. 裁剪左侧面板中 y 附近 ±30px 的行区域
          3. Qwen-VL-Plus OCR 识别该区域的文字

        Args:
            y: 红点在窗口中的垂直坐标（pixel）。

        Returns:
            联系人名字，识别失败返回空字符串。
        """
        if not self.bring_to_front():
            return ""

        rect = _window_rect()
        if rect is None:
            return ""

        _, _, w, h = rect
        if w <= 0 or h <= 0:
            return ""

        sess = _session_dir()
        raw_path = sess / "name_raw.png"
        if not _screenshot_window(raw_path):
            return ""

        # 裁剪左侧面板中 y 附近的一行
        crop_y = max(0, y - ROW_HEIGHT // 2)
        crop_h = ROW_HEIGHT
        if crop_y + crop_h > h:  # 边界保护，防止裁超出窗口
            crop_y = max(0, h - ROW_HEIGHT)
            crop_h = h - crop_y

        row_path = sess / "contact_row.png"
        if not _crop_image(raw_path, row_path, 0, crop_y, LEFT_PANEL_WIDTH, crop_h):
            return ""

        # 调用 Qwen-VL-Plus OCR
        result = _call_qwen_vl(
            row_path,
            "请仔细阅读这张截图，提取其中显示的联系人名字、群聊名称或备注名。"
            "只输出名字本身，不要额外文字。如果没有任何文字，输出空。",
        )

        if result is None:
            return ""
        return result.strip()
