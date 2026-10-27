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
    login: (
      platform: string,
      accountId: number,
      proxy?: { scheme: string; host: string; port: number; username?: string | null; password?: string | null },
    ) => Promise<{ ok: boolean; message: string; nickname?: string }>
    probe: (
      platform: string,
      accountId: number,
      proxy?: { scheme: string; host: string; port: number; username?: string | null; password?: string | null },
      archive?: { baseUrl: string; token: string },
    ) => Promise<{ ok: boolean; valid: boolean; message: string; screenshotUrl?: string }>
  }
  platforms?: {
    list: () => Promise<string[]>
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
      pendingCount: number
      logs: string[]
    }>
    onEvent: (cb: (ev: { type: string } & Record<string, unknown>) => void) => () => void
  }
  tabs?: {
    open: (opts: {
      url: string
      partition?: string
      title?: string
      proxy?: { scheme: string; host: string; port: number; username?: string | null; password?: string | null }
      background?: boolean
      hidden?: boolean
    }) => Promise<number>
    activate: (id: number | null) => Promise<void>
    close: (id: number) => Promise<void>
    navigate: (id: number, url: string) => Promise<void>
    nav: (id: number, action: 'back' | 'forward' | 'reload') => Promise<void>
    quickLinks: () => Promise<{ code: string; name: string; url: string }[]>
    rect: (rect: { x: number; y: number; width: number; height: number } | null) => Promise<void>
    state: () => Promise<{
      tabs: {
        id: number
        title: string
        url: string
        loading: boolean
        canBack: boolean
        canFwd: boolean
        background: boolean
      }[]
      activeId: number | null
    }>
    onChanged: (
      cb: (s: {
        tabs: {
          id: number
          title: string
          url: string
          loading: boolean
          canBack: boolean
          canFwd: boolean
          background: boolean
        }[]
        activeId: number | null
      }) => void,
    ) => () => void
  }
}
}
