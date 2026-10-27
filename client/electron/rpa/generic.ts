/** 元数据驱动的通用平台适配器：登录（cookie 轮询）→ 探测（入口页重定向判定）→ 发布
 *  （CDP 文件注入 → 表单填写 → 发布按钮文案组 → 成功判定）。
 *  流程骨架对齐蚁小二 videoRun，平台差异全部由 registry.ts 元数据描述 */
import electron from 'electron'

import type { ProxyConfig } from '../proxy'
import { closeTab, openTab, tabWebContents } from '../tabs'
import type { LoginResult, PlatformAdapter, ProbeResult, PublishInput, PublishResult } from './platforms'
import type { PlatformMeta } from './registry'
import { cdpSetFiles, clickByTextExpr, fillText, shot, sleep, waitFor, withTopics } from './util'

const { session } = electron

const LOGIN_TIMEOUT_MS = 15 * 60_000

const partitionOf = (code: string, accountId: number): string => `persist:${code}-${accountId}`

async function hasLoginCookie(meta: PlatformMeta, accountId: number): Promise<boolean> {
  const ses = session.fromPartition(partitionOf(meta.code, accountId))
  const cookies = await ses.cookies.get({ domain: meta.loginCookie.domain })
  return cookies.some((c) => meta.loginCookie.names.includes(c.name))
}

/** 登录：开授权页等用户扫码/账密，轮询分区 cookie；命中后尽力抓昵称并关标签 */
async function login(meta: PlatformMeta, accountId: number, proxy?: ProxyConfig): Promise<LoginResult> {
  if (await hasLoginCookie(meta, accountId)) return { ok: true, message: '已有登录态，无需扫码' }
  const tabId = openTab({
    url: meta.authorizeUrl,
    partition: partitionOf(meta.code, accountId),
    title: `${meta.name} 扫码登录`,
    proxy,
  })

  const deadline = Date.now() + LOGIN_TIMEOUT_MS
  while (Date.now() < deadline) {
    await sleep(2000)
    const wc = tabWebContents(tabId)
    if (!wc) return { ok: false, message: '页面已关闭，未完成登录' } // 用户手动关了标签
    if (await hasLoginCookie(meta, accountId)) {
      let nickname: string | undefined
      try {
        const sel =
          meta.nicknameSelector ?? '[class*="nickname"],[class*="nickName"],[class*="userName"],.user-name'
        // eslint-disable-next-line no-await-in-loop
        const name = await wc.executeJavaScript(
          `(document.querySelector(${JSON.stringify(sel)})?.textContent || '').trim()`,
        )
        if (name) nickname = name.slice(0, 60)
      } catch {
        /* 尽力而为，失败不影响登录结果 */
      }
      closeTab(tabId)
      return { ok: true, message: '登录成功', nickname }
    }
  }
  closeTab(tabId)
  return { ok: false, message: '等待扫码超时（15 分钟）' }
}

/** 探测：cookie 预检 + 开落地页，URL 被重定向回登录页关键词 = 登录态失效（截图留档） */
async function probe(meta: PlatformMeta, accountId: number, proxy?: ProxyConfig): Promise<ProbeResult> {
  if (!(await hasLoginCookie(meta, accountId))) {
    return { ok: true, valid: false, message: '无登录 cookie（未绑定或登录态已清理）' }
  }
  const tabId = openTab({
    url: meta.entryUrl,
    partition: partitionOf(meta.code, accountId),
    title: `检测${meta.name}登录态`,
    proxy,
  })
  try {
    const wc = tabWebContents(tabId)
    if (!wc) return { ok: false, valid: false, message: '页面已关闭' }
    await waitFor(wc, `document.readyState === 'complete'`, 20_000, 1000)
    await sleep(3000)
    const url = wc.getURL()
    const shots: string[] = []
    await shot(wc, `probe-${meta.code}-${accountId}`, shots)
    const redirected = meta.loginRedirectKeywords.some((k) => url.includes(k))
    return redirected
      ? { ok: true, valid: false, message: '登录态已失效（被跳转到登录页）', screenshot: shots[0] }
      : { ok: true, valid: true, message: '登录态有效', screenshot: shots[0] }
  } finally {
    closeTab(tabId)
  }
}

/** 发布：发布页 → CDP 注入视频 → 等表单 → 填标题（含话题）→ 点发布 → 等 URL 离开/成功文案。
 *  成功自动关标签；失败保留标签供人工检查（与抖音适配器一致） */
async function publish(meta: PlatformMeta, input: PublishInput): Promise<PublishResult> {
  const { accountId, itemId, mediaPath } = input
  if (!(await hasLoginCookie(meta, accountId))) {
    return { ok: false, message: `${meta.name}登录态缺失，请先扫码绑定` }
  }
  const tabId = openTab({
    url: meta.publishVideoUrl,
    partition: partitionOf(meta.code, accountId),
    title: `发布 #${itemId}`,
    proxy: input.proxy,
  })
  const wc = tabWebContents(tabId)
  if (!wc) return { ok: false, message: '标签页创建失败' }

  const shots: string[] = []
  let ok = false
  let result: PublishResult = { ok: false, message: '未知错误' }
  try {
    if (!(await waitFor(wc, `document.querySelector(${JSON.stringify(meta.fileSelector)})`, 30_000))) {
      result = { ok: false, message: '发布页加载超时（未出现文件选择框）', screenshots: shots }
      return result
    }
    await shot(wc, `item${itemId}_1_loaded`, shots)

    // 渲染层无法给 input[type=file] 赋值，走 CDP DOM.setFileInputFiles
    const set = await cdpSetFiles(wc, meta.fileSelector, [mediaPath])
    if (set !== 'ok') {
      result = { ok: false, message: `文件注入失败（${set}）`, screenshots: shots }
      return result
    }

    // 等上传/转码完成：标题输入框出现（大视频可能较久）
    if (!(await waitFor(wc, `document.querySelector(${JSON.stringify(meta.titleSelector)})`, 180_000))) {
      result = { ok: false, message: '等待上传/表单超时', screenshots: shots }
      return result
    }
    await shot(wc, `item${itemId}_2_uploaded`, shots)

    const fill = await fillText(wc, meta.titleSelector, withTopics(input.title, input.tags, meta.topicStyle))
    if (fill !== 'ok') {
      result = { ok: false, message: `标题填写异常：${fill}`, screenshots: shots }
      return result
    }

    // 发布按钮：候选文案组轮询（精确匹配，避免误点"存草稿"/"定时发布"类按钮）
    if (!(await waitFor(wc, clickByTextExpr(meta.publishTexts), 60_000))) {
      result = { ok: false, message: '未找到可用的发布按钮', screenshots: shots }
      return result
    }
    await shot(wc, `item${itemId}_3_clicked`, shots)

    // 成功判定：离开发布页，或页面出现成功文案（部分平台发布后不跳转）
    const publishPath = new URL(meta.publishVideoUrl).pathname
    const successExpr =
      `!location.pathname.startsWith(${JSON.stringify(publishPath)}) || ` +
      `[${meta.successTexts.map((t) => JSON.stringify(t)).join(',')}].some((t) => document.body.innerText.includes(t))`
    const done = await waitFor(wc, successExpr, 90_000)
    await shot(wc, `item${itemId}_4_${done ? 'done' : 'timeout'}`, shots)
    ok = done
    result = done
      ? { ok: true, message: '发布成功', publishUrl: wc.getURL(), screenshots: shots }
      : { ok: false, message: '点击发布后未见成功（可能弹风控/校验），请结合截图/标签页排查', screenshots: shots }
    return result
  } finally {
    if (ok) closeTab(tabId)
  }
}

/** 由元数据构造适配器（platforms.ts 注册表批量接入用） */
export function makeAdapter(meta: PlatformMeta): PlatformAdapter {
  return {
    code: meta.code,
    login: (accountId, proxy) => login(meta, accountId, proxy),
    publish: (input) => publish(meta, input),
    probe: (accountId, proxy) => probe(meta, accountId, proxy),
  }
}
