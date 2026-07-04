import logging
import time

import httpx
import oss2

from app.config import settings

logger = logging.getLogger(__name__)


def _bucket() -> oss2.Bucket:
    if not all(
        [
            settings.oss_access_key_id,
            settings.oss_access_key_secret,
            settings.oss_endpoint,
            settings.oss_bucket,
        ]
    ):
        raise ValueError("OSS 配置不完整，请检查 .env")
    auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
    return oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket)


def build_video_key(video_id: int) -> str:
    prefix = settings.oss_video_prefix.rstrip("/")
    return f"{prefix}/video_{video_id}_{int(time.time())}.mp4"


def public_url(key: str) -> str:
    return f"{settings.oss_public_base_url.rstrip('/')}/{key}"


def upload_video_bytes(data: bytes, key: str) -> str:
    bucket = _bucket()
    headers = oss2.CaseInsensitiveDict()
    headers["Content-Type"] = "video/mp4"
    headers["x-oss-object-acl"] = oss2.OBJECT_ACL_PUBLIC_READ
    bucket.put_object(key, data, headers=headers)
    return public_url(key)


def set_public_read(key: str) -> None:
    """将已有对象设为公共读（修复历史上传）。"""
    bucket = _bucket()
    bucket.put_object_acl(key, oss2.OBJECT_ACL_PUBLIC_READ)


async def download_bytes(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def transfer_to_oss(video_id: int, source_url: str) -> tuple[str, str]:
    data = await download_bytes(source_url)
    key = build_video_key(video_id)
    url = upload_video_bytes(data, key)
    return url, key


def delete_object(key: str | None) -> None:
    if not key:
        return
    try:
        _bucket().delete_object(key)
    except Exception:
        logger.exception("OSS 删除失败: %s", key)
