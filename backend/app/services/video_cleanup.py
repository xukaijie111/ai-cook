from app.models import Video
from app.services.oss import delete_object
from app.services.volcano import cancel_video_task


async def remove_video(video: Video) -> None:
    """删除视频记录前：尝试取消火山任务并清理 OSS。"""
    if video.task_id and video.status in ("pending", "generating"):
        await cancel_video_task(video.task_id)
    delete_object(video.oss_key)
