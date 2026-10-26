/** 平台适配器注册表：RPA 平台能力的统一抽象（对标蚁小二按平台拆分的在线脚本层）
 *  新平台接入：实现 PlatformAdapter 并在下方 registry 注册，引擎按 account.platform 分发 */
import { loginDouyin, publishDouyinVideo } from './douyin'

export interface PublishInput {
  itemId: number
  accountId: number
  title: string
  /** 引擎已下载就位的本地素材路径 */
  mediaPath: string
}

export interface PublishResult {
  ok: boolean
  message: string
  publishUrl?: string
}

export interface LoginResult {
  ok: boolean
  message: string
  nickname?: string
}

export interface PlatformAdapter {
  /** 平台标识，对应 server 侧 social_accounts.platform */
  code: string
  /** 扫码/登录绑定，成功后返回账号昵称 */
  login(accountId: number): Promise<LoginResult>
  publish(input: PublishInput): Promise<PublishResult>
}

const douyinAdapter: PlatformAdapter = {
  code: 'douyin',
  login: loginDouyin,
  publish: ({ itemId, accountId, title, mediaPath }) =>
    publishDouyinVideo({ accountId, itemId, title, videoPath: mediaPath }),
}

const registry: Record<string, PlatformAdapter> = { douyin: douyinAdapter }

export function adapterOf(platform: string): PlatformAdapter | undefined {
  return registry[platform]
}

/** 视图侧判断平台是否支持 RPA（M2 时经 IPC 暴露给渲染层，替代 platform === 'douyin' 硬编码） */
export function rpaPlatforms(): string[] {
  return Object.keys(registry)
}
