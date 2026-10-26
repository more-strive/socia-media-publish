/** 应用内多标签第三方页面：WebContentsView 挂在主窗口，由渲染层 /browser 页上报显示区域 */
import electron from 'electron'

const { WebContentsView, session } = electron

export interface TabInfo {
  id: number
  title: string
  url: string
}

export interface TabsState {
  tabs: TabInfo[]
  activeId: number | null
}

interface Tab extends TabInfo {
  view: InstanceType<typeof WebContentsView>
}

let seq = 0
const tabs = new Map<number, Tab>()
let bounds: Electron.Rectangle = { x: 0, y: 0, width: 0, height: 0 }
let activeId: number | null = null
let mainWindow: electron.BrowserWindow | null = null

function state(): TabsState {
  return {
    tabs: [...tabs.values()].map(({ id, title, url }) => ({ id, title, url })),
    activeId,
  }
}

function emit(): void {
  mainWindow?.webContents.send('tabs:changed', state())
}

/** 只把激活的 view 附到窗口上（其余作为后台标签保活） */
function syncAttached(): void {
  if (!mainWindow || mainWindow.isDestroyed()) return
  for (const t of tabs.values()) mainWindow.contentView.removeChildView(t.view)
  const active = activeId != null ? tabs.get(activeId) : undefined
  if (active) {
    mainWindow.contentView.addChildView(active.view)
    active.view.setBounds(bounds)
  }
}

export function initTabs(win: electron.BrowserWindow): void {
  mainWindow = win
  syncAttached()
  emit()
}

export function resetTabs(): void {
  mainWindow = null
  for (const t of tabs.values()) {
    try {
      t.view.webContents.close()
    } catch {
      /* 已销毁 */
    }
  }
  tabs.clear()
  activeId = null
}

export function openTab(opts: { url: string; partition?: string; title?: string; proxyRules?: string }): number {
  const view = new WebContentsView({
    webPreferences: { partition: opts.partition, contextIsolation: true, nodeIntegration: false },
  })
  const id = ++seq
  const tab: Tab = { id, title: opts.title ?? opts.url, url: opts.url, view }
  tabs.set(id, tab)
  view.webContents.on('page-title-updated', (_e, title) => {
    tab.title = title
    emit()
  })
  // 账号绑定的代理：setProxy 生效后再加载页面，避免首屏仍走直连（代理随 partition 持久生效）
  const load = (): void => {
    void view.webContents.loadURL(opts.url)
  }
  if (opts.partition && opts.proxyRules) {
    void session
      .fromPartition(opts.partition)
      .setProxy({ mode: 'fixed_servers', proxyRules: opts.proxyRules })
      .then(load)
      .catch(load)
  } else {
    load()
  }
  activeId = id
  syncAttached()
  emit()
  return id
}

export function activateTab(id: number): void {
  if (!tabs.has(id)) return
  activeId = id
  syncAttached()
  emit()
}

export function closeTab(id: number): void {
  const tab = tabs.get(id)
  if (!tab) return
  tabs.delete(id)
  try {
    mainWindow?.contentView.removeChildView(tab.view)
    tab.view.webContents.close()
  } catch {
    /* 已销毁 */
  }
  if (activeId === id) activeId = [...tabs.keys()].at(-1) ?? null
  syncAttached()
  emit()
}

/** 渲染层上报标签容器区域（DIP）；null 表示离开页面，隐藏所有标签 */
export function setTabBounds(
  rect: { x: number; y: number; width: number; height: number } | null,
): void {
  bounds = rect ? { ...rect } : { x: 0, y: 0, width: 0, height: 0 }
  syncAttached()
}

export function tabWebContents(id: number): electron.WebContents | undefined {
  return tabs.get(id)?.view.webContents
}

export function tabsState(): TabsState {
  return state()
}
