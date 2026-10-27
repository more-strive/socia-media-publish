import electron from 'electron'
const { contextBridge, ipcRenderer } = electron
interface TabItem {
  id: number
  title: string
  url: string
  loading: boolean
  canBack: boolean
  canFwd: boolean
  /** 静默执行中的标签（RPA 自动发布），点击可切换查看 */
  background: boolean
}
interface TabsState {
  tabs: TabItem[]
  activeId: number | null
}
interface EngineStatus {
  running: boolean
  enabled: boolean
  busy: boolean
  deviceId: string
  current: unknown
  pendingCount: number
  logs: string[]
}
interface EngineEvent {
  type: 'log' | 'claim' | 'done' | 'auth-expired' | 'pending'
  line?: string
  item?: unknown
  ok?: boolean
  message?: string
  count?: number
}
interface ElectronProxy {
  scheme: string
  host: string
  port: number
  username?: string | null
  password?: string | null
}
// 渲染进程可用的桥接：只暴露 invoke 型 IPC，不透传能力
contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  versions: { electron: process.versions.electron, chrome: process.versions.chrome, node: process.versions.node },
  rpa: {
    /** 按平台打开扫码/登录标签页（主进程适配器注册表分发），成功带回平台账号身份（昵称/UID/头像） */
    login: (
      platform: string,
      accountId: number,
      proxy?: ElectronProxy,
    ): Promise<{ ok: boolean; message: string; nickname?: string; platformUid?: string; avatar?: string }> =>
      ipcRenderer.invoke('rpa:login', platform, accountId, proxy),
    /** 登录态探测（开页验证 + 截图归档；auth_status 回写由调用方负责） */
    probe: (
      platform: string,
      accountId: number,
      proxy?: ElectronProxy,
      archive?: { baseUrl: string; token: string },
    ): Promise<{ ok: boolean; valid: boolean; message: string; screenshotUrl?: string }> =>
      ipcRenderer.invoke('rpa:probe', platform, accountId, proxy, archive),
  },
  platforms: {
    /** 已接入 RPA 的平台代码列表（视图据此判断平台能力） */
    list: (): Promise<string[]> => ipcRenderer.invoke('platforms:list'),
  },
  engine: {
    /** 注入凭证并启动主进程执行引擎（认领-执行-回报循环） */
    start: (opts: { baseUrl: string; token: string }): Promise<void> => ipcRenderer.invoke('engine:start', opts),
    /** 停止引擎循环（持久化的开关状态保留） */
    stop: (): Promise<void> => ipcRenderer.invoke('engine:stop'),
    /** 自动执行开关（持久化在主进程 userData） */
    setEnabled: (v: boolean): Promise<void> => ipcRenderer.invoke('engine:set-enabled', v),
    status: (): Promise<EngineStatus> => ipcRenderer.invoke('engine:status'),
    onEvent: (cb: (ev: EngineEvent) => void): (() => void) => {
      const listener = (_e: unknown, data: EngineEvent): void => cb(data)
      ipcRenderer.on('engine:event', listener)
      return () => ipcRenderer.removeListener('engine:event', listener)
    },
  },
  tabs: {
    open: (opts: {
      url: string
      partition?: string
      title?: string
      proxy?: ElectronProxy
      background?: boolean
      hidden?: boolean
    }): Promise<number> => ipcRenderer.invoke('tabs:open', opts),
    activate: (id: number | null): Promise<void> => ipcRenderer.invoke('tabs:activate', id),
    close: (id: number): Promise<void> => ipcRenderer.invoke('tabs:close', id),
    /** 地址栏导航（裸域名自动补 https） */
    navigate: (id: number, url: string): Promise<void> => ipcRenderer.invoke('tabs:navigate', id, url),
    /** 后退/前进/刷新 */
    nav: (id: number, action: 'back' | 'forward' | 'reload'): Promise<void> =>
      ipcRenderer.invoke('tabs:nav', id, action),
    /** 新标签快捷入口（各平台创作者中心） */
    quickLinks: (): Promise<{ code: string; name: string; url: string }[]> =>
      ipcRenderer.invoke('tabs:quick-links'),
    rect: (rect: { x: number; y: number; width: number; height: number } | null): Promise<void> =>
      ipcRenderer.invoke('tabs:rect', rect),
    state: (): Promise<TabsState> => ipcRenderer.invoke('tabs:state'),
    onChanged: (cb: (s: TabsState) => void): (() => void) => {
      const listener = (_e: unknown, data: TabsState): void => cb(data)
      ipcRenderer.on('tabs:changed', listener)
      return () => ipcRenderer.removeListener('tabs:changed', listener)
    },
  },
})
