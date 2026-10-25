import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import electron from 'electron'

// ESM 下 electron 模块需默认导入再解构；无 __dirname，用 import.meta 推导
const { app, BrowserWindow, shell } = electron
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

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

void app.whenReady().then(createWindow)
