/** 与 server Pydantic schema 对应的类型定义 */

export interface ApiResp<T = unknown> {
  code: number
  message: string
  data: T
}

export interface PageData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface User {
  id: number
  team_id: number
  nickname: string
  avatar: string | null
  phone: string | null
  email: string | null
  role: 'owner' | 'admin' | 'operator' | 'auditor'
  status: string
  last_login_at: string | null
}

export interface Team {
  id: number
  name: string
  plan_id: number | null
  plan_expire_at: string | null
  seats_total: number
  seats_used?: number
  credits: number
  audit_enabled: boolean
  webhook_url: string | null
}

export interface AccountGroup {
  id: number
  name: string
  sort: number
}

export interface SocialAccount {
  id: number
  platform: string
  platform_account_id: string | null
  nickname: string
  avatar: string | null
  fans_count: number
  auth_status: 'valid' | 'expired' | 'invalid'
  group_id: number | null
  group_name: string | null
  operator_id: number | null
  proxy_id: number | null
  channel: string
  region: string | null
  last_active_at: string | null
  note: string | null
}

export interface ProxyIP {
  id: number
  name: string
  scheme: string
  host: string
  port: number
  region: string | null
  status: 'unknown' | 'ok' | 'broken'
  last_check_at: string | null
}

export interface Content {
  id: number
  type: 'video' | 'article' | 'images'
  title: string
  summary: string | null
  body: string | null
  media: string[] | null
  cover: string | null
  tags: string[] | null
  status: 'draft' | 'reviewing' | 'approved' | 'rejected'
  review_note: string | null
  creator_id: number
  created_at: string
}

export interface PublishItem {
  id: number
  account_id: number
  status: 'pending' | 'publishing' | 'success' | 'failed'
  platform_publish_id: string | null
  publish_url: string | null
  fail_reason: string | null
  published_at: string | null
}

export interface PublishTask {
  id: number
  content_id: number
  content_title: string | null
  mode: 'immediate' | 'scheduled'
  scheduled_at: string | null
  status: 'reviewing' | 'scheduled' | 'queued' | 'publishing' | 'published' | 'partial' | 'failed' | 'canceled'
  creator_id: number
  reviewer_id: number | null
  review_note: string | null
  item_count: number
  success_count: number
  failed_count: number
  created_at: string
  items: PublishItem[]
}

export interface Message {
  id: number
  account_id: number
  msg_type: 'comment' | 'dm'
  direction: 'inbound' | 'outbound'
  parent_id: number | null
  reply_to_id: number | null
  content: string
  from_name: string | null
  from_avatar: string | null
  is_read: boolean
  auto_reply: boolean
  created_at: string
}

export interface ReplyRule {
  id: number
  rule_type: 'keyword' | 'welcome' | 'follow'
  keywords: string[] | null
  content: string
  status: boolean
}

export interface Script {
  id: number
  group_name: string
  title: string
  content: string
  owner_id: number | null
}

export interface StatPoint {
  date: string
  views: number
  likes: number
  comments: number
  shares: number
  new_followers: number
}

export interface AccountStat {
  account_id: number
  nickname: string
  platform: string
  followers: number
  series: StatPoint[]
}

export interface Summary {
  date: string
  account_count: number
  total_followers: number
  new_followers: number
  views: number
  likes: number
  comments: number
  shares: number
  published_count: number
}

export interface AITask {
  id: number
  task_type: 'copy' | 'video' | 'digital_human' | 'voice_clone'
  provider: string
  prompt: string
  params: Record<string, unknown> | null
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  result: Record<string, unknown> | null
  error: string | null
  credits_cost: number
  created_at: string
}

export interface Plan {
  id: number
  code: string
  name: string
  seats: number
  accounts: number
  credits_monthly: number
  price_monthly: number
  price_yearly: number
  features: string[] | null
}

export interface Order {
  id: number
  order_no: string
  type: 'new' | 'renew' | 'upgrade' | 'seats' | 'credits'
  plan_id: number | null
  quantity: number
  amount: number
  status: 'unpaid' | 'paid' | 'canceled' | 'refunded'
  paid_at: string | null
  created_at: string
}

export interface Invoice {
  id: number
  order_id: number
  title: string
  tax_no: string | null
  type: string
  amount: number
  status: string
  file_url: string | null
  created_at: string
}

export interface AuditLog {
  id: number
  user_id: number
  action: string
  detail: Record<string, unknown> | null
  created_at: string
}

export const PLATFORM_LABELS: Record<string, string> = {
  douyin: '抖音',
  shipinhao: '视频号',
  xhs: '小红书',
  kuaishou: '快手',
  bilibili: 'B 站',
  weibo: '微博',
  wechat_gzh: '公众号',
  toutiao: '头条',
  tiktok: 'TikTok',
  youtube: 'YouTube',
}

export const ROLE_LABELS: Record<string, string> = {
  owner: '创建者',
  admin: '管理员',
  operator: '运营',
  auditor: '审核员',
}

/** RPA 认领返回的待执行条目（server /publish/rpa/claim） */
export interface RpaClaimItem {
  item_id: number
  task_id: number
  account: { id: number; platform: string; nickname: string; note: string | null }
  content: {
    id: number
    type: string
    title: string
    summary: string | null
    media: string[] | null
    tags: string[] | null
  }
  extras: Record<string, unknown> | null
}
