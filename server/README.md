# 社媒矩阵运营平台 Server

基于 [docs/蚁小二功能分析.md](../docs/蚁小二功能分析.md) 搭建的服务端，技术栈：**Python 3.12+（建议 3.14）+ FastAPI + MySQL + Redis**。

## 功能模块（对应分析文档九大模块）

| 模块 | 路由前缀 | 说明 |
|---|---|---|
| 账户体系 | `/api/v1/auth` | 密码 / 短信验证码登录（mock 验证码）、JWT + refresh token 白名单 |
| 团队协作 | `/api/v1/teams`、`/api/v1/users` | 席位制、邀请链接、角色权限、审核流开关、操作日志 |
| 账号托管 | `/api/v1/accounts`、`/api/v1/proxies` | 多平台账号（抖音/小红书/视频号/公众号/TikTok 等 10 平台）、分组、运营人指派、失效批量检测、重新授权、代理 IP 连通性检测 |
| 一键分发 | `/api/v1/publish` | 1 内容 → 多账号、即时/定时发布（Redis zset 调度）、发布日历、发布前审核流 |
| 内容管理 | `/api/v1/contents` | 视频/图文/文章、内容审核流、AI 文案生成（火山方舟 Ark / mock）、DOCX 批量导入（零依赖解析） |
| 私信评论 | `/api/v1/messages` | 评论/私信统一收件、多级评论嵌套、关键词自动回复、欢迎语、话术库、模拟入站推送 |
| 数据统计 | `/api/v1/stats` | 账号时序数据、作品排行、单日汇总、CSV 导出、飞书/钉钉 webhook 推送 |
| AI 创作 | `/api/v1/ai` | 文案（同步）/ 视频（Seedance，异步轮询）/ 数字人 / 声音克隆，积分计费、失败退款 |
| 商业化 | `/api/v1/billing` | 套餐、订阅/续费/升级/席位/积分包订单、mock 支付（对接微信 papay 的位置已留）、发票申请 |

所有响应统一为 `{"code": 0, "message": "ok", "data": ...}`，`code != 0` 即业务错误。

## 快速开始（Docker，推荐）

```bash
# 仓库根目录
docker compose up -d --build
# 自动建表 + 写入演示数据，访问 http://localhost:8000/docs
```

## 本地开发

```bash
cd server
python -m venv .venv && .venv\Scripts\activate   # Windows；macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env   # macOS/Linux: cp .env.example .env，按需修改连接信息

python -m scripts.init_db      # 建表 + 演示数据
uvicorn app.main:app --reload  # 启动，文档见 /docs
```

演示账号（init_db 写入）：

| 手机号 | 密码 | 角色 |
|---|---|---|
| 13800000001 | demo123456 | owner（王老板） |
| 13800000002 | demo123456 | operator（小运营） |
| 13800000003 | demo123456 | auditor（审核员小张） |

## 数据库迁移

开发环境可直接 `python -m scripts.init_db`（create_all）；生产使用 Alembic：

```bash
alembic revision --autogenerate -m "init tables"
alembic upgrade head
```

## 冒烟测试（无需 MySQL）

用 SQLite 替身引擎跑通全业务链路，仅需本机 Redis：

```bash
python -m scripts.smoke_test
# 覆盖：注册登录/账号/内容审核/一键分发调度/定时取消/日历/AI计费/订单支付/私信自动回复/邀请加入/权限审核/代理检测/话术/统计导出
```

## 目录结构

```
server/
├── app/
│   ├── main.py              # 入口： lifespan / CORS / 异常处理 / /health
│   ├── core/                # 配置、JWT/bcrypt、业务异常
│   ├── db/                  # 异步 SQLAlchemy 引擎、Redis 客户端与 key 约定
│   ├── models/              # 18 张表：团队/账号/内容/发布/消息/统计/AI/计费
│   ├── schemas/             # Pydantic 请求/响应模型
│   ├── api/
│   │   ├── deps.py          # 当前用户、角色门卫、分页参数
│   │   └── v1/              # 11 个路由模块
│   └── services/            # 发布调度器、平台适配器、AI 服务、自动回复、计费生效
├── scripts/init_db.py       # 建表 + 演示数据
├── alembic/                 # 迁移环境（异步）
├── Dockerfile
└── requirements.txt
```

## 关键设计

- **发布调度**：`publish:queue`（Redis zset）存定时任务，后台协程每 3s 轮询到期任务，Redis SETNX 锁防多实例重复发布；服务重启自动恢复未完成任务。
- **平台适配器**：`app/services/platforms.py` 注册制，当前 mock；接真实平台时按 `open_api`（公众号等）/ `rpa`（无开放平台网站）分别实现 adapter，路由与调度零改动。
- **审核流**：团队级开关（`audit_enabled`）。开启后内容需审核通过才能发布；operator 创建的发布任务需 auditor/admin 审核后入队。
- **多租户**：所有业务表带 `team_id`，接口层统一按当前用户 team 过滤；角色 owner/admin/operator/auditor。
- **AI 积分**：任务创建即扣，同步失败立即退，异步失败后台退；无 API Key 时自动走 mock 链路。

## 尚未实现（对应分析文档，按需扩展）

- 微信扫码 / 钉钉登录（`/auth` 预留扩展点）
- 微信 papay 免密代扣（现为 `POST /billing/orders/{id}/mock-pay`）
- 指纹浏览器 / 云窗口（依赖桌面客户端协议，需先定义客户端 WS 协议）
- 浏览器插件回调、OpenClaw 本地伙伴对接
- 分片上传（对象存储选型后实现，`contents.media` 已按 URL 列表设计）
