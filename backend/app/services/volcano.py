import asyncio
import logging
import os
from collections.abc import Callable

import httpx
from dotenv import load_dotenv

from app.config import ENV_FILE, settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = 10
MAX_POLL_ATTEMPTS = 60

# Seedance 提示词过长会失败，保留核心描述
MAX_PROMPT_CHARS = 2000


def _reload_env() -> None:
    """后台任务可能在 .env 更新前启动，每次调用前重新加载。"""
    load_dotenv(ENV_FILE, override=True)


def _cfg(name: str, fallback: str = "") -> str:
    return os.getenv(name, fallback)


class VolcanoAPIError(Exception):
    pass


class VideoCancelledError(Exception):
    pass


def _parse_api_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        err = data.get("error") or data
        if isinstance(err, dict):
            code = err.get("code", "")
            msg = err.get("message", "")
            if code and msg:
                return f"{code}: {msg}"
            return msg or str(data)
        return str(data)
    except Exception:
        return resp.text[:500] or f"HTTP {resp.status_code}"


def _build_video_prompt(prompt: str, negative_prompt: str | None) -> str:
    text = prompt.strip()
    if negative_prompt:
        text = f"{text}\n\n反向提示词\n{negative_prompt.strip()}"
    if len(text) > MAX_PROMPT_CHARS:
        text = text[:MAX_PROMPT_CHARS] + "…"
    return text


async def create_video_task(prompt: str, negative_prompt: str | None = None) -> str:
    _reload_env()
    ark_api_key = _cfg("ARK_API_KEY", settings.ark_api_key)
    video_model = _cfg("VIDEO_MODEL", settings.video_model)
    ark_base_url = _cfg("ARK_BASE_URL", settings.ark_base_url).rstrip("/")
    video_resolution = _cfg("VIDEO_RESOLUTION", settings.video_resolution)
    video_ratio = _cfg("VIDEO_RATIO", settings.video_ratio)
    video_duration = int(_cfg("VIDEO_DURATION", str(settings.video_duration)))

    if not ark_api_key:
        raise ValueError("ARK_API_KEY 未配置")
    if not video_model:
        raise ValueError("VIDEO_MODEL 未配置，请在 .env 填入视频接入点 ep-xxx 并重启服务")

    body = {
        "model": video_model,
        "content": [
            {
                "type": "text",
                "text": _build_video_prompt(prompt, negative_prompt),
            }
        ],
        "resolution": video_resolution,
        "ratio": video_ratio,
        "duration": video_duration,
        "watermark": False,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{ark_base_url}/contents/generations/tasks",
            headers={
                "Authorization": f"Bearer {ark_api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code >= 400:
            detail = _parse_api_error(resp)
            logger.error("Volcano create task failed: %s", detail)
            if "does not support content generation" in detail or "seedream" in detail.lower():
                raise VolcanoAPIError(
                    "VIDEO_MODEL 接入点不是视频模型（当前是 Seedream 文生图）。"
                    "请在火山方舟控制台创建 Seedance/即梦「视频生成」接入点，"
                    "将 ep-xxx 填入 .env 的 VIDEO_MODEL。"
                    f" 详情: {detail}"
                )
            raise VolcanoAPIError(f"火山视频 API 错误: {detail}")
        data = resp.json()
        task_id = data.get("id") or data.get("task_id")
        if not task_id:
            raise ValueError(f"火山 API 未返回 task_id: {data}")
        return task_id


async def cancel_video_task(task_id: str) -> None:
    """取消排队任务或删除已结束任务。running 状态可能无法取消，见火山文档。"""
    _reload_env()
    ark_api_key = _cfg("ARK_API_KEY", settings.ark_api_key)
    ark_base_url = _cfg("ARK_BASE_URL", settings.ark_base_url).rstrip("/")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(
            f"{ark_base_url}/contents/generations/tasks/{task_id}",
            headers={"Authorization": f"Bearer {ark_api_key}"},
        )
        if resp.status_code >= 400:
            logger.warning(
                "取消火山任务失败 task_id=%s: %s",
                task_id,
                _parse_api_error(resp),
            )


async def get_video_task(task_id: str) -> dict:
    _reload_env()
    ark_api_key = _cfg("ARK_API_KEY", settings.ark_api_key)
    ark_base_url = _cfg("ARK_BASE_URL", settings.ark_base_url).rstrip("/")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{ark_base_url}/contents/generations/tasks/{task_id}",
            headers={"Authorization": f"Bearer {ark_api_key}"},
        )
        if resp.status_code >= 400:
            raise VolcanoAPIError(f"查询视频任务失败: {_parse_api_error(resp)}")
        return resp.json()


def _extract_video_url(data: dict) -> str | None:
    content = data.get("content")
    if isinstance(content, dict):
        url = content.get("video_url")
        if url:
            return url
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                url = item.get("video_url") or item.get("url")
                if url:
                    return url
    output = data.get("output") or data.get("result")
    if isinstance(output, dict):
        return output.get("video_url") or output.get("url")
    return None


async def wait_for_video(
    task_id: str,
    should_continue: Callable[[], bool] | None = None,
) -> str:
    for _ in range(MAX_POLL_ATTEMPTS):
        if should_continue and not should_continue():
            raise VideoCancelledError("任务已删除，停止等待")

        data = await get_video_task(task_id)
        status = (data.get("status") or "").lower()

        if status in ("succeeded", "success", "completed"):
            url = _extract_video_url(data)
            if url:
                return url
            raise ValueError(f"任务成功但未找到 video_url: {data}")

        if status in ("failed", "error"):
            err = data.get("error") or data.get("message") or str(data)
            raise ValueError(f"视频生成失败: {err}")

        if status == "cancelled":
            raise VideoCancelledError("火山任务已取消")

        await asyncio.sleep(POLL_INTERVAL)

    raise TimeoutError(f"视频生成超时，task_id={task_id}")
