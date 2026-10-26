# client 改造计划（对标蚁小二桌面端）

> 依据：[蚁小二功能分析.md](./蚁小二功能分析.md)（Web 端功能面）+ 本机蚁小二4.0（4.13.19）客户端实证剖析（安装目录/用户数据目录结构，2026-10）。
> 分析口径：仅读取目录结构与元数据，未使用其代码。

## 一、对标实证（蚁小二怎么做的）

1. **执行体独立**：发布执行跑在独立 `publish_service` 侧车进程（`platform-service/logs/publish_service_*.log`，构建依赖含 NestJS），不依赖 UI 存活。
2. **平台脚本热更新**：`online-srcripts-2/rpa`、`online-srcripts/reptile` 目录 + `config.json` 的 `rpaVersion`/`reptileVersion` 键 —— 平台选择器/流程逻辑由服务端按版本下发，改脚本不发客户端版本。这是它维护 40+ 平台的根本。
3. **会话隔离**：Electron `Partitions`（`auth-<团队ID>` 授权会话；`default-session-create-tab-N` 每个内嵌标签独立 session）。
4. **双发布通道**：内置浏览器 RPA 之外，另有 Chrome 扩展（浏览器发布助手）经本地 socket.io 借用户真实浏览器执行，风控更友好。
5. **素材链路**：火山 TOS 云端中转（tos-crc64-js）+ 本地 `uploads` 缓存；客户端本质是"常驻执行宿主"。

## 二、我们的差距（摘要）

- 引擎循环在渲染层 composable（关页面/切路由即停摆）；
- [douyin.ts](../client/electron/rpa/douyin.ts) 单文件，无平台抽象，视图层还有 `platform === 'douyin'` 硬编码；
- [main.ts](../client/electron/main.ts) 的 `prepareVideo` 用 `arrayBuffer()` 整包进内存；
- 登录态只在发布瞬间检查，无探活/批量重授权；partition 未绑定账号级代理。

## 三、里程碑

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | RPA 引擎主进程化：认领-执行-回报循环、deviceId/开关持久化、事件推送、token 注入、素材流式下载 | **本轮实施** |
| M1 | 平台适配器注册表：`PlatformAdapter` 接口 + registry，抖音先行适配 | **本轮实施** |
| M2 | 视图去硬编码：AccountsView 的 `platform === 'douyin'` 判断改为注册表能力查询 | 下轮（接入第二平台时一并做） |
| M3 | 脚本声明式化 + server 版本下发（对标 online-srcripts；**必须带签名校验**，防止任意代码下发变成 RCE 面） | 待启动 |
| M4 | 账号可信度：登录态定时探活 + 批量重授权、partition 会话绑定账号级代理、失败退避重试 + 风控弹窗检测、每步截图 URL 随回报归档 | 待启动 |
| M5 | 体验与对齐：electron-updater 自动更新、账号浏览器 UX（按账号分组/状态角标）、Chrome 扩展发布通道（远期） | 待启动 |

## 四、M0/M1 设计（本轮）

### 新增 `electron/rpa/platforms.ts`
- `PlatformAdapter` 接口：`{ code, login(accountId), publish(input) }`；`registry` + `adapterOf(platform)`；
- 抖音适配器薄封装现有 `loginDouyin`/`publishDouyinVideo`，行为不变。

### 新增 `electron/engine.ts`（主进程引擎）
- 循环：每 5s 认领 `/publish/rpa/claim`（Bearer token，`{device_id, limit: 1}`），按 `item.account.platform` 取适配器执行，`/publish/rpa/report` 回报；执行异常同样回报，避免条目卡在 dispatched 等超时回收。
- 持久化：`userData/engine.json`（`device_id`、`enabled`）。
- IPC：`engine:start {baseUrl, token}` / `engine:stop` / `engine:set-enabled` / `engine:status`。
- 事件：`engine:event {type: log|claim|done|auth-expired, ...}` 广播到各窗口；日志环形 60 条，`status` 一次性带回。
- token 由渲染层注入（主进程不重复实现登录/刷新，也不落盘 token）；401 → `auth-expired`，暂停循环，渲染层换新 token 重启。
- 素材准备移入引擎 `prepareMedia`：http(s) 素材**流式下载**（`Readable.fromWeb` + `pipeline`），不再整包进内存。

### `electron/main.ts`
- 注册 engine IPC，应用启动即初始化引擎（不自动开跑，等渲染层注入凭证 start）；
- `rpa:douyin-exec` 手动通道保留，内部改走引擎的 `prepareMedia` + 适配器，避免两份下载逻辑。

### 渲染层
- [useRpaEngine.ts](../client/src/composables/useRpaEngine.ts) 重写为"控制台"：不再自建 `setInterval`；状态来自 `engine:status` + `engine:event`；
- **对外 API（enabled/busy/current/logs/canRun/start/toggle/bindDouyin）签名不变**，AdminLayout/AccountsView 无感；
- 收到 `claim` 事件仍跳转 `/browser` 展示自动化过程（沿用现状）；
- 登录后/布局挂载时携带 token 调 `engine:start`；收到 `auth-expired` 用新 token 重启引擎。

## 五、验收
1. `pnpm typecheck` 通过；
2. 引擎启动后切换路由/离开 `/browser`，认领与发布不中断（主进程循环）；
3. `setEnabled(false)` 后不再认领，重新开启恢复；
4. 抖音发布行为与改造前一致（每步截图、失败保留标签页）。

## 六、风险
- token 过期窗口：认领前不预校验，401 后暂停，最长空转一个轮询周期（5s）；
- 主进程 fetch 与渲染层 axios 的 baseURL 一致性由渲染层统一注入保证；
- 并发：`busy` 互斥沿用；多窗口只广播状态，执行循环进程内单实例。

## 七、M6：页面结构对齐蚁小二（进行中）

现状盘点：页面内部结构已较齐（发布页已有 任务/待审核/发布日历；账号域已有 分组 CRUD/批量有效性检测/重新授权/代理 IP；私信页已有 收件箱/自动回复/话术库），主要差距在**顶层信息架构**——侧边栏是 10 项扁平菜单。

| 动作 | 状态 |
|---|---|
| 侧边栏按业务域分组：工作台（顶部）+ 内容分发（一键分发/内容中心）+ 账号运营（账号管理/账号浏览器）+ 互动 + 数据 + 创作 + 管理（团队/订阅账单） | 本轮实施（分组命名暂按功能域推断） |
| 蚁小二客户端真实界面取证（CDP DOM 提取或截屏视觉分析），据实微调分组与命名 | 待用户在交互会话打开蚁小二 |
| 工作台首页改版：待办（待审核数/失效账号数/RPA 队列）+ 快捷入口 + 核心数据卡片 | 待启动 |

注：从自动化会话拉起蚁小二4.0.exe 会立即退出（无参 exit=0，带 --remote-debugging-port 为 exit=9），疑似 updater/elevate 提升链路或非交互会话防护，需在用户交互会话手动启动后再取证。

## M6 补充实证：web 版（www.yixiaoer.cn/web）信息架构

> 2026-10-26 通过 web 版 Vite bundle（入口 index-*.js，仅提取界面文案与路由路径）还原：

- 路由：overview（数据总览，含达人/排行子页）、publish、tasks、accounts、environments、asset-library、social、team、order、operation-log、system-notifications、digital-human、long-article/editor、tryout
- 账号页为三页签：账号管理 / 分组管理 / 指纹环境（"指纹环境"= 环境隔离管理，对应我方 M4 的 partition+代理方案，方向验证成立）
- 私信评论在 web 版外跳 qdy.com，桌面端内置；商业化为"功能包"模式（私信评论包，资源席位不足/超额熔断自动禁用高级功能）
- 快捷命令注册表：授权账号 / 批量授权失效账号 / 批量检测失效账号 / 打开收藏分组 / 发布视频命令

### 本轮落地（M6 第二批）

- 工作台改版：新增本机 RPA 引擎状态条（运行状态 + 当前任务 + 开关，仅桌面端显示）、汇总卡片补 托管账号(含失效数)/待审核/今日发布
- 侧边栏分组结构已与 web 版 IA 对齐（分发/账号/互动/数据/创作/管理）
- 后续可选：operation-log 操作日志、system-notifications 系统通知（服务端需新增对应表与接口）
