"""内容管理：素材/图文/文章 CRUD、审核流、AI 文案生成、DOCX 导入、素材上传（本地存储）"""
import re
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile
from sqlalchemy import delete, func, select

from app.api.deps import CurrentUser, DbDep, PageDep
from app.core.config import settings
from app.core.exceptions import BizError, NotFoundError
from app.models.content import Content, PublishItem, PublishTask
from app.models.enums import ContentStatus, UserRole
from app.models.stats import ContentDailyStat
from app.schemas.common import ok
from app.schemas.content import AIGenerateIn, ContentIn, ContentOut, ContentUpdateIn, ReviewIn
from app.services import ai_service

router = APIRouter(prefix="/contents", tags=["内容管理"])

_TAG_RE = re.compile(r"<[^>]+>")

# 素材上传：本地磁盘暂存（对象存储选型前的过渡方案），经 /api/v1/files 静态访问
_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
_VIDEO_MAX_BYTES = 500 * 1024 * 1024
_IMAGE_MAX_BYTES = 20 * 1024 * 1024
_CHUNK = 1024 * 1024


@router.post("/upload", summary="上传素材（视频/图片，流式落盘本地 uploads）")
async def upload_media(user: CurrentUser, file: UploadFile = File(description="视频或图片文件")):
    ext = Path(file.filename or "").suffix.lower()
    if ext in _VIDEO_EXTS:
        limit = _VIDEO_MAX_BYTES
    elif ext in _IMAGE_EXTS:
        limit = _IMAGE_MAX_BYTES
    else:
        raise BizError(400, f"不支持的素材类型 {ext or '（无后缀）'}：仅支持常见视频/图片格式")
    rel = Path("content") / datetime.now().strftime("%Y%m") / f"{uuid4().hex}{ext}"
    path = Path(settings.upload_dir) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with path.open("wb") as out:
        while chunk := await file.read(_CHUNK):
            size += len(chunk)
            if size > limit:
                out.close()
                path.unlink(missing_ok=True)
                raise BizError(400, f"文件超过大小限制 {limit // 1024 // 1024}MB")
            out.write(chunk)
    return ok({"url": f"{settings.api_v1_prefix}/files/{rel.as_posix()}", "size": size})


def _extract_docx_text(data: bytes) -> str:
    """从 DOCX 提取纯文本（word/document.xml 去标签）——零依赖实现"""
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)
    return _TAG_RE.sub("", xml).strip()


@router.get("", summary="内容列表")
async def list_contents(
    user: CurrentUser,
    db: DbDep,
    page: PageDep,
    type_: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
):
    conds = [Content.team_id == user.team_id]
    if type_:
        conds.append(Content.type == type_)
    if status:
        conds.append(Content.status == status)
    if keyword:
        conds.append(Content.title.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(Content).where(*conds))
    rows = (
        await db.execute(
            select(Content).where(*conds).order_by(Content.id.desc()).offset(page.offset).limit(page.page_size)
        )
    ).scalars().all()
    return ok(
        {
            "items": [ContentOut.model_validate(r).model_dump(mode="json") for r in rows],
            "total": total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


@router.post("", summary="新建内容（视频/图文/文章）")
async def create_content(payload: ContentIn, user: CurrentUser, db: DbDep):
    content = Content(team_id=user.team_id, creator_id=user.id, **payload.model_dump())
    db.add(content)
    await db.commit()
    return ok(ContentOut.model_validate(content).model_dump(mode="json"))


@router.get("/{content_id}", summary="内容详情")
async def get_content(content_id: int, user: CurrentUser, db: DbDep):
    content = await db.scalar(
        select(Content).where(Content.id == content_id, Content.team_id == user.team_id)
    )
    if content is None:
        raise NotFoundError("内容不存在")
    return ok(ContentOut.model_validate(content).model_dump(mode="json"))


@router.put("/{content_id}", summary="编辑内容（仅草稿/驳回可编辑）")
async def update_content(content_id: int, payload: ContentUpdateIn, user: CurrentUser, db: DbDep):
    content = await db.scalar(
        select(Content).where(Content.id == content_id, Content.team_id == user.team_id)
    )
    if content is None:
        raise NotFoundError("内容不存在")
    if content.status not in (ContentStatus.draft.value, ContentStatus.rejected.value):
        raise BizError(400, "当前状态不可编辑")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(content, k, v)
    await db.commit()
    return ok(ContentOut.model_validate(content).model_dump(mode="json"))


@router.delete("/{content_id}", summary="删除内容")
async def delete_content(content_id: int, user: CurrentUser, db: DbDep):
    content = await db.scalar(
        select(Content).where(Content.id == content_id, Content.team_id == user.team_id)
    )
    if content is None:
        raise NotFoundError("内容不存在")
    # 内容被发布任务引用（publish_tasks.content_id 外键）：连同其任务与条目一并清理
    task_ids = (
        (await db.execute(select(PublishTask.id).where(PublishTask.content_id == content_id))).scalars().all()
    )
    if task_ids:
        item_ids = (
            (await db.execute(select(PublishItem.id).where(PublishItem.task_id.in_(task_ids)))).scalars().all()
        )
        if item_ids:
            await db.execute(delete(ContentDailyStat).where(ContentDailyStat.publish_item_id.in_(item_ids)))
            await db.execute(delete(PublishItem).where(PublishItem.id.in_(item_ids)))
        await db.execute(delete(PublishTask).where(PublishTask.id.in_(task_ids)))
    await db.delete(content)
    await db.commit()
    return ok(message="已删除")


@router.post("/{content_id}/submit", summary="提交审核")
async def submit_content(content_id: int, user: CurrentUser, db: DbDep):
    content = await db.scalar(
        select(Content).where(Content.id == content_id, Content.team_id == user.team_id)
    )
    if content is None:
        raise NotFoundError("内容不存在")
    if content.status not in (ContentStatus.draft.value, ContentStatus.rejected.value):
        raise BizError(400, "当前状态不可提交")
    content.status = ContentStatus.reviewing.value
    await db.commit()
    return ok(message="已提交审核")


@router.post("/{content_id}/review", summary="内容审核（通过/驳回）")
async def review_content(content_id: int, payload: ReviewIn, user: CurrentUser, db: DbDep):
    if user.role not in (UserRole.owner.value, UserRole.admin.value, UserRole.auditor.value):
        raise BizError(403, "仅审核员/管理员可审核")
    content = await db.scalar(
        select(Content).where(Content.id == content_id, Content.team_id == user.team_id)
    )
    if content is None:
        raise NotFoundError("内容不存在")
    if content.status != ContentStatus.reviewing.value:
        raise BizError(400, "内容不在审核中")
    content.status = ContentStatus.approved.value if payload.approve else ContentStatus.rejected.value
    content.review_note = payload.note
    await db.commit()
    return ok(message="审核完成")


@router.post("/ai-generate", summary="AI 文案生成（火山方舟 Ark / mock）")
async def ai_generate(payload: AIGenerateIn, user: CurrentUser, db: DbDep):
    text = await ai_service.generate_copy(payload.topic, payload.platform, payload.tone)
    return ok({"content": text, "topic": payload.topic, "platform": payload.platform})


@router.post("/import-docx", summary="DOCX 批量导入为文章草稿")
async def import_docx(
    user: CurrentUser,
    db: DbDep,
    files: list[UploadFile] = File(description="DOCX 文件列表，文件名作为标题"),
):
    created = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".docx"):
            continue
        data = await f.read()
        try:
            text = _extract_docx_text(data)
        except (zipfile.BadZipFile, KeyError):
            raise BizError(400, f"{f.filename} 不是有效的 DOCX 文件")
        title = f.filename.rsplit(".", 1)[0]
        content = Content(
            team_id=user.team_id,
            creator_id=user.id,
            type="article",
            title=title,
            body=text,
            status=ContentStatus.draft.value,
        )
        db.add(content)
        created.append(title)
    await db.commit()
    return ok({"imported": len(created), "titles": created})
