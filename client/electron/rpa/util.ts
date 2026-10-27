/** RPA 共享工具：等待/截图/文本注入/按钮点击/CDP 文件注入（抽自抖音适配器，通用与平台专用适配器共用）
 *  注入策略对齐蚁小二：页面内原型 setter / execCommand 优先，主进程 insertText 兜底（绕过 React 受控组件） */
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

import electron from 'electron'

const { app } = electron

export const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms))

/** RPA 过程截图目录（userData/rpa-logs） */
export async function logDir(): Promise<string> {
  const dir = join(app.getPath('userData'), 'rpa-logs')
  await mkdir(dir, { recursive: true })
  return dir
}

/** 轮询页面 JS 表达式直到为 true；页面跳转中的异常忽略 */
export async function waitFor(
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

/** 每个关键步骤截图到 userData/rpa-logs，便于排查选择器失配；路径收集后随结果归档上传 */
export async function shot(wc: electron.WebContents, name: string, into: string[] = []): Promise<void> {
  try {
    const img = await wc.capturePage()
    const path = join(await logDir(), `${name}.png`)
    await writeFile(path, img.toPNG())
    into.push(path)
  } catch {
    /* 截图失败不影响流程 */
  }
}

/** 话题拼接（蚁小二 description 预处理规则）：抖音"#话题 "（超 5 个截断）、微博"#话题#"、其余平台剔除 */
export function withTopics(
  title: string,
  tags: string[] | null | undefined,
  style: 'hash-space' | 'hash-wrap' | 'strip',
): string {
  if (!tags?.length || style === 'strip') return title
  const list = style === 'hash-space' ? tags.slice(0, 5) : tags
  return `${title} ${list.map((t) => (style === 'hash-space' ? `#${t} ` : `#${t}#`)).join('')}`.trim()
}

/** 填文本：input/textarea 走原型 value setter + input/change 事件（React 受控组件兼容），
 * contenteditable 走 selectAll + execCommand insertText；页面路径失败回退主进程 insertText */
export async function fillText(
  wc: electron.WebContents,
  selector: string,
  text: string,
): Promise<'ok' | 'not-found' | 'fail'> {
  const r = await wc
    .executeJavaScript(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)})
      if (!el) return 'not-found'
      el.focus()
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        const proto = el.tagName === 'INPUT' ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype
        const set = Object.getOwnPropertyDescriptor(proto, 'value')?.set
        if (set) set.call(el, ${JSON.stringify(text)})
        else el.value = ${JSON.stringify(text)}
        el.dispatchEvent(new Event('input', { bubbles: true }))
        el.dispatchEvent(new Event('change', { bubbles: true }))
        return 'ok'
      }
      document.execCommand('selectAll', false, null)
      return document.execCommand('insertText', false, ${JSON.stringify(text)}) ? 'ok' : 'fallback'
    })()`)
    .catch(() => 'fail' as const)
  if (r === 'fallback') {
    try {
      await wc.insertText(text)
      return 'ok'
    } catch {
      return 'fail'
    }
  }
  return r
}

/** 生成"按文案找元素并点击"的页面表达式（配合 waitFor 轮询）：
 *  蚁小二 baseStartPush 同款策略：button/div/span 取叶子节点精确匹配候选文案，跳过禁用项 */
export function clickByTextExpr(texts: string[]): string {
  return `(() => {
    for (const t of ${JSON.stringify(texts)}) {
      const el = [...document.querySelectorAll('button,div,span')]
        .find((x) => x.childElementCount === 0 && x.textContent.trim() === t
          && !x.disabled && x.getAttribute('aria-disabled') !== 'true')
      if (el) { el.click(); return true }
    }
    return false
  })()`
}

/** CDP 给 input[type=file] 注入本地文件（渲染层无法直接赋值）；
 *  getDocument 用 depth:-1 + pierce 覆盖 shadow DOM（蚁小二同款参数） */
export async function cdpSetFiles(
  wc: electron.WebContents,
  selector: string,
  files: string[],
): Promise<'ok' | 'not-found' | 'fail'> {
  const dbg = wc.debugger
  try {
    dbg.attach('1.1')
  } catch {
    /* 已附加 */
  }
  try {
    const doc = await dbg.sendCommand('DOM.getDocument', { depth: -1, pierce: true })
    const node = await dbg.sendCommand('DOM.querySelector', {
      nodeId: doc.root.nodeId,
      selector,
    })
    if (!node.nodeId) return 'not-found'
    await dbg.sendCommand('DOM.setFileInputFiles', { files, nodeId: node.nodeId })
    return 'ok'
  } catch {
    return 'fail'
  } finally {
    try {
      dbg.detach()
    } catch {
      /* 已断开 */
    }
  }
}
