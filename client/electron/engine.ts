/** RPA 执行引擎（主进程常驻）：认领 → 执行 → 回报，独立于渲染层存活（对标蚁小二 publish_service）
 *  渲染层只注入凭证与展示事件；设计见 docs/client改造计划.md M0 */
import { createWriteStream, existsSync, readFileSync } from 'node:fs'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Readable } from 'node:stream'
import type { ReadableStream as NodeWebReadableStream } from 'node:stream/web'
import { pipeline } from 'node:stream/promises'
import electron from 'electron'
import type { ProxyConfig } from './proxy'
import { adapterOf } from './rpa/platforms'
import { uploadScreenshot } from './upload'

const { app, ipcMain, BrowserWindow } = electron

const POLL_MS = 5000

/** server /publish/rpa/claim 返回的待执行条目（与 src/types 的 RpaClaimItem 对齐） */
export interface EngineClaim {
  item_id: number
  task_id: number
  account: {
    id: number
    platform: string
    nickname: string
    note: string | null
    /** 账号绑定代理（server 由 proxy_id 解析下发），发布与登录保持同一出口 */
    proxy: ProxyConfig | null
  }
  content: {
    id: number
    type: string
    title: string
    summary: string | null
    media: string[] | null
    tags: string[] | null
  }
  extras: Record<string, unknown> | null
}

export interface EngineStatus {
  running: boolean
  enabled: boolean
  busy: boolean
  deviceId: string
  current: EngineClaim | null
  logs: string[]
}

export type EngineEvent =
  | { type: 'log'; line: string }
  | { type: 'claim'; item: EngineClaim }
  | { type: 'done'; item: EngineClaim; ok: boolean; message: string }
  | { type: 'auth-expired' }

interface EngineStartOpts {
  baseUrl: string
  token: string
}

class AuthExpiredError extends Error {}

let creds: EngineStartOpts | null = null
let timer: ReturnType<typeof setInterval> | null = null
let busy = false
let authPaused = false
let current: EngineClaim | null = null
const logs: string[] = []

// ---- 持久化（userData/engine.json）：device_id 与自动执行开关 ----
function configFile(): string {
  return join(app.getPath('userData'), 'engine.json')
}

function loadState(): { deviceId: string; enabled: boolean } {
  try {
    if (existsSync(configFile())) {
      const raw = JSON.parse(readFileSync(configFile(), 'utf8')) as { device_id?: string; enabled?: boolean }
      if (raw.device_id) return { deviceId: raw.device_id, enabled: raw.enabled !== false }
    }
  } catch {
    /* 损坏则重建 */
  }
  return { deviceId: crypto.randomUUID(), enabled: false }
}

let state = loadState()

function saveState(): void {
  void writeFile(configFile(), JSON.stringify({ device_id: state.deviceId, enabled: state.enabled })).catch(
    () => undefined,
  )
}

function log(line: string): void {
  logs.unshift(`[${new Date().toLocaleTimeString()}] ${line}`)
  if (logs.length > 60) logs.length = 60
  broadcast({ type: 'log', line: logs[0] })
}

function broadcast(ev: EngineEvent): void {
  for (const w of BrowserWindow.getAllWindows()) {
    if (!w.isDestroyed()) w.webContents.send('engine:event', ev)
  }
}

// ---- server API（token 由渲染层注入；401 抛 AuthExpiredError 并暂停循环）----
async function api<T>(path: string, body: unknown): Promise<T> {
  if (!creds) throw new Error('引擎未启动')
  const res = await fetch(`${creds.baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${creds.token}` },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  })
  if (res.status === 401) {
    authPaused = true
    broadcast({ type: 'auth-expired' })
    log('登录态失效，等待渲染层刷新后重启引擎')
    throw new AuthExpiredError('token 失效')
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const json = (await res.json()) as { code: number; data: T }
  if (json.code !== 0) throw new Error(`业务错误 code=${json.code}`)
  return json.data
}

async function report(payload: {
  item_id: number
  success: boolean
  publish_url?: string
  fail_reason?: string
  screenshots?: string[]
}): Promise<void> {
  await api('/publish/rpa/report', payload)
}

/** 截图归档：尽力而为，失败仅记日志（不影响回报主流程） */
async function archiveShots(item: EngineClaim, paths: string[]): Promise<string[]> {
  if (!paths.length || !creds) return []
  const urls: string[] = []
  for (const p of paths) {
    try {
      // eslint-disable-next-line no-await-in-loop
      urls.push(await uploadScreenshot(creds, p, 'publish', item.item_id))
    } catch {
      /* 归档失败不阻断回报 */
    }
  }
  return urls
}

/** 素材准备：http(s) 流式下载到临时文件（不整包进内存）；本地路径直接使用 */
export async function prepareMedia(mediaUrl: string): Promise<string> {
  if (!/^https?:\/\//.test(mediaUrl)) return mediaUrl
  const res = await fetch(mediaUrl)
  if (!res.ok) throw new Error(`素材下载失败 HTTP ${res.status}`)
  const name = mediaUrl.split('/').pop()?.split('?')[0] || 'video.mp4'
  const dir = await mkdtemp(join(tmpdir(), 'smp-rpa-'))
  const path = join(dir, name)
  await pipeline(Readable.fromWeb(res.body as unknown as NodeWebReadableStream), createWriteStream(path))
  return path
}

async function executeOne(item: EngineClaim): Promise<void> {
  current = item
  broadcast({ type: 'claim', item })
  const tag = `#${item.item_id} ${item.account.nickname}`
  try {
    const adapter = adapterOf(item.account.platform)
    if (!adapter) throw new Error(`平台 ${item.account.platform} 暂不支持 RPA 执行`)
    const media = item.content.media?.[0]
    if (!media) throw new Error('内容缺少素材文件')
    const mediaPath = await prepareMedia(media)
    const out = await adapter.publish({
      itemId: item.item_id,
      accountId: item.account.id,
      title: item.content.title,
      mediaPath,
      proxy: item.account.proxy ?? undefined,
    })
    const shots = await archiveShots(item, out.screenshots ?? [])
    await report({
      item_id: item.item_id,
      success: out.ok,
      publish_url: out.publishUrl,
      fail_reason: out.ok ? undefined : out.message,
      screenshots: shots,
    })
    log(`${tag}：${out.ok ? '发布成功' : `失败 - ${out.message}`}`)
    broadcast({ type: 'done', item, ok: out.ok, message: out.message })
  } catch (e) {
    // 执行异常也要回报，避免条目卡在 dispatched 等超时回收
    await report({ item_id: item.item_id, success: false, fail_reason: String(e) }).catch(() => undefined)
    log(`${tag}：异常 - ${e}`)
    broadcast({ type: 'done', item, ok: false, message: String(e) })
  } finally {
    current = null
  }
}

async function tick(): Promise<void> {
  if (busy || !creds || !state.enabled || authPaused) return
  busy = true
  try {
    const data = await api<EngineClaim[] | { items?: EngineClaim[] }>('/publish/rpa/claim', {
      device_id: state.deviceId,
      capacity: 1,
    })
    const items = Array.isArray(data) ? data : (data.items ?? [])
    for (const item of items) await executeOne(item)
  } catch {
    /* 认领失败（网络抖动等）下轮再试，不打日志避免刷屏 */
  } finally {
    busy = false
  }
}

// ---- 对渲染层暴露的引擎控制 ----
function start(opts: EngineStartOpts): void {
  creds = { baseUrl: opts.baseUrl.replace(/\/$/, ''), token: opts.token }
  authPaused = false
  if (timer) clearInterval(timer)
  timer = setInterval(() => void tick(), POLL_MS)
  log('RPA 引擎已启动，每 5s 认领一次')
  void tick()
}

function stop(): void {
  if (timer) clearInterval(timer)
  timer = null
  creds = null
  log('RPA 引擎已停止')
}

function status(): EngineStatus {
  return { running: timer !== null, enabled: state.enabled, busy, deviceId: state.deviceId, current, logs: [...logs] }
}

/** 注册 engine IPC；应用启动即挂载（循环要等渲染层注入凭证 start 才开跑） */
export function initEngine(): void {
  ipcMain.handle('engine:start', (_e, opts: EngineStartOpts) => start(opts))
  ipcMain.handle('engine:stop', () => stop())
  ipcMain.handle('engine:set-enabled', (_e, v: boolean) => {
    state = { ...state, enabled: !!v }
    saveState()
    log(v ? '已开启自动执行' : '已暂停自动执行')
    if (v) void tick()
  })
  ipcMain.handle('engine:status', () => status())
  app.on('before-quit', stop)
}
