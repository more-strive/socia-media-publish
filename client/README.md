# 社媒矩阵运营平台 Client（Electron 桌面端）

技术栈：**Electron 45 + Vue 3.5 + TypeScript + Element Plus + UnoCSS + Vite 6 + Axios（+ ECharts）**，包管理器 **pnpm**，对接 [server](../server/) 的 59 个接口。

## 快速开始

包管理器使用 **pnpm**（≥10，需 pnpm-workspace.yaml 中的 `allowBuilds` 白名单允许 Electron 安装脚本）。

```bash
pnpm install         # 国内网络若 Electron 二进制下载失败，见下方"镜像说明"
pnpm dev             # 同时启动 vite(5173) 与 Electron 窗口（需先启动 server）
```

先启动 server（默认 127.0.0.1:8000）。**前期免登录**：客户端启动时用内置演示账号自动登录，直接进入工作台（账号在 `.env.development` 的 `VITE_DEMO_ACCOUNT/VITE_DEMO_PASSWORD` 配置，默认 `13800000001 / demo123456`）；仅当自动登录失败（如 server 未启动）才回退到登录页。

```bash
pnpm build           # 产出 dist/（渲染层）+ dist-electron/（主进程）
pnpm dist            # electron-builder 打安装包（release/）
pnpm typecheck       # vue-tsc 类型检查
```

### 纯浏览器开发（不启动 Electron）

```bash
WEB_ONLY=1 pnpm vite   # 浏览器打开 http://127.0.0.1:5173，API 由 vite 代理到 server
```

### 镜像说明（Electron 二进制下载失败时）

```bash
ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ node node_modules/electron/install.js
```

> pnpm 11 注意：安装脚本白名单在 [pnpm-workspace.yaml](pnpm-workspace.yaml) 的 `allowBuilds`（package.json 里的 `pnpm` 字段已废弃）。
>
> 若终端设置了 `ELECTRON_RUN_AS_NODE=1`（某些内嵌终端会有），Electron 会以纯 Node 模式启动导致报错 `Cannot read properties of undefined (reading 'on')`，去掉该变量即可。

## 页面与 server 模块对应

| 菜单 | 路由 | 功能 |
|---|---|---|
| 工作台 | /dashboard | 今日/昨日汇总卡片、最近任务、快捷入口 |
| 账号管理 | /accounts | 账号列表（筛选/分组/批量检测/重新授权）、代理 IP 管理 |
| 内容中心 | /contents | 视频/图文/文章管理、提交审核、AI 文案生成、DOCX 导入 |
| 一键分发 | /publish | 任务列表（自动轮询执行中）、待审核、发布日历、创建任务（多账号/定时/原创/合集） |
| 私信评论 | /messages | 统一收件箱、回复（话术库快捷插入）、自动回复规则、话术库、模拟入站 |
| 数据统计 | /stats | ECharts 趋势图（粉丝/播放/点赞）、账号明细、作品排行、CSV 导出、飞书/钉钉推送 |
| AI 创作 | /ai | 积分余额、创建任务（文案同步/视频异步轮询）、结果查看 |
| 订阅与账单 | /billing | 套餐卡片、订阅/续费/席位/积分包下单、模拟支付、发票申请 |
| 团队管理 | /team | 团队设置（审核流/webhook）、邀请成员、角色管理、操作日志 |

## 目录结构

```
client/
├── electron/            # 主进程 + preload（contextBridge）
├── src/
│   ├── api/             # http.ts（token 注入/401 静默刷新/统一错误提示）+ modules.ts（全部接口）
│   ├── stores/          # pinia：登录态持久化
│   ├── router/          # hash 路由 + 登录守卫
│   ├── layouts/         # 侧边栏 + 顶栏（未读消息角标）
│   ├── views/           # 9 个业务页面 + 登录页
│   ├── types/           # 与 server Pydantic 对齐的类型
│   └── utils/           # 数字/时间/状态标签格式化
├── vite.config.ts       # electron 插件 + /api 代理 + WEB_ONLY 开关
├── pnpm-workspace.yaml  # pnpm 11 配置：allowBuilds 安装脚本白名单
└── uno.config.ts        # UnoCSS + 图标（@iconify-json/carbon）
```

## 约定

- 响应统一 `{code, message, data}`，`code !== 0` 自动 toast，`401` 自动刷新 token 重试一次，失败跳登录
- 生产环境 API 地址在 `.env.production` 的 `VITE_API_BASE` 中配置
- 开发环境 `/api` 由 vite 代理到 `http://127.0.0.1:8000`
