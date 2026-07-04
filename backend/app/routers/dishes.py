import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db
from app.models import Dish, PromptVersion, Video
from app.schemas import (
    DishCreate,
    DishDetail,
    DishListItem,
    DishUpdate,
    GeneratePromptResult,
    MessageResult,
    PromptVersionOut,
    SeedResult,
    VideoOut,
)
from app.services.oss import transfer_to_oss
from app.services.qwen import generate_dish_list, generate_prompt_for_dish
from app.services.video_cleanup import remove_video
from app.services.volcano import (
    VideoCancelledError,
    cancel_video_task,
    create_video_task,
    wait_for_video,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dishes", tags=["dishes"])


def _touch_dish(db: Session, dish_id: int) -> None:
    db.query(Dish).filter(Dish.id == dish_id).update({Dish.updated_at: func.now()})


def _dish_to_list_item(dish: Dish, prompt_count: int) -> DishListItem:
    return DishListItem(
        id=dish.id,
        name=dish.name,
        category=dish.category,
        region=dish.region,
        publish_copy=dish.publish_copy,
        prompt_count=prompt_count,
        created_at=dish.created_at,
        updated_at=dish.updated_at,
    )


@router.get("", response_model=list[DishListItem])
def list_dishes(db: Session = Depends(get_db)):
    rows = (
        db.query(Dish, func.count(PromptVersion.id).label("prompt_count"))
        .outerjoin(PromptVersion, PromptVersion.dish_id == Dish.id)
        .group_by(Dish.id)
        .order_by(Dish.updated_at.desc())
        .all()
    )
    return [_dish_to_list_item(dish, count) for dish, count in rows]


@router.post("", response_model=DishListItem)
def create_dish(payload: DishCreate, db: Session = Depends(get_db)):
    existing = db.query(Dish).filter(Dish.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="菜品已存在")
    dish = Dish(**payload.model_dump())
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return _dish_to_list_item(dish, 0)


@router.get("/{dish_id}", response_model=DishDetail)
def get_dish(dish_id: int, db: Session = Depends(get_db)):
    dish = (
        db.query(Dish)
        .options(joinedload(Dish.prompt_versions))
        .filter(Dish.id == dish_id)
        .first()
    )
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")

    versions = sorted(dish.prompt_versions, key=lambda p: p.version_no, reverse=True)
    item = _dish_to_list_item(dish, len(versions))
    return DishDetail(
        **item.model_dump(),
        prompt_versions=[PromptVersionOut.model_validate(v) for v in versions],
    )


@router.patch("/{dish_id}", response_model=DishListItem)
def update_dish(dish_id: int, payload: DishUpdate, db: Session = Depends(get_db)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(dish, key, value)
    _touch_dish(db, dish_id)
    db.commit()
    db.refresh(dish)
    count = db.query(PromptVersion).filter(PromptVersion.dish_id == dish_id).count()
    return _dish_to_list_item(dish, count)


@router.delete("/{dish_id}", response_model=MessageResult)
async def delete_dish(dish_id: int, db: Session = Depends(get_db)):
    dish = (
        db.query(Dish)
        .options(joinedload(Dish.prompt_versions).joinedload(PromptVersion.videos))
        .filter(Dish.id == dish_id)
        .first()
    )
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")
    for prompt in dish.prompt_versions:
        for video in prompt.videos:
            await remove_video(video)
    db.delete(dish)
    db.commit()
    return MessageResult(message="已删除")


@router.post("/seed", response_model=SeedResult)
async def seed_dishes(db: Session = Depends(get_db)):
    try:
        dishes_data = await generate_dish_list()
    except Exception as exc:
        logger.exception("seed dishes failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    created = 0
    skipped = 0
    for item in dishes_data:
        name = (item.get("name") or "").strip()
        if not name:
            skipped += 1
            continue
        exists = db.query(Dish).filter(Dish.name == name).first()
        if exists:
            skipped += 1
            continue
        db.add(
            Dish(
                name=name,
                category=item.get("category"),
                region=item.get("region"),
            )
        )
        created += 1

    db.commit()
    return SeedResult(created=created, skipped=skipped, total=len(dishes_data))


@router.post("/{dish_id}/prompts", response_model=GeneratePromptResult)
async def generate_prompt(dish_id: int, db: Session = Depends(get_db)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")

    try:
        result = await generate_prompt_for_dish(dish.name, dish.category, dish.region)
    except Exception as exc:
        logger.exception("generate prompt failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    max_version = (
        db.query(func.max(PromptVersion.version_no))
        .filter(PromptVersion.dish_id == dish_id)
        .scalar()
    ) or 0

    prompt = PromptVersion(
        dish_id=dish_id,
        version_no=max_version + 1,
        content=result["content"],
        negative_prompt=result["negative_prompt"],
    )
    dish.publish_copy = result["publish_copy"]
    _touch_dish(db, dish_id)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)

    return GeneratePromptResult(
        prompt=PromptVersionOut.model_validate(prompt),
        publish_copy=result["publish_copy"],
    )


async def _run_video_generation(video_id: int) -> None:
    def still_exists() -> bool:
        db = SessionLocal()
        try:
            return db.query(Video).filter(Video.id == video_id).first() is not None
        finally:
            db.close()

    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return

        prompt_version = (
            db.query(PromptVersion)
            .filter(PromptVersion.id == video.prompt_version_id)
            .first()
        )
        if not prompt_version:
            video.status = "failed"
            video.error_msg = "提示词不存在"
            db.commit()
            return

        try:
            if not still_exists():
                return

            task_id = await create_video_task(
                prompt_version.content,
                prompt_version.negative_prompt,
            )

            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                await cancel_video_task(task_id)
                return

            video.task_id = task_id
            video.status = "generating"
            db.commit()

            volcano_url = await wait_for_video(task_id, should_continue=still_exists)

            if not still_exists():
                return

            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                return

            oss_url, oss_key = await transfer_to_oss(video.id, volcano_url)
            video.video_url = oss_url
            video.oss_key = oss_key
            video.status = "done"
            video.error_msg = None
            _touch_dish(db, prompt_version.dish_id)
            db.commit()
        except VideoCancelledError:
            logger.info("video_id=%s cancelled (deleted by user)", video_id)
        except Exception as exc:
            if not still_exists():
                return
            logger.exception("video generation failed for video_id=%s", video_id)
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = "failed"
                video.error_msg = str(exc)
                db.commit()
    finally:
        db.close()


@router.post("/prompts/{prompt_id}/videos", response_model=VideoOut)
def create_video(
    prompt_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    prompt = db.query(PromptVersion).filter(PromptVersion.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词不存在")

    active = (
        db.query(Video)
        .filter(
            Video.prompt_version_id == prompt_id,
            Video.status.in_(["pending", "generating"]),
        )
        .first()
    )
    if active:
        raise HTTPException(status_code=400, detail="该提示词已有视频在生成中")

    video = Video(prompt_version_id=prompt_id, status="pending")
    db.add(video)
    _touch_dish(db, prompt.dish_id)
    db.commit()
    db.refresh(video)

    background_tasks.add_task(_run_video_generation, video.id)
    return VideoOut.model_validate(video)
