/** RPA 引擎：渲染层轮询认领（自带登录态）→ IPC 交主进程浏览器执行 → 回报结果 */
import { computed, ref } from 'vue'

import { rpaApi } from '@/api/modules'
import router from '@/router'
import type { RpaClaimItem } from '@/types'

const POLL_MS = 5000

const enabled = ref(localStorage.getItem('rpa_enabled') === '1')
const busy = ref(false)
const current = ref<RpaClaimItem | null>(null)
const logs = ref<string[]>([])

let timer: ReturnType<typeof setInterval> | null = null

function log(line: string): void {
  logs.value.unshift(`[${new Date().toLocaleTimeString()}] ${line}`)
  if (logs.value.length > 60) logs.value.length = 60
}

function deviceId(): string {
  let id = localStorage.getItem('rpa_device')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('rpa_device', id)
  }
  return id
}

const canRun = computed(() => !!window.electronAPI?.rpa)

async function executeOne(item: RpaClaimItem): Promise<void> {
  current.value = item
  const tag = `#${item.item_id} ${item.account.nickname}`
  // 跳到账号浏览器页，让 WebContentsView 覆盖区可见自动化过程（离开页面也不影响执行）
  void router.push('/browser')
  try {
    const media = item.content.media?.[0]
    if (!media) throw new Error('内容缺少素材文件')
    const out = await window.electronAPI!.rpa!.executeDouyin({
      item_id: item.item_id,
      account_id: item.account.id,
      title: item.content.title,
      media_url: media,
    })
    await rpaApi.report({
      item_id: item.item_id,
      success: out.ok,
      publish_url: out.publishUrl,
      fail_reason: out.ok ? undefined : out.message,
    })
    log(`${tag}：${out.ok ? '发布成功' : `失败 - ${out.message}`}`)
  } catch (e) {
    // 执行异常也要回报，避免条目卡在 dispatched 等超时回收
    await rpaApi.report({ item_id: item.item_id, success: false, fail_reason: String(e) }).catch(() => undefined)
    log(`${tag}：异常 - ${e}`)
  } finally {
    current.value = null
  }
}

async function tick(): Promise<void> {
  if (busy.value || !enabled.value || !canRun.value) return
  busy.value = true
  try {
    const items = await rpaApi.claim(deviceId(), 1)
    for (const item of items) await executeOne(item)
  } catch {
    /* 认领失败（网络抖动等）下轮再试 */
  } finally {
    busy.value = false
  }
}

export function useRpaEngine() {
  function start(): void {
    if (timer || !canRun.value) return
    timer = setInterval(() => void tick(), POLL_MS)
    log(enabled.value ? 'RPA 引擎已启动，每 5s 认领一次' : 'RPA 引擎待启用（账号管理页可开关）')
  }

  function toggle(v: boolean | string | number): void {
    enabled.value = !!v
    localStorage.setItem('rpa_enabled', enabled.value ? '1' : '0')
    log(enabled.value ? '已开启自动执行' : '已暂停自动执行')
    if (enabled.value) void tick()
  }

  /** 打开扫码登录标签页，返回结果由调用方提示 */
  function bindDouyin(accountId: number): Promise<{ ok: boolean; message: string; nickname?: string }> {
    if (!window.electronAPI?.rpa) return Promise.resolve({ ok: false, message: '仅桌面端可用' })
    void router.push('/browser')
    return window.electronAPI.rpa.loginDouyin(accountId)
  }

  return { enabled, busy, current, logs, canRun, start, toggle, bindDouyin }
}
