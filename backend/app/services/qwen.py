import json
import re
from typing import Any

import httpx

from app.config import settings
from app.prompts.templates import (
    GENERATE_PROMPT_SYSTEM,
    GENERATE_PROMPT_USER,
    SEED_DISHES_SYSTEM,
    SEED_DISHES_USER,
)


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def _chat(system: str, user: str, model: str | None = None) -> str:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY 未配置")

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": model or settings.openai_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def generate_dish_list() -> list[dict[str, str]]:
    raw = await _chat(SEED_DISHES_SYSTEM, SEED_DISHES_USER)
    dishes = _extract_json(raw)
    if not isinstance(dishes, list):
        raise ValueError("千问返回格式错误：期望 JSON 数组")
    return dishes


async def generate_prompt_for_dish(dish_name: str) -> dict[str, str]:
    raw = await _chat(
        GENERATE_PROMPT_SYSTEM,
        GENERATE_PROMPT_USER.format(dish_name=dish_name),
    )
    result = _extract_json(raw)
    if not isinstance(result, dict):
        raise ValueError("千问返回格式错误：期望 JSON 对象")

    content = result.get("content", "").strip()
    negative_prompt = result.get("negative_prompt", "").strip()
    publish_copy = result.get("publish_copy", "").strip()

    if not content or not publish_copy:
        raise ValueError("千问返回缺少 content 或 publish_copy")

    return {
        "content": content,
        "negative_prompt": negative_prompt,
        "publish_copy": publish_copy,
    }
