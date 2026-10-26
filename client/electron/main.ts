import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import electron from 'electron'
import { initEngine } from './engine'
import { adapterOf, rpaPlatforms } from './rpa/platforms'
import { activateTab, closeTab, initTabs, openTab, resetTabs, setTabBounds, tabsState } from './tabs'
// ESM 下 electron 模块需默认导入再解构；无 __dirname，用 import.meta 推导
const { app, BrowserWindow, ipcMain, shell } = electron
const appDir = fileURLToPath(new URL('.', import.meta.url))
process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = 'true'
let win: electron.BrowserWindow | null = null
function preloadPath(): string {
  // vite-plugin-electron 输出 .mjs；兼容历史 .js
  const mjs = join(appDir, 'preload.mjs')
  return existsSync(mjs) ? mjs : join(appDir, 'preload.js')
}
function createWindow(): void {
  win = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    autoHideMenuBar: true,
    title: '社媒矩阵运营平台',
    webPreferences: {
      preload: preloadPath(),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })
  win.on('ready-to-show', () => win?.show())
  initTabs(win)
  win.on('closed', resetTabs)
  // 开发诊断：渲染层 console 与异常转发到主进程日志
  // Electron 45 处于新旧事件参数过渡期，此处按旧签名取参（运行时实测有效）
  win.webContents.on('console-message', (_e, _level, message) => {
    if (message) console.log('[renderer]', message)
  })
  win.webContents.on('render-process-gone', (_e, details) => {
    console.error('[renderer] 进程崩溃:', details.reason)
  })
  win.webContents.on('did-fail-load', (_e, code, desc, url) => {
    console.error('[renderer] 加载失败:', code, desc, url)
  })
  // 外部链接交给系统浏览器打开
  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })
  if (process.env.VITE_DEV_SERVER_URL) {
    void win.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    void win.loadFile(join(appDir, '../dist/index.html'))
  }
}
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
// ---- RPA IPC（平台能力经适配器注册表分发，视图层不感知具体平台）----
ipcMain.handle('platforms:list', () => rpaPlatforms())
ipcMain.handle('rpa:login', (_e, platform: string, accountId: number) => {
  const adapter = adapterOf(platform)
  if (!adapter) return { ok: false, message: '平台 ' + platform + ' 暂不支持 RPA 绑定' }
  return adapter.login(accountId)
})

// ---- 应用内标签页 ----
ipcMain.handle('tabs:open', (_e, opts: { url: string; partition?: string; title?: string }) => openTab(opts))
ipcMain.handle('tabs:activate', (_e, id: number) => activateTab(id))
ipcMain.handle('tabs:close', (_e, id: number) => closeTab(id))
ipcMain.handle('tabs:rect', (_e, rect: { x: number; y: number; width: number; height: number } | null) => {
  setTabBounds(rect)
})
ipcMain.handle('tabs:state', () => tabsState())
// ---- RPA 引擎（主进程常驻认领-执行-回报，见 docs/client改造计划.md M0）----
initEngine()
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
void app.whenReady().then(createWindow)
