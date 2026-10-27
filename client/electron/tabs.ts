/** 应用内多标签第三方页面（蚁小二式浏览器 Shell）：WebContentsView 挂在主窗口，
 *  由渲染层 Shell 布局上报内容区；控制台与平台页同为"标签"，活动平台标签覆盖控制台
 *  activeId = null 表示控制台标签激活（所有平台 view 脱离窗口、后台保活） */
import electron from 'electron'

import { applySessionProxy, type ProxyConfig } from './proxy'
import { PLATFORM_METAS } from './rpa/registry'

const { WebContentsView } = electron

export interface TabInfo {
  id: number
  title: string
  url: string
  loading: boolean
  canBack: boolean
  canFwd: boolean
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

function navFlags(tab: Tab): void {
  try {
    const h = tab.view.webContents.navigationHistory
    tab.canBack = h.canGoBack()
    tab.canFwd = h.canGoForward()
  } catch {
    tab.canBack = tab.canFwd = false
  }
}

function state(): TabsState {
  return {
    tabs: [...tabs.values()].map(({ id, title, url, loading, canBack, canFwd }) => ({
      id,
      title,
      url,
      loading,
      canBack,
      canFwd,
    })),
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

export function openTab(opts: { url: string; partition?: string; title?: string; proxy?: ProxyConfig }): number {
  const view = new WebContentsView({
    webPreferences: { partition: opts.partition, contextIsolation: true, nodeIntegration: false },
  })
  const id = ++seq
  const tab: Tab = {
    id,
    title: opts.title ?? opts.url,
    url: opts.url,
    loading: true,
    canBack: false,
    canFwd: false,
    view,
  }
  tabs.set(id, tab)
  const wc = view.webContents
  wc.on('page-title-updated', (_e, title) => {
    tab.title = title
    emit()
  })
  wc.on('did-start-loading', () => {
    tab.loading = true
    emit()
  })
  wc.on('did-stop-loading', () => {
    tab.loading = false
    navFlags(tab)
    emit()
  })
  wc.on('did-navigate', (_e, url) => {
    tab.url = url
    navFlags(tab)
    emit()
  })
  wc.on('did-navigate-in-page', (_e, url) => {
    tab.url = url
    navFlags(tab)
    emit()
  })
  // 账号绑定的代理：setProxy 生效后再加载页面，避免首屏仍走直连（代理随 partition 持久生效）
  const load = (): void => {
    void view.webContents.loadURL(opts.url)
  }
  if (opts.partition && opts.proxy) {
    void applySessionProxy(opts.partition, opts.proxy)
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

/** 激活标签；null = 回到控制台标签 */
export function activateTab(id: number | null): void {
  if (id !== null && !tabs.has(id)) return
  activeId = id
  syncAttached()
  emit()
}

/** 地址栏导航：裸域名自动补 https:// */
export function navigateTab(id: number, url: string): void {
  const tab = tabs.get(id)
  if (!tab || !url.trim()) return
  const target = /^https?:\/\//i.test(url.trim()) ? url.trim() : `https://${url.trim()}`
  tab.loading = true
  emit()
  void tab.view.webContents.loadURL(target).catch(() => undefined)
}

export function navTab(id: number, action: 'back' | 'forward' | 'reload'): void {
  const wc = tabs.get(id)?.view.webContents
  if (!wc) return
  try {
    if (action === 'back') wc.navigationHistory.goBack()
    else if (action === 'forward') wc.navigationHistory.goForward()
    else wc.reload()
  } catch {
    /* 页面已销毁 */
  }
}

/** 新标签快捷入口：各平台创作者中心（人工巡检/运营用，公共会话） */
export function quickLinks(): { code: string; name: string; url: string }[] {
  return [
    { code: 'douyin', name: '抖音', url: 'https://creator.douyin.com/creator-micro/home' },
    ...PLATFORM_METAS.map((m) => ({ code: m.code, name: m.name, url: m.entryUrl })),
  ]
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
