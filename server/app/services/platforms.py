"""平台发布适配器

真实实现分三类（对应蚁小二的发布通道）：
- open_api: 微信公众号等开放平台 API
- rpa: 浏览器 RPA 自动化（无开放平台的网站兜底）
- cloud_app: App 云发布

当前提供 mock 适配器；接入真实平台时在此注册新 adapter 即可，路由与调度逻辑不用动。
"""
import hashlib
import time

from app.models.account import SocialAccount
from app.models.content import Content


class PublishResult(dict):
    """{platform_publish_id, publish_url}"""


class BaseAdapter:
    name = "base"

    async def publish(self, account: SocialAccount, content: Content, extras: dict | None = None) -> PublishResult:
        raise NotImplementedError


class MockAdapter(BaseAdapter):
    """模拟发布：立即返回成功，生成伪作品 ID 与链接"""

    name = "mock"

    async def publish(self, account: SocialAccount, content: Content, extras: dict | None = None) -> PublishResult:
        seed = hashlib.md5(f"{account.id}:{content.id}:{time.time_ns()}".encode()).hexdigest()[:16]
        return PublishResult(
            platform_publish_id=f"{account.platform}_{seed}",
            publish_url=f"https://mock.{account.platform}.com/p/{seed}",
        )


# 平台 -> 适配器注册表
_adapters: dict[str, BaseAdapter] = {"mock": MockAdapter()}


def get_adapter(account: SocialAccount) -> BaseAdapter:
    from app.core.config import settings

    if settings.mock_publish:
        return _adapters["mock"]
    # TODO: 按 account.platform / account.channel 路由到真实 open_api / rpa 适配器
    raise LookupError(f"平台 {account.platform} 暂未接入真实发布适配器")
