"""AI 创作任务（文案 / 视频 / 数字人 / 声音克隆，积分计费）"""
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin
from app.models.enums import AITaskStatus


class AITask(TimestampMixin, Base):
    __tablename__ = "ai_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    task_type: Mapped[str] = mapped_column(String(32), comment="copy/video/digital_human/voice_clone")
    provider: Mapped[str] = mapped_column(String(32), default="mock", comment="ark/seedance/mock")
    prompt: Mapped[str] = mapped_column(Text, comment="输入提示词/主题")
    params: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default=AITaskStatus.pending.value, index=True)
    result: Mapped[dict | None] = mapped_column(JSON, comment="生成结果（文本/视频 URL 等）")
    error: Mapped[str | None] = mapped_column(String(255))
    credits_cost: Mapped[int] = mapped_column(Integer, default=0, comment="消耗积分")
