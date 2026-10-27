"""业务异常与统一响应"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class BizError(Exception):
    """业务异常：code 会透出给前端，message 直接可展示"""

    def __init__(self, code: int = 400, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(BizError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(404, message)


class PermissionDeniedError(BizError):
    def __init__(self, message: str = "无权限执行该操作"):
        super().__init__(403, message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def biz_error_handler(_: Request, exc: BizError):
        return JSONResponse(status_code=200, content={"code": exc.code, "message": exc.message, "data": None})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        msg = first.get("msg", "参数错误")
        return JSONResponse(
            status_code=200,
            content={"code": 422, "message": f"{loc}: {msg}" if loc else msg, "data": None},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, exc: IntegrityError):
        # 区分外键（1451 删除/更新被引用行）与唯一键（1062）冲突，避免误导排查方向
        mysql_code = getattr(getattr(exc, "orig", None), "args", [None])[0]
        msg = "数据被其他记录引用，无法删除或修改" if mysql_code == 1451 else "数据冲突，请检查唯一性字段"
        return JSONResponse(status_code=200, content={"code": 409, "message": msg, "data": None})

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception):
        from app.core.config import settings

        detail = str(exc) if settings.debug else "服务器内部错误"
        return JSONResponse(status_code=200, content={"code": 500, "message": detail, "data": None})
