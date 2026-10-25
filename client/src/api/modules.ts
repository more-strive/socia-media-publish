/** 全部后端接口封装（与 server/app/api/v1 一一对应） */
import { del, download, get, post, put } from './http'
import type {
  AccountGroup,
  AccountStat,
  AITask,
  AuditLog,
  Content,
  Invoice,
  Message,
  Order,
  PageData,
  Plan,
  ProxyIP,
  PublishTask,
  ReplyRule,
  Script,
  SocialAccount,
  Summary,
  Team,
  User,
} from '@/types'

// ---- 认证 ----
export const authApi = {
  register: (body: { phone?: string; email?: string; password: string; nickname: string; team_name: string }) =>
    post<{ access_token: string; refresh_token: string }>('/auth/register', body),
  login: (account: string, password: string) =>
    post<{ access_token: string; refresh_token: string }>('/auth/login', { account, password }),
  smsSend: (phone: string) => post<{ code?: string; expire_seconds: number }>('/auth/sms/send', { phone }),
  smsLogin: (phone: string, code: string) =>
    post<{ access_token: string; refresh_token: string }>('/auth/sms/login', { phone, code }),
  logout: () => post('/auth/logout'),
  me: () => get<{ user: User; team: Team }>('/auth/me'),
}

// ---- 团队 / 成员 ----
export const teamApi = {
  get: () => get<Team & { seats_used: number }>('/teams/me'),
  update: (body: Partial<Pick<Team, 'name' | 'audit_enabled' | 'webhook_url'>>) => put<Team>('/teams/me', body),
  invite: () => post<{ invite_code: string; expire_seconds: number }>('/teams/invite'),
  join: (invite_code: string) => post('/teams/join', { invite_code }),
  logs: (page = 1, page_size = 20) => get<PageData<AuditLog>>('/teams/logs', { page, page_size }),
}

export const userApi = {
  list: (page = 1, page_size = 100) => get<PageData<User>>('/users', { page, page_size }),
  me: () => get<User>('/users/me'),
  updateMe: (body: { nickname?: string; avatar?: string; password?: string }) => put<User>('/users/me', body),
  updateRole: (id: number, role: string) => put(`/users/${id}/role`, { role }),
  remove: (id: number) => del(`/users/${id}`),
}

// ---- 账号托管 ----
export const accountApi = {
  list: (params: Record<string, unknown>) => get<PageData<SocialAccount>>('/accounts', params),
  create: (body: Record<string, unknown>) => post<SocialAccount>('/accounts', body),
  update: (id: number, body: Record<string, unknown>) => put<SocialAccount>(`/accounts/${id}`, body),
  remove: (id: number) => del(`/accounts/${id}`),
  batchCheck: () => post<{ total: number; expired: number }>('/accounts/batch-check'),
  reAuth: (id: number) => post(`/accounts/${id}/re-auth`),
  groups: () => get<AccountGroup[]>('/accounts/groups'),
  createGroup: (body: { name: string; sort?: number }) => post<AccountGroup>('/accounts/groups', body),
  updateGroup: (id: number, body: { name: string; sort?: number }) => put<AccountGroup>(`/accounts/groups/${id}`, body),
  removeGroup: (id: number) => del(`/accounts/groups/${id}`),
}

export const proxyApi = {
  list: (params: Record<string, unknown>) => get<PageData<ProxyIP>>('/proxies', params),
  create: (body: Record<string, unknown>) => post<ProxyIP>('/proxies', body),
  update: (id: number, body: Record<string, unknown>) => put<ProxyIP>(`/proxies/${id}`, body),
  remove: (id: number) => del(`/proxies/${id}`),
  check: (id: number) => post<ProxyIP>(`/proxies/${id}/check`),
}

// ---- 内容 ----
export const contentApi = {
  list: (params: Record<string, unknown>) => get<PageData<Content>>('/contents', params),
  get: (id: number) => get<Content>(`/contents/${id}`),
  create: (body: Record<string, unknown>) => post<Content>('/contents', body),
  update: (id: number, body: Record<string, unknown>) => put<Content>(`/contents/${id}`, body),
  remove: (id: number) => del(`/contents/${id}`),
  submit: (id: number) => post(`/contents/${id}/submit`),
  review: (id: number, approve: boolean, note?: string) => post(`/contents/${id}/review`, { approve, note }),
  aiGenerate: (topic: string, platform: string, tone?: string) =>
    post<{ content: string; topic: string; platform: string }>('/contents/ai-generate', { topic, platform, tone }),
  importDocx: (files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return post<{ imported: number; titles: string[] }>('/contents/import-docx', form)
  },
}

// ---- 一键分发 ----
export const publishApi = {
  create: (body: Record<string, unknown>) => post<PublishTask>('/publish/tasks', body),
  list: (params: Record<string, unknown>) => get<PageData<PublishTask>>('/publish/tasks', params),
  get: (id: number) => get<PublishTask>(`/publish/tasks/${id}`),
  cancel: (id: number) => post(`/publish/tasks/${id}/cancel`),
  review: (id: number, approve: boolean, note?: string) => post(`/publish/tasks/${id}/review`, { approve, note }),
  reviews: (page = 1, page_size = 20) => get<PageData<PublishTask>>('/publish/reviews', { page, page_size }),
  calendar: (start: string, end: string) =>
    get<{ date: string; task_count: number; account_count: number; tasks: PublishTask[] }[]>('/publish/calendar', { start, end }),
}

// ---- 私信评论 ----
export const messageApi = {
  list: (params: Record<string, unknown>) => get<PageData<Message>>('/messages', params),
  unreadCount: () => get<{ comment: number; dm: number }>('/messages/unread-count'),
  reply: (id: number, content: string) => post<Message>(`/messages/${id}/reply`, { content }),
  markRead: (ids: number[]) => post('/messages/read', { ids }),
  mockInbound: (body: Record<string, unknown>) => post<Message>('/messages/mock/inbound', body),
  rules: () => get<ReplyRule[]>('/messages/reply-rules'),
  createRule: (body: Record<string, unknown>) => post<ReplyRule>('/messages/reply-rules', body),
  updateRule: (id: number, body: Record<string, unknown>) => put<ReplyRule>(`/messages/reply-rules/${id}`, body),
  removeRule: (id: number) => del(`/messages/reply-rules/${id}`),
  scripts: () => get<Script[]>('/messages/scripts'),
  createScript: (body: Record<string, unknown>) => post<Script>('/messages/scripts', body),
  updateScript: (id: number, body: Record<string, unknown>) => put<Script>(`/messages/scripts/${id}`, body),
  removeScript: (id: number) => del(`/messages/scripts/${id}`),
}

// ---- 数据统计 ----
export const statsApi = {
  accounts: (params: Record<string, unknown>) => get<AccountStat[]>('/stats/accounts', params),
  contents: (params: Record<string, unknown>) =>
    get<
      {
        content_id: number
        title: string
        account_id: number
        platform: string | null
        views: number
        likes: number
        comments: number
        shares: number
        publish_url: string | null
        published_at: string | null
      }[]
    >('/stats/contents', params),
  summary: (day?: string) => get<Summary>('/stats/summary', { day }),
  export: (start: string, end: string) => download('/stats/export', { start, end }, `stats_${start}_${end}.csv`),
  push: (day?: string) => post<{ pushed: boolean; text: string }>('/stats/push-summary', { day }),
}

// ---- AI 创作 ----
export const aiApi = {
  credits: () => get<{ credits: number }>('/ai/credits'),
  create: (body: { task_type: string; prompt: string; params?: Record<string, unknown> }) => post<AITask>('/ai/tasks', body),
  list: (params: Record<string, unknown>) => get<PageData<AITask>>('/ai/tasks', params),
  get: (id: number) => get<AITask>(`/ai/tasks/${id}`),
}

// ---- 商业化 ----
export const billingApi = {
  plans: () => get<Plan[]>('/billing/plans'),
  subscription: () =>
    get<{ plan: Plan | null; plan_expire_at: string | null; seats_total: number; seats_used: number; credits: number }>(
      '/billing/subscription',
    ),
  createOrder: (body: { type: string; plan_id?: number; quantity?: number }) => post<Order>('/billing/orders', body),
  mockPay: (id: number) => post<Order>(`/billing/orders/${id}/mock-pay`),
  orders: (page = 1, page_size = 20) => get<PageData<Order>>('/billing/orders', { page, page_size }),
  createInvoice: (body: Record<string, unknown>) => post<Invoice>('/billing/invoices', body),
  invoices: (page = 1, page_size = 20) => get<PageData<Invoice>>('/billing/invoices', { page, page_size }),
}
