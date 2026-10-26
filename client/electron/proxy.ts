/** 账号代理统一装配：partition 会话 setProxy + 认证代理 407 挑战应答
 *  Chromium 的 fixed_servers 规则不支持内嵌账密，认证须在 app 'login' 事件回填凭据；
 *  设计见 docs/client改造计划.md M4 第三批 */
import electron from 'electron'

const { app, session } = electron

/** 账号绑定代理（server claim / ProxyIP 下发；username/password 用于认证代理） */
export interface ProxyConfig {
  scheme: string
  host: string
  port: number
  username?: string | null
  password?: string | null
}

/** Electron fixed_servers 规则（scheme://host:port），随 partition 会话持久 */
export function proxyRulesOf(proxy: ProxyConfig): string {
  return `${proxy.scheme}://${proxy.host}:${proxy.port}`
}

// host:port -> 凭据：407 挑战回调只带代理地址，按地址匹配
const credentials = new Map<string, { username: string; password: string }>()

/** 应用到 partition 会话；调用方须 await 完成后再 loadURL，防首屏直连竞态 */
export async function applySessionProxy(partition: string, proxy: ProxyConfig): Promise<void> {
  if (proxy.username && proxy.password) {
    credentials.set(`${proxy.host}:${proxy.port}`, { username: proxy.username, password: proxy.password })
  }
  await session.fromPartition(partition).setProxy({ mode: 'fixed_servers', proxyRules: proxyRulesOf(proxy) })
}

/** 认证代理应答：应用启动时注册一次 */
export function initProxyAuth(): void {
  app.on('login', (event, _wc, _details, authInfo, callback) => {
    if (!authInfo.isProxy) return
    const cred = credentials.get(`${authInfo.host}:${authInfo.port}`)
    if (!cred) return
    event.preventDefault()
    callback(cred.username, cred.password)
  })
}
