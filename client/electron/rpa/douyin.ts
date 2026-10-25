/** 抖音创作者平台 RPA：每账号独立 session（扫码登录一次，cookie 持久化），自动上传视频发布
 * 第三方页面一律在应用内标签页打开（electron/tabs.ts），不弹独立窗口 */
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

import electron from 'electron'

import { closeTab, openTab, tabWebContents } from '../tabs'

const { app, session } = electron

const CREATOR_HOME = 'https://creator.douyin.com/creator-micro/home'
const UPLOAD_URL = 'https://creator.douyin.com/creator-micro/content/upload'
const LOGIN_TIMEOUT_MS = 15 * 60_000

const partitionOf = (accountId: number): string => `persist:douyin-${accountId}`

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function logDir(): Promise<string> {
  const dir = join(app.getPath('userData'), 'rpa-logs')
  await mkdir(dir, { recursive: true })
  return dir
}

async function hasLoginCookie(accountId: number): Promise<boolean> {
  const ses = session.fromPartition(partitionOf(accountId))
  const cookies = await ses.cookies.get({ domain: '.douyin.com' })
  return cookies.some((c) => c.name === 'sessionid' || c.name === 'sessionid_ss')
}

/** 在应用内标签页打开抖音，等待用户扫码；检测到登录 cookie 即成功并关闭标签，尽力带回昵称 */
export async function loginDouyin(accountId: number): Promise<{ ok: boolean; message: string; nickname?: string }> {
  if (await hasLoginCookie(accountId)) return { ok: true, message: '已有登录态，无需扫码' }
  const tabId = openTab({ url: CREATOR_HOME, partition: partitionOf(accountId), title: '抖音扫码登录' })

  const deadline = Date.now() + LOGIN_TIMEOUT_MS
  while (Date.now() < deadline) {
    await sleep(2000)
    const wc = tabWebContents(tabId)
    if (!wc) return { ok: false, message: '页面已关闭，未完成登录' } // 用户手动关了标签
    if (await hasLoginCookie(accountId)) {
      // 尽力读取账号昵称（选择器不确定，多候选取第一个非空；失败不影响登录结果）
      let nickname: string | undefined
      try {
        const name = await wc.executeJavaScript(`
          (document.querySelector('.user-info .name, .account-name, .nick-name, [class*="nickname"]')
            ?.textContent || '').trim()`)
        if (name) nickname = name.slice(0, 60)
      } catch {
        /* 尽力而为 */
      }
      closeTab(tabId)
      return { ok: true, message: '登录成功', nickname }
    }
  }
  closeTab(tabId)
  return { ok: false, message: '等待扫码超时（15 分钟）' }
}

/** 轮询页面 JS 表达式直到为 true；页面跳转中的异常忽略 */
async function waitFor(
  wc: electron.WebContents,
  expr: string,
  timeoutMs: number,
  everyMs = 1500,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      // eslint-disable-next-line no-await-in-loop
      if (await wc.executeJavaScript(`!!(${expr})`)) return true
    } catch {
      /* 页面跳转中 */
    }
    // eslint-disable-next-line no-await-in-loop
    await sleep(everyMs)
  }
  return false
}

/** 每个关键步骤截图到 userData/rpa-logs，便于排查选择器失配 */
async function shot(wc: electron.WebContents, name: string): Promise<void> {
  try {
    const img = await wc.capturePage()
    await writeFile(join(await logDir(), `${name}.png`), img.toPNG())
  } catch {
    /* 截图失败不影响流程 */
  }
}

export interface DouyinPublishIn {
  accountId: number
  itemId: number
  title: string
  videoPath: string
}

export interface DouyinPublishOut {
  ok: boolean
  message: string
  publishUrl?: string
}

/** 自动上传发布：标签页打开创作者上传页 → CDP 注入视频文件 → 填标题 → 点发布 → 等跳转
 * 成功自动关标签；失败保留标签供人工检查 */
export async function publishDouyinVideo(input: DouyinPublishIn): Promise<DouyinPublishOut> {
  const { accountId, itemId, title } = input
  if (!(await hasLoginCookie(accountId))) return { ok: false, message: '抖音登录态缺失，请先扫码绑定' }

  const tabId = openTab({ url: UPLOAD_URL, partition: partitionOf(accountId), title: `发布 #${itemId}` })
  const wc = tabWebContents(tabId)
  if (!wc) return { ok: false, message: '标签页创建失败' }

  let result: DouyinPublishOut = { ok: false, message: '未知错误' }
  try {
    if (!(await waitFor(wc, `document.querySelector('input[type=file]')`, 30_000))) {
      result = { ok: false, message: '上传页加载超时（未出现文件输入框）' }
      return result
    }
    await shot(wc, `item${itemId}_1_loaded`)

    // 渲染层无法给 input[type=file] 赋值，走 CDP DOM.setFileInputFiles
    const dbg = wc.debugger
    dbg.attach('1.1')
    try {
      const doc = await dbg.sendCommand('DOM.getDocument')
      const node = await dbg.sendCommand('DOM.querySelector', {
        nodeId: doc.root.nodeId,
        selector: 'input[type=file]',
      })
      if (!node.nodeId) {
        result = { ok: false, message: '上传页未找到文件输入框' }
        return result
      }
      await dbg.sendCommand('DOM.setFileInputFiles', { files: [input.videoPath], nodeId: node.nodeId })
    } finally {
      try {
        dbg.detach()
      } catch {
        /* 已断开 */
      }
    }

    // 等上传转码完成：标题编辑器出现（大视频可能较久）
    if (!(await waitFor(wc, `document.querySelector('.editor-kit__container, [contenteditable=true], .ql-editor')`, 180_000))) {
      result = { ok: false, message: '等待上传/编辑器超时' }
      return result
    }
    await shot(wc, `item${itemId}_2_uploaded`)

    // 填标题：抖音标题为 contenteditable，用 execCommand 触发输入事件（React 受控组件兼容）
    const fill = await wc.executeJavaScript(`
      (() => {
        const ed = document.querySelector(
          '.editor-kit__container [contenteditable=true], [contenteditable=true], .ql-editor')
        if (!ed) return 'no-editor'
        ed.focus()
        document.execCommand('selectAll', false, null)
        document.execCommand('insertText', false, ${JSON.stringify(title)})
        return 'ok'
      })()`)
    if (fill !== 'ok') {
      result = { ok: false, message: `标题编辑器异常：${fill}` }
      return result
    }

    // 找“发布”按钮（精确文案，避免误点“存草稿”/“定时发布”）并点击
    const clicked = await waitFor(
      wc,
      `(() => {
        const b = [...document.querySelectorAll('button')]
          .find((x) => x.textContent.trim() === '发布' && !x.disabled)
        if (!b) return false
        b.click()
        return true
      })()`,
      60_000,
    )
    if (!clicked) {
      result = { ok: false, message: '未找到可用的发布按钮' }
      return result
    }
    await shot(wc, `item${itemId}_3_clicked`)

    // 成功判定：离开上传页
    const done = await waitFor(wc, `!location.pathname.includes('/content/upload')`, 60_000)
    await shot(wc, `item${itemId}_4_${done ? 'done' : 'timeout'}`)
    result = done
      ? { ok: true, message: '发布成功', publishUrl: wc.getURL() }
      : { ok: false, message: '点击发布后未跳转，请结合截图/标签页排查（可能有风控弹窗）' }
    return result
  } finally {
    if (result.ok) closeTab(tabId)
  }
}
