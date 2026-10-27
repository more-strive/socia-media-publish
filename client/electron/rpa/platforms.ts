/** 平台适配器注册表：RPA 平台能力的统一抽象（对标蚁小二按平台拆分的在线脚本层）
 *  新平台接入：优先在 registry.ts 加元数据走 generic 适配器（URL/判定规则有蚁小二实证）；
 *  流程特殊的平台（如抖音）再实现 PlatformAdapter 并在下方注册，引擎按 account.platform 分发 */
import type { ProxyConfig } from '../proxy'
import { loginDouyin, probeDouyinLogin, publishDouyinVideo } from './douyin'
import { makeAdapter } from './generic'
import { PLATFORM_METAS } from './registry'

export interface PublishInput {
  itemId: number
  accountId: number
  title: string
  /** 话题标签：按平台规则拼进标题（蚁小二 description 预处理，见 util.withTopics） */
  tags?: string[] | null
  /** 图文摘要：平台编辑器支持正文时的候选（通用流程暂只消费标题） */
  summary?: string | null
  /** 引擎已下载就位的本地素材路径 */
  mediaPath: string
  /** 账号绑定代理：发布与登录保持同一出口 */
  proxy?: ProxyConfig
}

export interface PublishResult {
  ok: boolean
  message: string
  publishUrl?: string
  /** 各步骤截图本地路径（引擎负责上传归档） */
  screenshots?: string[]
}

export interface LoginResult {
  ok: boolean
  message: string
  nickname?: string
}

export interface ProbeResult {
  ok: boolean
  valid: boolean
  message: string
  /** 探测截图本地路径（调用方注入凭证后归档） */
  screenshot?: string
  /** 归档后的服务端 URL（rpa:probe 处理器上传后回填） */
  screenshotUrl?: string
}
export interface PlatformAdapter {
  /** 平台标识，对应 server 侧 social_accounts.platform */
  code: string
  /** 扫码/登录绑定，成功后返回账号昵称 */
  login(accountId: number, proxy?: ProxyConfig): Promise<LoginResult>
  publish(input: PublishInput): Promise<PublishResult>
  /** 登录态探测（可选能力）：开页验证 cookie 是否仍有效 */
  probe?(accountId: number, proxy?: ProxyConfig): Promise<ProbeResult>
}

const douyinAdapter: PlatformAdapter = {
  code: 'douyin',
  login: loginDouyin,
  publish: ({ itemId, accountId, title, tags, mediaPath, proxy }) =>
    publishDouyinVideo({ accountId, itemId, title, tags, videoPath: mediaPath, proxy }),
  probe: probeDouyinLogin,
}

const registry: Record<string, PlatformAdapter> = {
  douyin: douyinAdapter,
  // 元数据驱动的通用适配器：快手/小红书/B站/头条/微博/视频号/百家号/知乎（URL 与登录判定为蚁小二实证）
  ...Object.fromEntries(PLATFORM_METAS.map((m) => [m.code, makeAdapter(m)])),
}

export function adapterOf(platform: string): PlatformAdapter | undefined {
  return registry[platform]
}

/** 视图侧判断平台是否支持 RPA（M2 时经 IPC 暴露给渲染层，替代 platform === 'douyin' 硬编码） */
export function rpaPlatforms(): string[] {
  return Object.keys(registry)
}
