"""AI 能力封装：方舟 Ark（文案）/ Seedance（视频）

无 API Key 时走 mock 实现，保证链路可跑通；配置 Key 后自动切换真实调用。
"""
import asyncio
import uuid
from typing import Any

from app.core.config import settings

_PLATFORM_STYLE = {
    "xhs": "小红书风格：标题带 emoji、分点种草、口语化、结尾带话题标签",
    "douyin": "抖音风格：强钩子开头、短句、节奏快、结尾引导关注",
    "wechat_gzh": "公众号风格：结构化长文、小标题分段、正式书面语",
}


async def generate_copy(topic: str, platform: str = "xhs", tone: str | None = None) -> str:
    """AI 文案生成（火山方舟 Ark）"""
    if not settings.ark_api_key:
        # mock：返回可直接使用的模板文案
        style = _PLATFORM_STYLE.get(platform, _PLATFORM_STYLE["xhs"])
        tone_part = f"，语气{tone}" if tone else ""
        await asyncio.sleep(0.2)
        return (
            f"【{topic}】{style}的种草文案{tone_part}：\n\n"
            f"1. 开头钩子：{topic}，90% 的人都做错了！\n"
            f"2. 核心干货：三步搞定 {topic}，亲测有效（附避坑清单）\n"
            f"3. 结尾互动：你还有哪些 {topic} 的疑问？评论区告诉我～\n\n"
            f"# {topic} # 干货分享"
        )

    import httpx

    prompt = f"请为主题「{topic}」写一篇{style}的社媒文案{f'，语气{tone}' if tone else ''}，直接输出正文。"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            headers={"Authorization": f"Bearer {settings.ark_api_key}"},
            json={"model": settings.ark_model, "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def generate_video(prompt: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Seedance 视频生成：返回 {video_url}。无 Key 时延迟后返回 mock URL。"""
    if not settings.seedance_api_key:
        delay = min(settings.ai_mock_delay_seconds, 30)
        await asyncio.sleep(delay)
        return {"video_url": f"https://mock-cdn.example.com/seedance/{uuid.uuid4().hex}.mp4"}

    # TODO: 对接 Seedance 任务创建 + 轮询取回
    raise NotImplementedError("Seedance 真实接入待实现")


async def mock_run_with_delay(delay: float | None = None) -> None:
    """数字人 / 声音克隆等长任务的模拟耗时"""
    await asyncio.sleep(delay if delay is not None else min(settings.ai_mock_delay_seconds, 30))
