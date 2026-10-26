import electron from 'electron'
const { contextBridge, ipcRenderer } = electron
interface DouyinExecPayload {
  item_id: number
  account_id: number
  title: string
  media_url: string
}
interface TabsState {
  tabs: { id: number; title: string; url: string }[]
  activeId: number | null
}
interface EngineStatus {
  running: boolean
  enabled: boolean
  busy: boolean
  deviceId: string
  current: unknown
  logs: string[]
}
interface EngineEvent {
  type: 'log' | 'claim' | 'done' | 'auth-expired'
  line?: string
  item?: unknown
  ok?: boolean
  message?: string
}
// 渲染进程可用的桥接：只暴露 invoke 型 IPC，不透传能力
contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  versions: { electron: process.versions.electron, chrome: process.versions.chrome, node: process.versions.node },
  rpa: {
    /** 打开抖音扫码登录窗口（每账号独立 session），成功返回 { ok, message } */
    loginDouyin: (accountId: number): Promise<{ ok: boolean; message: string }> =>
      ipcRenderer.invoke('rpa:login-douyin', accountId),
    /** 执行一条抖音发布任务（主进程下载素材 + 浏览器自动化） */
    executeDouyin: (payload: DouyinExecPayload): Promise<{ ok: boolean; message: string; publishUrl?: string }> =>
      ipcRenderer.invoke('rpa:execute-douyin', payload),
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
    open: (opts: { url: string; partition?: string; title?: string }): Promise<number> =>
      ipcRenderer.invoke('tabs:open', opts),
    activate: (id: number): Promise<void> => ipcRenderer.invoke('tabs:activate', id),
    close: (id: number): Promise<void> => ipcRenderer.invoke('tabs:close', id),
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
