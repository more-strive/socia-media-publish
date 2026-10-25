from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# 各任务类型基础积分定价
CREDITS_TABLE = {
    "copy": 1,
    "video": 100,
    "digital_human": 200,
    "voice_clone": 50,
}


class AITaskIn(BaseModel):
    task_type: str = Field(pattern=r"^(copy|video|digital_human|voice_clone)$")
    prompt: str = Field(min_length=1, max_length=4000)
    params: dict[str, Any] | None = None


class AITaskOut(BaseModel):
    id: int
    task_type: str
    provider: str
    prompt: str
    params: dict | None = None
    status: str
    result: dict | None = None
    error: str | None = None
    credits_cost: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditsOut(BaseModel):
    credits: int
