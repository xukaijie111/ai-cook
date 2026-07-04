from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import PromptVersion, Video
from app.schemas import MessageResult, PromptVersionOut, VideoOut
from app.services.video_cleanup import remove_video

router = APIRouter(prefix="/api", tags=["prompts", "videos"])


@router.get("/prompts/{prompt_id}", response_model=PromptVersionOut)
def get_prompt(prompt_id: int, db: Session = Depends(get_db)):
    prompt = db.query(PromptVersion).filter(PromptVersion.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词不存在")
    return PromptVersionOut.model_validate(prompt)


@router.delete("/prompts/{prompt_id}", response_model=MessageResult)
async def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    prompt = (
        db.query(PromptVersion)
        .options(joinedload(PromptVersion.videos))
        .filter(PromptVersion.id == prompt_id)
        .first()
    )
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词不存在")
    for video in prompt.videos:
        await remove_video(video)
    db.delete(prompt)
    db.commit()
    return MessageResult(message="已删除提示词及关联视频")


@router.get("/prompts/{prompt_id}/videos", response_model=list[VideoOut])
def list_videos_for_prompt(prompt_id: int, db: Session = Depends(get_db)):
    prompt = db.query(PromptVersion).filter(PromptVersion.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词不存在")

    videos = (
        db.query(Video)
        .filter(Video.prompt_version_id == prompt_id)
        .order_by(Video.id.desc())
        .all()
    )
    return [VideoOut.model_validate(v) for v in videos]


@router.get("/videos/{video_id}", response_model=VideoOut)
def get_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return VideoOut.model_validate(video)


@router.delete("/videos/{video_id}", response_model=MessageResult)
async def delete_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    await remove_video(video)
    db.delete(video)
    db.commit()
    return MessageResult(message="已删除视频")
