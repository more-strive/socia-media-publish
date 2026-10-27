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
  /** 静默执行中的标签（RPA 自动发布），点击可切换查看 */
  background: boolean
}

export interface TabsState {
  tabs: TabInfo[]
  activeId: number | null
}

interface Tab extends TabInfo {
  view: InstanceType<typeof WebContentsView>
  /** 静默标签：挂在主渲染层之下被控制台 UI 覆盖（页面正常渲染/截图），不激活不抢焦点 */
  background: boolean
  /** 隐藏标签：在 background 基础上连标签条也不出现（探测等短命自动流程） */
  hidden: boolean
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
    tabs: [...tabs.values()]
      .filter((t) => !t.hidden)
      .map(({ id, title, url, loading, canBack, canFwd, background }) => ({
        id,
        title,
        url,
        loading,
        canBack,
        canFwd,
        background,
      })),
    activeId,
  }
}

function emit(): void {
  mainWindow?.webContents.send('tabs:changed', state())
}

/** 层级装配（自底向上）：静默标签 → 主渲染层（控制台 UI，盖住静默标签）→ 激活的平台标签
 *  静默标签保持全尺寸挂载（覆盖态）——页面照常渲染，capturePage 截图与页面行为不受影响 */
function syncAttached(): void {
  if (!mainWindow || mainWindow.isDestroyed()) return
  const cv = mainWindow.contentView
  for (const t of tabs.values()) cv.removeChildView(t.view)
  const [cw, ch] = mainWindow.getContentSize()
  // 主渲染层 = contentView 中承载窗口 webContents 的那个 view；静默标签要垫在它之下
  let mainView: electron.WebContentsView | undefined
  for (const v of cv.children) {
    const wv = v as electron.WebContentsView
    if (wv.webContents && wv.webContents === mainWindow.webContents) {
      mainView = wv
      break
    }
  }
  const bgTabs = [...tabs.values()].filter((t) => t.background && t.id !== activeId)
  if (mainView) {
    for (const t of bgTabs) {
      cv.addChildView(t.view)
      t.view.setBounds({ x: 0, y: 0, width: cw || 1280, height: ch || 800 })
    }
    // 主渲染层移除后重挂即置顶，控制台 UI 覆盖住静默标签
    cv.removeChildView(mainView)
    cv.addChildView(mainView)
  } else {
    // 兜底：识别不到主渲染层时把静默标签挂到可视区外，避免盖住控制台
    for (const t of bgTabs) {
      cv.addChildView(t.view)
      t.view.setBounds({ x: -2000, y: 0, width: cw || 1280, height: ch || 800 })
    }
  }
  const active = activeId != null ? tabs.get(activeId) : undefined
  if (active) {
    cv.addChildView(active.view)
    active.view.setBounds(bounds)
  }
}

export function initTabs(win: electron.BrowserWindow): void {
  mainWindow = win
  // 窗口尺寸变化时静默标签同步重设 bounds（渲染层只在平台页上报 rect，控制台下不会触发）
  win.on('resize', () => syncAttached())
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

export function openTab(opts: {
  url: string
  partition?: string
  title?: string
  proxy?: ProxyConfig
  /** 静默标签：不激活不抢焦点，藏在控制台 UI 之下执行（RPA 自动发布用） */
  background?: boolean
  /** 隐藏标签：连标签条也不出现（探测等短命自动流程），隐含 background */
  hidden?: boolean
}): number {
  const view = new WebContentsView({
    // backgroundThrottling 关闭：被覆盖的静默标签不被降频，页面定时器/上传进度正常走
    webPreferences: {
      partition: opts.partition,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
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
    background: !!opts.background || !!opts.hidden,
    hidden: !!opts.hidden,
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
  // 静默标签不改变当前激活态（用户停留在原页面，自动化在底层执行）
  if (!tab.background) activeId = id
  syncAttached()
  emit()
  return id
}

/** 激活标签；null = 回到控制台标签（隐藏标签不可激活——不在标签条，无 UI 入口） */
export function activateTab(id: number | null): void {
  if (id !== null) {
    const t = tabs.get(id)
    if (!t || t.hidden) return
  }
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
