import { PLATFORM_LABELS } from '@/types'

export function platformLabel(p: string): string {
  return PLATFORM_LABELS[p] ?? p
}

export function fmtNum(n: number | null | undefined): string {
  if (n == null) return '-'
  if (n >= 100000000) return `${(n / 100000000).toFixed(1)}亿`
  if (n >= 10000) return `${(n / 10000).toFixed(1)}w`
  return String(n)
}

export function fmtTime(s: string | null | undefined, withTime = true): string {
  if (!s) return '-'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const pad = (x: number) => String(x).padStart(2, '0')
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  if (!withTime) return date
  return `${date} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  switch (status) {
    case 'published':
    case 'success':
    case 'valid':
    case 'approved':
    case 'paid':
    case 'succeeded':
    case 'ok':
      return 'success'
    case 'publishing':
    case 'running':
    case 'scheduled':
    case 'reviewing':
    case 'pending':
    case 'unpaid':
      return 'warning'
    case 'failed':
    case 'expired':
    case 'invalid':
    case 'rejected':
    case 'broken':
      return 'danger'
    default:
      return 'info'
  }
}

export const STATUS_LABELS: Record<string, string> = {
  // 内容/任务/账号/订单等通用状态中文映射
  draft: '草稿',
  reviewing: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  scheduled: '已排期',
  queued: '已入队',
  publishing: '发布中',
  published: '已发布',
  partial: '部分成功',
  failed: '失败',
  canceled: '已取消',
  pending: '等待中',
  dispatched: 'RPA 执行中',
  success: '成功',
  valid: '有效',
  expired: '已失效',
  invalid: '异常',
  unpaid: '待支付',
  paid: '已支付',
  refunded: '已退款',
  running: '执行中',
  succeeded: '已完成',
  unknown: '未知',
  ok: '正常',
  broken: '不可达',
  immediate: '立即发布',
}
