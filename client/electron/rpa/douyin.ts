/** 抖音创作者平台 RPA：每账号独立 session（扫码登录一次，cookie 持久化），自动上传视频发布
 *  第三方页面一律在应用内标签页打开（electron/tabs.ts），不弹独立窗口
 *  通用部分（等待/截图/文本注入/CDP 文件注入）已抽至 util.ts，与 generic 适配器共用 */
import electron from 'electron'

import { closeTab, openTab, tabWebContents } from '../tabs'
import type { ProxyConfig } from '../proxy'
import { cdpSetFiles, clickByTextExpr, fillText, shot, sleep, waitFor, withTopics } from './util'

const { session } = electron

const CREATOR_HOME = 'https://creator.douyin.com/creator-micro/home'
const UPLOAD_URL = 'https://creator.douyin.com/creator-micro/content/upload'
const LOGIN_TIMEOUT_MS = 15 * 60_000

const partitionOf = (accountId: number): string => `persist:douyin-${accountId}`

async function hasLoginCookie(accountId: number): Promise<boolean> {
  const ses = session.fromPartition(partitionOf(accountId))
  const cookies = await ses.cookies.get({ domain: '.douyin.com' })
  return cookies.some((c) => c.name === 'sessionid' || c.name === 'sessionid_ss')
}

/** 在应用内标签页打开抖音，等待用户扫码；检测到登录 cookie 即成功并关闭标签，尽力带回昵称 */
export async function loginDouyin(
  accountId: number,
  proxy?: ProxyConfig,
): Promise<{ ok: boolean; message: string; nickname?: string }> {
  if (await hasLoginCookie(accountId)) return { ok: true, message: '已有登录态，无需扫码' }
  const tabId = openTab({ url: CREATOR_HOME, partition: partitionOf(accountId), title: '抖音扫码登录', proxy })

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

export interface DouyinPublishIn {
  accountId: number
  itemId: number
  title: string
  /** 话题标签：抖音规则为 "#话题 " 追加在标题后（超 5 个截断，蚁小二实证） */
  tags?: string[] | null
  videoPath: string
  /** 账号绑定代理：发布与登录保持同一出口（claim 由 server 下发） */
  proxy?: ProxyConfig
}

export interface DouyinPublishOut {
  ok: boolean
  message: string
  publishUrl?: string
  /** 各步骤截图本地路径（成功/失败均留档，供引擎上传归档） */
  screenshots: string[]
}

/** 自动上传发布：标签页打开创作者上传页 → CDP 注入视频文件 → 填标题（含话题）→ 点发布 → 等跳转
 * 成功自动关标签；失败保留标签供人工检查 */
export async function publishDouyinVideo(input: DouyinPublishIn): Promise<DouyinPublishOut> {
  const { accountId, itemId } = input
  if (!(await hasLoginCookie(accountId))) {
    return { ok: false, message: '抖音登录态缺失，请先扫码绑定', screenshots: [] }
  }

  const tabId = openTab({
    url: UPLOAD_URL,
    partition: partitionOf(accountId),
    title: `发布 #${itemId}`,
    proxy: input.proxy,
  })
  const wc = tabWebContents(tabId)
  if (!wc) return { ok: false, message: '标签页创建失败', screenshots: [] }

  const shots: string[] = []
  let result: DouyinPublishOut = { ok: false, message: '未知错误', screenshots: shots }
  try {
    if (!(await waitFor(wc, `document.querySelector('input[type=file]')`, 30_000))) {
      result = { ok: false, message: '上传页加载超时（未出现文件输入框）', screenshots: shots }
      return result
    }
    await shot(wc, `item${itemId}_1_loaded`, shots)

    // 渲染层无法给 input[type=file] 赋值，走 CDP DOM.setFileInputFiles
    const set = await cdpSetFiles(wc, 'input[type=file]', [input.videoPath])
    if (set !== 'ok') {
      result = { ok: false, message: `文件注入失败（${set}）`, screenshots: shots }
      return result
    }

    // 等上传转码完成：标题编辑器出现（大视频可能较久）
    if (!(await waitFor(wc, `document.querySelector('.editor-kit__container, [contenteditable=true], .ql-editor')`, 180_000))) {
      result = { ok: false, message: '等待上传/编辑器超时', screenshots: shots }
      return result
    }
    await shot(wc, `item${itemId}_2_uploaded`, shots)

    // 填标题（contenteditable，execCommand/insertText 兜底见 util.fillText）；话题按抖音规则追加
    const fill = await fillText(
      wc,
      '.editor-kit__container [contenteditable=true], [contenteditable=true], .ql-editor',
      withTopics(input.title, input.tags, 'hash-space'),
    )
    if (fill !== 'ok') {
      result = { ok: false, message: `标题编辑器异常：${fill}`, screenshots: shots }
      return result
    }

    // 找"发布"按钮并点击（蚁小二 baseStartPush 文案组：精确匹配，避免误点"存草稿"/"定时发布"）
    const clicked = await waitFor(
      wc,
      clickByTextExpr(['发布', '发表', '发布作品', '发 布', '立即投稿']),
      60_000,
    )
    if (!clicked) {
      result = { ok: false, message: '未找到可用的发布按钮', screenshots: shots }
      return result
    }
    await shot(wc, `item${itemId}_3_clicked`, shots)

    // 成功判定：离开上传页
    const done = await waitFor(wc, `!location.pathname.includes('/content/upload')`, 60_000)
    await shot(wc, `item${itemId}_4_${done ? 'done' : 'timeout'}`, shots)
    result = done
      ? { ok: true, message: '发布成功', publishUrl: wc.getURL(), screenshots: shots }
      : { ok: false, message: '点击发布后未跳转，请结合截图/标签页排查（可能有风控弹窗）', screenshots: shots }
    return result
  } finally {
    if (result.ok) closeTab(tabId)
  }
}

/** 登录态探测（M4）：cookie 预检 + 开创作者首页验证是否被跳登录页，截图本地留档（路径随结果返回供归档） */
export async function probeDouyinLogin(
  accountId: number,
  proxy?: ProxyConfig,
): Promise<{ ok: boolean; valid: boolean; message: string; screenshot?: string }> {
  if (!(await hasLoginCookie(accountId))) {
    return { ok: true, valid: false, message: '无登录 cookie（未绑定或登录态已清理）' }
  }
  const tabId = openTab({ url: CREATOR_HOME, partition: partitionOf(accountId), title: '检测登录态', proxy })
  try {
    await waitFor(tabWebContents(tabId) as electron.WebContents, `document.readyState === 'complete'`, 20_000, 1000)
    const wc = tabWebContents(tabId)
    if (!wc) return { ok: false, valid: false, message: '页面已关闭' }
    await sleep(3000)
    const url = wc.getURL()
    const shots: string[] = []
    await shot(wc, `probe-douyin-${accountId}`, shots)
    const redirected = ['passport.douyin.com', '/login', 'sso.douyin'].some((k) => url.includes(k))
    return redirected
      ? { ok: true, valid: false, message: '登录态已失效（被跳转到登录页）', screenshot: shots[0] }
      : { ok: true, valid: true, message: '登录态有效', screenshot: shots[0] }
  } finally {
    closeTab(tabId)
  }
}
