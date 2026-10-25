from datetime import date, datetime

from pydantic import BaseModel


class StatSeriesPoint(BaseModel):
    date: date
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    new_followers: int = 0


class AccountStatOut(BaseModel):
    account_id: int
    nickname: str
    platform: str
    followers: int = 0
    series: list[StatSeriesPoint] = []


class ContentStatRow(BaseModel):
    content_id: int
    title: str
    account_id: int
    account_nickname: str | None = None
    platform: str | None = None
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    publish_url: str | None = None
    published_at: datetime | None = None


class SummaryOut(BaseModel):
    date: date
    account_count: int = 0
    total_followers: int = 0
    new_followers: int = 0
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    published_count: int = 0
