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
  }
}
