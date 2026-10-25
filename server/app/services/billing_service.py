"""订单支付生效逻辑"""
import random
from datetime import timedelta

from sqlalchemy import func, select

from app.core.exceptions import BizError
from app.models.billing import Order, Plan
from app.models.enums import OrderStatus, OrderType
from app.models.team import Team


def gen_order_no() -> str:
    return f"SN{random.randint(10**11, 10**12 - 1)}"


async def calc_amount(session, order_type: str, plan_id: int | None, quantity: int) -> tuple[float, Plan | None]:
    plan = None
    if order_type in (OrderType.new.value, OrderType.renew.value, OrderType.upgrade.value):
        plan = await session.get(Plan, plan_id)
        if plan is None:
            raise BizError(404, "套餐不存在")
    match order_type:
        case OrderType.new.value | OrderType.renew.value | OrderType.upgrade.value:
            amount = float(plan.price_monthly) * quantity
        case OrderType.seats.value:
            amount = 99.0 * quantity  # 单席位单价
        case OrderType.credits.value:
            amount = 0.1 * quantity  # quantity 为积分包数，每包 1000 积分 100 元
        case _:
            raise BizError(400, "未知订单类型")
    return round(amount, 2), plan


async def apply_paid_order(session, order: Order) -> None:
    """订单支付成功后对团队生效：绑定/续期套餐 / 加席 / 加积分"""
    team = await session.get(Team, order.team_id)
    if team is None:
        raise BizError(404, "团队不存在")

    db_now = (await session.execute(select(func.now()))).scalar()
    base = max(team.plan_expire_at, db_now) if team.plan_expire_at else db_now

    match order.type:
        case OrderType.new.value | OrderType.renew.value:
            plan = await session.get(Plan, order.plan_id)
            team.plan_id = order.plan_id
            team.plan_expire_at = base + timedelta(days=30 * order.quantity)
            team.credits += (plan.credits_monthly if plan else 0) * order.quantity
        case OrderType.upgrade.value:
            team.plan_id = order.plan_id
        case OrderType.seats.value:
            team.seats_total += order.quantity
        case OrderType.credits.value:
            team.credits += order.quantity * 1000
    order.status = OrderStatus.paid.value
    order.paid_at = db_now
