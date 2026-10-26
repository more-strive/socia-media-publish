/// <reference types="vite/client" />
declare module '*.vue' {
import type { DefineComponent } from 'vue'
const component: DefineComponent<object, object, unknown>
export default component
}
// 直接 import 图标集 JSON，避免 unocss 文件系统自动加载失败（pnpm 环境下不稳）
declare module '@iconify-json/carbon/icons.json' {
  const icons: { prefix: string; icons: Record<string, { body: string }> }
  export default icons
}
interface Window {
electronAPI?: {
  platform: string
  versions: { electron: string; chrome: string; node: string }
  rpa?: {
    loginDouyin: (accountId: number) => Promise<{ ok: boolean; message: string; nickname?: string }>
    executeDouyin: (payload: {
      item_id: number
      account_id: number
      title: string
      media_url: string
    }) => Promise<{ ok: boolean; message: string; publishUrl?: string }>
  }
  engine?: {
    start: (opts: { baseUrl: string; token: string }) => Promise<void>
    stop: () => Promise<void>
    setEnabled: (v: boolean) => Promise<void>
    status: () => Promise<{
      running: boolean
      enabled: boolean
      busy: boolean
      deviceId: string
      current: unknown
      logs: string[]
    }>
    onEvent: (cb: (ev: { type: string } & Record<string, unknown>) => void) => () => void
  }
  tabs?: {
    open: (opts: { url: string; partition?: string; title?: string }) => Promise<number>
    activate: (id: number) => Promise<void>
    close: (id: number) => Promise<void>
    rect: (rect: { x: number; y: number; width: number; height: number } | null) => Promise<void>
    state: () => Promise<{ tabs: { id: number; title: string; url: string }[]; activeId: number | null }>
    onChanged: (cb: (s: { tabs: { id: number; title: string; url: string }[]; activeId: number | null }) => void) => () => void
  }
}
}
