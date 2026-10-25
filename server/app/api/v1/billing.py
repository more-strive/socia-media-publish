"""商业化：套餐 / 订阅 / 订单（mock 支付）/ 发票"""
from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, PageDep
from app.core.exceptions import BizError, NotFoundError
from app.models.billing import Invoice, Order, Plan
from app.models.enums import OrderStatus, UserRole
from app.models.team import Team, User
from app.schemas.billing import InvoiceIn, InvoiceOut, OrderIn, OrderOut, PlanOut, SubscriptionOut
from app.schemas.common import ok
from app.services.billing_service import apply_paid_order, calc_amount, gen_order_no

router = APIRouter(prefix="/billing", tags=["商业化"])


@router.get("/plans", summary="套餐列表")
async def list_plans(db: DbDep):
    rows = (
        await db.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_monthly))
    ).scalars().all()
    return ok([PlanOut.model_validate(r).model_dump(mode="json") for r in rows])


@router.get("/subscription", summary="当前订阅与席位用量")
async def subscription(user: CurrentUser, db: DbDep):
    team = await db.get(Team, user.team_id)
    seats_used = await db.scalar(select(func.count()).select_from(User).where(User.team_id == team.id))
    plan = await db.get(Plan, team.plan_id) if team.plan_id else None
    return ok(
        SubscriptionOut(
            plan=PlanOut.model_validate(plan) if plan else None,
            plan_expire_at=team.plan_expire_at,
            seats_total=team.seats_total,
            seats_used=seats_used,
            credits=team.credits,
        ).model_dump(mode="json")
    )


@router.post("/orders", summary="创建订单（订阅/续费/升级/席位/积分包）")
async def create_order(payload: OrderIn, user: CurrentUser, db: DbDep):
    amount, _ = await calc_amount(db, payload.type.value, payload.plan_id, payload.quantity)
    order = Order(
        team_id=user.team_id,
        order_no=gen_order_no(),
        type=payload.type.value,
        plan_id=payload.plan_id,
        quantity=payload.quantity,
        amount=amount,
    )
    db.add(order)
    await db.commit()
    return ok(OrderOut.model_validate(order).model_dump(mode="json"), "下单成功，请支付")


@router.post("/orders/{order_id}/mock-pay", summary="模拟支付（生产环境对接微信 papay 免密代扣）")
async def mock_pay(order_id: int, user: CurrentUser, db: DbDep):
    order = await db.scalar(select(Order).where(Order.id == order_id, Order.team_id == user.team_id))
    if order is None:
        raise NotFoundError("订单不存在")
    if order.status != OrderStatus.unpaid.value:
        raise BizError(400, "订单状态不可支付")
    await apply_paid_order(db, order)
    await db.commit()
    return ok(OrderOut.model_validate(order).model_dump(mode="json"), "支付成功")


@router.get("/orders", summary="订单列表")
async def list_orders(user: CurrentUser, db: DbDep, page: PageDep):
    conds = [Order.team_id == user.team_id]
    total = await db.scalar(select(func.count()).select_from(Order).where(*conds))
    rows = (
        await db.execute(
            select(Order).where(*conds).order_by(Order.id.desc()).offset(page.offset).limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [OrderOut.model_validate(r).model_dump(mode="json") for r in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


@router.post("/invoices", summary="申请开票（仅已支付订单）")
async def create_invoice(payload: InvoiceIn, user: CurrentUser, db: DbDep):
    if user.role not in (UserRole.owner.value, UserRole.admin.value):
        raise BizError(403, "仅管理员可申请开票")
    order = await db.scalar(select(Order).where(Order.id == payload.order_id, Order.team_id == user.team_id))
    if order is None:
        raise NotFoundError("订单不存在")
    if order.status != OrderStatus.paid.value:
        raise BizError(400, "仅已支付订单可开票")
    exists = await db.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.order_id == order.id)
    )
    if exists:
        raise BizError(409, "该订单已申请过开票")
    invoice = Invoice(team_id=user.team_id, amount=order.amount, **payload.model_dump())
    db.add(invoice)
    await db.commit()
    return ok(InvoiceOut.model_validate(invoice).model_dump(mode="json"))


@router.get("/invoices", summary="发票列表")
async def list_invoices(user: CurrentUser, db: DbDep, page: PageDep):
    conds = [Invoice.team_id == user.team_id]
    total = await db.scalar(select(func.count()).select_from(Invoice).where(*conds))
    rows = (
        await db.execute(
            select(Invoice).where(*conds).order_by(Invoice.id.desc()).offset(page.offset).limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [InvoiceOut.model_validate(r).model_dump(mode="json") for r in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )
