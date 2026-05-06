import os
import re
import json
import logging
from typing import Dict, Any, Optional, List

import requests

logger = logging.getLogger(__name__)

BILIBILI_COOKIE = os.getenv("BILIBILI_COOKIE", "")
BILIBILI_SESSDATA = os.getenv("BILIBILI_SESSDATA", "")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}


def parse_bv_number(url: str) -> Optional[str]:
    """
    从B站URL中提取BV号。

    Args:
        url: B站视频URL

    Returns:
        BV号字符串，如 BV1xx411c7mD；解析失败返回 None
    """
    patterns = [
        r"(BV[a-zA-Z0-9]+)",
        r"/video/(BV[a-zA-Z0-9]+)",
        r"bvid=(BV[a-zA-Z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _build_cookie_string() -> str:
    """构建请求用的Cookie字符串"""
    parts = []
    if BILIBILI_COOKIE:
        parts.append(BILIBILI_COOKIE)
    if BILIBILI_SESSDATA:
        if "SESSDATA" not in BILIBILI_COOKIE:
            parts.append("SESSDATA=" + BILIBILI_SESSDATA)
    return "; ".join(parts) if parts else ""


def get_video_info(bvid: str) -> Dict[str, Any]:
    """
    获取B站视频基本信息。

    Args:
        bvid: BV号

    Returns:
        包含 title, description, duration, owner 等字段的字典
    """
    api_url = "https://api.bilibili.com/x/web-interface/view"
    params = {"bvid": bvid}
    headers = dict(_HEADERS)
    cookie = _build_cookie_string()
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        try:
            data = resp.json()
        except json.JSONDecodeError:
            logger.error("B站API返回非JSON数据: %s", resp.text[:200])
            return {"error": "B站API返回数据格式异常"}

        if data.get("code") != 0:
            logger.warning("B站API返回错误: %s", data.get("message", ""))
            return {"error": data.get("message", "API返回错误")}

        info = data.get("data", {})
        return {
            "bvid": bvid,
            "aid": info.get("aid"),
            "title": info.get("title", ""),
            "description": info.get("desc", ""),
            "duration": info.get("duration", 0),
            "owner": info.get("owner", {}).get("name", ""),
            "cid": info.get("cid", 0),
            "pages": info.get("pages", []),
        }
    except requests.RequestException as e:
        logger.error("获取B站视频信息失败: %s", e)
        return {"error": str(e)}


def get_subtitle_urls(bvid: str, cid: int) -> List[Dict[str, str]]:
    """
    获取视频字幕URL列表（CC字幕）。

    Args:
        bvid: BV号
        cid: 视频CID

    Returns:
        字幕信息列表，每项包含 lang, subtitle_url
    """
    api_url = "https://api.bilibili.com/x/player/wbi/v2"
    params = {"bvid": bvid, "cid": cid}
    headers = dict(_HEADERS)
    cookie = _build_cookie_string()
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            logger.warning("获取字幕URL失败: %s", data.get("message", ""))
            return []

        subtitle_info = data.get("data", {}).get("subtitle", {})
        subtitles = subtitle_info.get("subtitles", [])

        result = []
        for sub in subtitles:
            sub_url = sub.get("subtitle_url", "")
            if sub_url and not sub_url.startswith("http"):
                sub_url = "https:" + sub_url
            result.append({
                "lang": sub.get("lan_doc", "中文（自动生成）"),
                "lang_code": sub.get("lan", ""),
                "subtitle_url": sub_url,
            })

        return result
    except requests.RequestException as e:
        logger.error("获取字幕URL失败: %s", e)
        return []


def fetch_subtitle_text(subtitle_url: str) -> str:
    """
    下载并解析字幕JSON，返回纯文本。

    Args:
        subtitle_url: 字幕JSON的URL

    Returns:
        字幕纯文本，每行格式: [时间戳] 字幕内容
    """
    headers = dict(_HEADERS)
    cookie = _build_cookie_string()
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = requests.get(subtitle_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        body = data.get("body", [])
        if not body:
            logger.warning("字幕JSON的body为空")
            return ""

        lines = []
        for entry in body:
            start_ms = entry.get("from", 0)
            minutes = int(start_ms) // 60
            seconds = int(start_ms) % 60
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            content = entry.get("content", "").strip()
            if content:
                lines.append(f"{timestamp} {content}")

        return "\n".join(lines)
    except json.JSONDecodeError as json_err:
        logger.error("字幕JSON解析失败: %s, url=%s", json_err, subtitle_url)
        return ""
    except requests.RequestException as e:
        logger.error("下载字幕失败: %s", e)
        return ""
    except Exception as e:
        logger.error("解析字幕时意外错误: %s", e)
        return ""


def get_video_full_text(url: str) -> Dict[str, Any]:
    """
    完整流程：从URL提取BV号 → 获取视频信息 → 获取字幕 → 返回结构化数据。

    Args:
        url: B站视频URL

    Returns:
        包含 video_info, subtitle_text, full_text 的字典
    """
    bvid = parse_bv_number(url)
    if not bvid:
        return {"error": "无法解析BV号，请检查URL格式"}

    video_info = get_video_info(bvid)
    if "error" in video_info:
        return video_info

    cid = video_info.get("cid", 0)
    if not cid and video_info.get("pages"):
        cid = video_info["pages"][0].get("cid", 0)

    if not cid:
        return {"error": "无法获取视频CID，可能需要登录Cookie"}

    subtitle_urls = get_subtitle_urls(bvid, cid)

    subtitle_text = ""
    subtitle_lang = ""
    if subtitle_urls:
        first_sub = subtitle_urls[0]
        subtitle_lang = first_sub.get("lang", "")
        subtitle_text = fetch_subtitle_text(first_sub["subtitle_url"])

    if not subtitle_text:
        desc = video_info.get("description", "")
        title = video_info.get("title", "")
        fallback_text = f"视频标题：{title}\n\n视频简介：{desc}"
        if not desc:
            return {
                "error": "该视频没有CC字幕，且简介为空。请选择有字幕的视频，或在.env中配置BILIBILI_COOKIE以获取更多内容。",
                "video_info": video_info,
            }
        return {
            "video_info": video_info,
            "subtitle_text": "",
            "subtitle_lang": "",
            "full_text": fallback_text,
            "source": "description",
        }

    return {
        "video_info": video_info,
        "subtitle_text": subtitle_text,
        "subtitle_lang": subtitle_lang,
        "full_text": subtitle_text,
        "source": "subtitle",
    }


def mock_bilibili_import(video_title: str = "") -> Dict[str, Any]:
    """模拟B站导入结果（降级模式，根据标题动态生成）"""
    main_topic = video_title if video_title else "知识点"
    return {
        "video_info": {
            "bvid": "BV1demo0000",
            "title": video_title or "学习视频",
            "description": f"本视频系统讲解{main_topic}的基础概念",
            "duration": 1800,
            "owner": "学习频道",
        },
        "subtitle_text": (
            f"[00:00] 大家好，今天我们来聊{main_topic}的基础\n"
            f"[02:30] 首先什么是{main_topic}？它是该领域的重要概念\n"
            f"[05:00] {main_topic}的核心原理和基本要素\n"
            f"[08:00] {main_topic}的典型应用场景\n"
            f"[12:00] {main_topic}的进阶内容和扩展\n"
            f"[15:00] 常见问题和注意事项\n"
            f"[18:00] 总结和回顾\n"
        ),
        "full_text": (
            f"[00:00] 大家好，今天我们来聊{main_topic}的基础\n"
            f"[02:30] 首先什么是{main_topic}？它是该领域的重要概念\n"
            f"[05:00] {main_topic}的核心原理和基本要素\n"
            f"[08:00] {main_topic}的典型应用场景\n"
            f"[12:00] {main_topic}的进阶内容和扩展\n"
            f"[15:00] 常见问题和注意事项\n"
            f"[18:00] 总结和回顾\n"
        ),
        "source": "subtitle",
    }
