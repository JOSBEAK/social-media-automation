from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    platform: str
    filename: str
    account_count: int
    created_at: str


class JobCreate(BaseModel):
    batch_id: str = Field(min_length=1)
    action: Literal["like", "comment", "reply", "repost", "retweet"]
    target_url: str = Field(min_length=8, max_length=2048)
    comment_text: Optional[str] = Field(default=None, max_length=1000)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_id: str
    batch_name: str
    platform: str
    action: str
    target_url: str
    params: dict
    status: str
    total: int
    completed: int
    succeeded: int
    failed: int
    error: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class JobDetailResponse(JobResponse):
    results: list[dict]
