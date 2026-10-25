"""数据统计：账号日统计 / 作品日统计"""
from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AccountDailyStat(Base):
    __tablename__ = "account_daily_stats"
    __table_args__ = (UniqueConstraint("account_id", "date", name="uq_account_daily_stats_account_id_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("social_accounts.id"), index=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    date: Mapped[date] = mapped_column(Date, comment="统计日期")
    followers: Mapped[int] = mapped_column(default=0, comment="粉丝总量")
    new_followers: Mapped[int] = mapped_column(default=0)
    views: Mapped[int] = mapped_column(default=0)
    likes: Mapped[int] = mapped_column(default=0)
    comments: Mapped[int] = mapped_column(default=0)
    shares: Mapped[int] = mapped_column(default=0)


class ContentDailyStat(Base):
    __tablename__ = "content_daily_stats"
    __table_args__ = (UniqueConstraint("publish_item_id", "date", name="uq_content_daily_stats_item_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    publish_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("publish_items.id"), index=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("social_accounts.id"), index=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    views: Mapped[int] = mapped_column(default=0)
    likes: Mapped[int] = mapped_column(default=0)
    comments: Mapped[int] = mapped_column(default=0)
    shares: Mapped[int] = mapped_column(default=0)
