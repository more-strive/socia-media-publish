/** RPA 引擎控制台：执行循环在主进程（electron/engine.ts），这里只做凭证注入与状态镜像
 *  对外 API 与旧版渲染层轮询实现保持一致，AdminLayout/AccountsView 无感切换 */
import { computed, ref } from 'vue'
import router from '@/router'
import type { RpaClaimItem } from '@/types'

const enabled = ref(false)
const busy = ref(false)
const running = ref(false)
const current = ref<RpaClaimItem | null>(null)
const logs = ref<string[]>([])
let bound = false
// 旧版把开关存在渲染层 localStorage，首次启动迁移到主进程 userData
const LEGACY_KEY = 'rpa_enabled'

const canRun = computed(() => !!window.electronAPI?.engine)

function pushLog(line: string): void {
  logs.value.unshift(`[${new Date().toLocaleTimeString()}] ${line}`)
  if (logs.value.length > 60) logs.value.length = 60
}

/** 相对 baseURL（开发态走 vite 代理）需拼页面 origin，主进程 fetch 才有绝对地址 */
function engineBaseUrl(): string {
  const base = (import.meta.env.VITE_API_BASE as string) || '/api/v1'
  return /^https?:/.test(base) ? base : `${location.origin}${base}`
}

function inject(): Promise<void> {
  const token = localStorage.getItem('token') ?? ''
  return window.electronAPI!.engine!.start({ baseUrl: engineBaseUrl(), token })
}

async function syncStatus(): Promise<void> {
  const s = await window.electronAPI?.engine?.status()
  if (!s) return
  enabled.value = s.enabled
  busy.value = s.busy
  running.value = s.running
  current.value = (s.current as RpaClaimItem | null) ?? null
  if (logs.value.length === 0) logs.value = [...s.logs]
}

async function start(): Promise<void> {
  if (!canRun.value) return
  const legacy = localStorage.getItem(LEGACY_KEY)
  if (legacy !== null) {
    localStorage.removeItem(LEGACY_KEY)
    await window.electronAPI?.engine?.setEnabled(legacy === '1')
  }
  await inject()
  await syncStatus()
  if (bound) return
  bound = true
  window.electronAPI?.engine?.onEvent((ev) => {
    if (ev.type === 'log') {
      pushLog(String(ev.line))
    } else if (ev.type === 'claim') {
      current.value = ev.item as RpaClaimItem
      // 跳到账号浏览器页展示自动化过程（主进程执行不依赖页面存活）
      void router.push('/browser')
    } else if (ev.type === 'done') {
      current.value = null
    } else if (ev.type === 'auth-expired') {
      // 渲染层 http 拦截器会刷新 localStorage 里的 token，这里重注入即可恢复
      void inject()
    }
  })
}

async function toggle(v: boolean | string | number): Promise<void> {
  enabled.value = !!v
  await window.electronAPI?.engine?.setEnabled(!!v)
}

/** 按平台打开扫码登录标签页（主进程适配器分发），返回结果由调用方提示 */
function bindPlatform(platform: string, accountId: number): Promise<{ ok: boolean; message: string; nickname?: string }> {
  if (!window.electronAPI?.rpa?.login) return Promise.resolve({ ok: false, message: '仅桌面端可用' })
  void router.push('/browser')
  return window.electronAPI.rpa.login(platform, accountId)
}

export function useRpaEngine() {
  return { enabled, busy, current, logs, canRun, running, start, toggle, bindPlatform }
}
