"""全局枚举（以字符串存库，便于扩展平台）"""
from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


# ---- 平台 ----
class Platform(StrEnum):
    douyin = "douyin"            # 抖音
    shipinhao = "shipinhao"      # 视频号
    xhs = "xhs"                  # 小红书
    kuaishou = "kuaishou"        # 快手
    bilibili = "bilibili"        # B 站
    weibo = "weibo"              # 微博
    wechat_gzh = "wechat_gzh"    # 微信公众号（开放平台 API）
    toutiao = "toutiao"          # 今日头条
    tiktok = "tiktok"            # 海外
    youtube = "youtube"          # 海外


class PublishChannel(StrEnum):
    """发布通道：开放平台 API / 浏览器 RPA / App 云发布"""
    open_api = "open_api"
    rpa = "rpa"
    cloud_app = "cloud_app"


# ---- 团队 / 用户 ----
class UserRole(StrEnum):
    owner = "owner"              # 创建者
    admin = "admin"              # 管理员
    operator = "operator"        # 运营
    auditor = "auditor"          # 审核员


class UserStatus(StrEnum):
    active = "active"
    disabled = "disabled"


# ---- 账号 ----
class AuthStatus(StrEnum):
    valid = "valid"              # 授权有效
    expired = "expired"          # 已失效（可重新授权）
    invalid = "invalid"          # 异常（需重新登录/检查）


class ProxyStatus(StrEnum):
    unknown = "unknown"
    ok = "ok"
    broken = "broken"


# ---- 内容 / 发布 ----
class ContentType(StrEnum):
    video = "video"
    article = "article"
    images = "images"


class ContentStatus(StrEnum):
    draft = "draft"
    reviewing = "reviewing"
    approved = "approved"
    rejected = "rejected"


class PublishMode(StrEnum):
    immediate = "immediate"
    scheduled = "scheduled"


class PublishTaskStatus(StrEnum):
    reviewing = "reviewing"      # 待审核
    scheduled = "scheduled"      # 定时待执行
    queued = "queued"            # 已入队执行中
    publishing = "publishing"
    published = "published"      # 全部成功
    partial = "partial"          # 部分成功
    failed = "failed"            # 全部失败
    canceled = "canceled"


class PublishItemStatus(StrEnum):
    pending = "pending"
    publishing = "publishing"
    dispatched = "dispatched"    # RPA：已派发给客户端执行
    success = "success"
    failed = "failed"


# ---- 私信评论 ----
class MessageType(StrEnum):
    comment = "comment"
    dm = "dm"


class MessageDirection(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class ReplyRuleType(StrEnum):
    keyword = "keyword"          # 关键词自动回复
    welcome = "welcome"          # 欢迎语 / 关注回复
    follow = "follow"


# ---- AI 创作 ----
class AITaskType(StrEnum):
    copy = "copy"                  # AI 文案
    video = "video"                # Seedance 视频生成
    digital_human = "digital_human"  # 数字人
    voice_clone = "voice_clone"    # 声音克隆


class AITaskStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


# ---- 商业化 ----
class OrderType(StrEnum):
    new = "new"                # 新购
    renew = "renew"            # 续费
    upgrade = "upgrade"        # 升级
    seats = "seats"            # 加席位
    credits = "credits"        # 流量/积分包


class OrderStatus(StrEnum):
    unpaid = "unpaid"
    paid = "paid"
    canceled = "canceled"
    refunded = "refunded"


class InvoiceStatus(StrEnum):
    pending = "pending"
    issued = "issued"
