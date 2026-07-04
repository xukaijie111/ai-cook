from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DishBase(BaseModel):
    name: str
    category: str | None = None
    region: str | None = None


class DishCreate(DishBase):
    pass


class DishUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    region: str | None = None
    publish_copy: str | None = None


class DishListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str | None
    region: str | None
    publish_copy: str | None
    prompt_count: int = 0
    created_at: datetime
    updated_at: datetime


class PromptVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dish_id: int
    version_no: int
    content: str
    negative_prompt: str | None
    created_at: datetime


class PromptUpdate(BaseModel):
    content: str | None = None
    negative_prompt: str | None = None


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt_version_id: int
    video_url: str | None
    status: str
    error_msg: str | None
    task_id: str | None
    created_at: datetime


class DishDetail(DishListItem):
    prompt_versions: list[PromptVersionOut] = []


class SeedResult(BaseModel):
    created: int
    skipped: int
    total: int


class GeneratePromptResult(BaseModel):
    prompt: PromptVersionOut
    publish_copy: str


class MessageResult(BaseModel):
    message: str
