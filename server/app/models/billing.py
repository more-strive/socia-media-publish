"""商业化：套餐 / 订单 / 发票 / 操作日志"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin
from app.models.enums import InvoiceStatus, OrderStatus, OrderType


class Plan(TimestampMixin, Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    seats: Mapped[int] = mapped_column(default=3, comment="包含席位数")
    accounts: Mapped[int] = mapped_column(default=20, comment="可托管账号数")
    credits_monthly: Mapped[int] = mapped_column(default=0, comment="每月 AI 积分")
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), comment="月付价格（元）")
    price_yearly: Mapped[Decimal] = mapped_column(Numeric(10, 2), comment="年付价格（元）")
    features: Mapped[list | None] = mapped_column(JSON, comment="功能卖点列表")
    is_active: Mapped[bool] = mapped_column(default=True)


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    order_no: Mapped[str] = mapped_column(String(40), unique=True, comment="业务单号")
    type: Mapped[str] = mapped_column(String(16), comment="new/renew/upgrade/seats/credits")
    plan_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plans.id"))
    quantity: Mapped[int] = mapped_column(default=1, comment="数量（月数/席位数/积分数）")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(16), default=OrderStatus.unpaid.value, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)

    plan: Mapped[Plan | None] = relationship(lazy="joined")


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id"), index=True)
    title: Mapped[str] = mapped_column(String(128), comment="发票抬头")
    tax_no: Mapped[str | None] = mapped_column(String(64), comment="税号")
    type: Mapped[str] = mapped_column(String(16), default="normal", comment="normal/vat 普票/专票")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(16), default=InvoiceStatus.pending.value)
    file_url: Mapped[str | None] = mapped_column(String(512), comment="PDF 下载地址")


class AuditLog(Base):
    """操作日志"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64), comment="操作类型")
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
