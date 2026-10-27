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

### M2 完成（2026-10-26）

- IPC 改为平台无关：`platforms:list`（注册表清单）+ `rpa:login(platform, accountId)`（适配器分发），删除 `rpa:login-douyin` / `rpa:execute-douyin`（后者渲染层已无调用方，属 M0 引擎化后的死代码）
- 渲染层新增 `usePlatforms()` composable；AccountsView 4 处 `platform === 'douyin'` 硬编码全部改 `isRpa(platform)` 能力查询
- 新平台接入从"改 N 个视图"收敛为"实现 PlatformAdapter + 注册"两步

### M4 第一批（2026-10-26）：登录探测

- `probeDouyinLogin`：cookie 预检（无 cookie 直接判失效，不开窗）+ 开创作者首页验证是否被 302 登录页 + 截图留档 rpa-logs
- 适配器新增可选能力 `probe?`（ProbeResult）；IPC `rpa:probe(platform, accountId)`；composable `probeLogin`
- AccountsView 行内"检测登录"按钮（逐行 loading），结果回写服务端 auth_status（AccountUpdateIn 新增可选 auth_status 字段，exclude_none 语义下安全）
- 待办（M4 第二批）：partition 绑定代理（tabs.openTab 加 proxyRules + session.setProxy）、探测截图上传服务端归档、批量探测

### M4 第二批（2026-10-26）：partition 绑代理 + 批量探测

- tabs.openTab 支持 proxyRules：setProxy(fixed_servers) 生效后再 loadURL（防首屏直连竞态），代理随 partition 会话持久
- 账号绑定的代理（proxy_id → ProxyIP）在视图侧拼装 scheme://host:port，经 rpa:login / rpa:probe 全链路透传到 openTab（登录即走代理，cookie 留在代理环境里）
- AccountsView 工具栏新增"批量检测登录态"：顺序探测当前页 RPA 账号并回写 auth_status，逐行 loading，完成提示 N/M 有效
- 局限：ProxyIP 类型无账密字段，认证代理需后续扩展（类型+server schema）；引擎发布路径的代理接入需服务端 claim 携带代理信息（M4 第三批）

### M4 第三批（2026-10-26）：引擎发布链路走账号代理 + 认证代理

- server `/publish/rpa/claim` 携带账号绑定代理：`account.proxy = {scheme, host, port, username, password}`（proxy_id → ProxyIP 批量解析），引擎 publish 与登录/探测同出口
- 认证代理支持：`ProxyOut` 下发账密（proxies 路由随之收紧为 owner/admin/operator，与 RPA 派发同门槛）；主进程新增 `electron/proxy.ts`——fixed_servers 规则不支持内嵌账密，凭据登记后经 `app 'login'` 事件应答 407 挑战
- 代理透传从 `proxyRules: string` 全面改为结构化 `ProxyConfig`（IPC rpa:login/rpa:probe/tabs:open、适配器接口、engine claim、渲染层 types/composable）；`publishDouyinVideo` 的 openTab 补上代理（此前发布走直连）
- AccountsView 补齐 proxy_id 的 UI 入口：账号弹窗"绑定代理"选择器 + 列表"代理"列（闭环 M4 第二批只差视图绑定的问题）
- 局限：素材下载（prepareMedia）仍直连（Node fetch 走代理需 undici ProxyAgent，素材来自自家 server，风险低）；AccountUpdateIn 为 exclude_none 语义，清空代理/分组需后续改为 exclude_unset；探测截图上传服务端归档仍待做（需新增上传接口）

### M4 第四批（2026-10-26）：执行截图服务端归档

- server 新增 `POST /publish/rpa/screenshot`（multipart，PNG≤5MB，kind=publish|probe），落盘 `uploads/rpa/<kind>/<yyyymm>/<uuid>.png`，经 `/api/v1/files` 静态暴露（挂在 api 前缀下复用客户端 /api 反向代理；开发态 vite proxy 直通）
- 发布归档：douyin 每步截图（shot）收集本地路径随结果返回，引擎回报前批量上传（尽力而为，失败不阻断回报），URL 随 `/publish/rpa/report` 写入 `publish_items.screenshots`（≤8 张）；PublishView 任务详情条目表新增"截图"列（缩略图 + 点击预览）
- 探测归档：`rpa:probe` IPC 增加可选 archive 凭证参数（渲染层注入 localStorage token），主进程上传探测截图并把 URL 随结果返回，AccountsView 回写 `social_accounts.last_probe_screenshot`，"最近检测"列显示缩略图
- 顺带修复：`update_account` 改 `exclude_unset`（原 exclude_none 导致无法清空代理/分组等可空关联；客户端编辑表单总是显式传全量键，行为兼容）
- 新增 DB 列（create_all 不会改已有表，存量库需手工执行）：
  `ALTER TABLE publish_items ADD COLUMN screenshots JSON NULL COMMENT 'RPA 执行步骤截图 URL';`
  `ALTER TABLE social_accounts ADD COLUMN last_probe_screenshot VARCHAR(512) NULL COMMENT '最近登录探测截图 URL';`
- 局限：静态文件目录无清理策略（截图随时间累积，后续可加定期清理）；上传接口只校验 PNG 魔数与大小

### M7 第一批（2026-10-27）：多平台数据驱动接入（REA 逆向实证）

- 逆向取证：用 REA（github.com/morluto/rea）分析本机蚁小二 4.14.22（`D:\Program Files\yixiaoer`，Electron 应用），解包 app.asar 后提取其主进程/渲染层 bundle 的平台注册表（AuthorizeConfig / TargetPlatformUrl / baseStartPush / description 话题预处理规则），实证数据归档见 docs/蚁小二功能分析.md 附录
- `electron/rpa/registry.ts`：平台元数据表（code/authorizeUrl/entryUrl/publishVideoUrl/loginCookie 判定/loginRedirectKeywords/标题与文件选择器/发布按钮文案组/成功文案/话题风格），首批 8 平台：快手、小红书、B 站、头条、微博、视频号、百家号、知乎（URL 与登录 cookie 判定为蚁小二实证值；选择器为启发式候选，靠步骤截图归档迭代）
- `electron/rpa/generic.ts`：元数据驱动通用适配器（login = 开授权页轮询分区 cookie；probe = 开入口页判登录页重定向；publish = CDP setFileInputFiles 注入视频 → fillText 填标题 → clickByTextExpr 文案组点发布 → URL 离开/成功文案判定），批量注册进 platforms.ts 注册表（视图层 M2 能力查询自动生效，无需改视图）
- `electron/rpa/util.ts`：从抖音适配器抽出共享工具（waitFor/shot/withTopics/fillText/clickByTextExpr/cdpSetFiles）；注入策略对齐蚁小二——input/textarea 走原型 value setter + input/change 事件（React 受控兼容），contenteditable 走 selectAll+execCommand insertText，失败兜底主进程 webContents.insertText；CDP getDocument 用 depth:-1+pierce 覆盖 shadow DOM
- douyin.ts 重构复用 util：发布按钮从单一精确 '发布' 升级为蚁小二 baseStartPush 文案组（发布/发表/发布作品/发 布/立即投稿，叶子节点精确匹配 + 禁用跳过）；标题支持话题追加（`#话题 ` 风格，超 5 个截断，蚁小二实证规则）
- engine claim 的 content.tags/summary 透传进适配器（PublishInput 扩展）；PLATFORM_LABELS 补百家号/知乎（server platform 为自由字符串，无需迁移）
- 登录成功判定 v1 用分区 cookie 命中（与抖音一致）；蚁小二更稳的 CDP Fetch 响应体嗅探（每平台 XHR pattern + 响应字段判定，见附录）留作 M7 第二批
- 局限：通用流程仅消费标题（含话题），正文/封面/原创声明/位置等蚁小二全量字段未接入；各平台选择器需真实账号逐步验证（失败自动截图归档定位）

### 浏览器 Shell 布局（2026-10-27，M6 延伸：对齐蚁小二桌面端形态）

- AdminLayout 改造为浏览器 Shell（蚁小二实证形态）：顶部标签条（控制台为常驻首标签 + 平台标签 + 「+」新标签快捷入口[各平台创作者中心，取自 RPA 注册表 entryUrl]）+ 导航工具条（后退/前进/刷新/地址栏[裸域名补 https]/未读消息/用户区）；原顶栏并入工具条
- 内容区：控制台标签 = 原侧边栏+页面（v-show 保活）；平台标签 = WebContentsView 覆盖层，区域由 Shell 布局上报（tabs:rect），控制台激活时上报 null 隐藏全部平台标签（后台保活）
- tabs.ts：TabInfo 增加 loading/canBack/canFwd（did-navigate/did-start-loading 等事件同步）；新增 navigateTab（地址栏）/navTab（back/forward/reload）/quickLinks；activateTab 接受 null=回控制台；新 IPC tabs:navigate、tabs:nav、tabs:quick-links
- /browser 页改为「账号浏览器」控制台页：平台快捷入口网格 + 已开标签管理（不再承担视图宿主职责）；useRpaEngine 认领/绑定时不再跳转 /browser（Shell 下平台标签全局可见，引擎开标签即自动激活）
