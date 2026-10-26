/** RPA 截图归档上传：multipart 到 server /publish/rpa/screenshot，返回可访问 URL
 *  发布截图由引擎回报时携带；探测截图由 rpa:probe 调用方注入凭证归档 */
import { readFile } from 'node:fs/promises'

export interface ServerCreds {
  baseUrl: string
  token: string
}

export async function uploadScreenshot(
  creds: ServerCreds,
  filePath: string,
  kind: 'publish' | 'probe',
  itemId?: number,
): Promise<string> {
  const fd = new FormData()
  fd.set('file', new Blob([await readFile(filePath)], { type: 'image/png' }), 'shot.png')
  fd.set('kind', kind)
  if (itemId != null) fd.set('item_id', String(itemId))
  const res = await fetch(`${creds.baseUrl}/publish/rpa/screenshot`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${creds.token}` },
    body: fd,
    signal: AbortSignal.timeout(20_000),
  })
  if (res.status === 401) throw new Error('token 失效')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const json = (await res.json()) as { code: number; data: { url: string } }
  if (json.code !== 0) throw new Error(`业务错误 code=${json.code}`)
  return json.data.url
}
