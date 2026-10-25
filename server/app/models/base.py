"""模型公共基类：约束命名规范 + 时间戳"""
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

# 统一命名约定，保证 alembic 迁移可重复生成
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Base.metadata.naming_convention = NAMING_CONVENTION


class TimestampMixin:
    # MySQL 无 INSERT..RETURNING，server_default 列（created_at 等）提交后为未加载状态，
    # 异步下惰性刷新会抛 MissingGreenlet；eager_defaults 让 flush 时主动 SELECT 回填
    __mapper_args__ = {"eager_defaults": True}

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
