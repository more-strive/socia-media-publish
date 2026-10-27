/** axios 实例：token 注入、业务码统一处理、401 静默刷新 */
import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE as string) || '/api/v1',
  timeout: 30000,
})

let refreshing: Promise<string | null> | null = null

async function doRefresh(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null
  try {
    const { data } = await axios.post(
      `${http.defaults.baseURL}/auth/refresh`,
      { refresh_token: refreshToken },
      { timeout: 10000 },
    )
    if (data.code === 0 && data.data?.access_token) {
      localStorage.setItem('token', data.data.access_token)
      localStorage.setItem('refresh_token', data.data.refresh_token)
      return data.data.access_token as string
    }
    return null
  } catch {
    return null
  }
}

/** 强制登出：localStorage 与 pinia store 一起清——只清前者时守卫看 store.token 仍 isLogged，
 *  跳 /login 会被弹回 /dashboard，表现为"点了没反应"的僵尸登录态（动态引入避免 http↔store 循环依赖） */
async function forceLogout(): Promise<void> {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user')
  localStorage.removeItem('team')
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const auth = useAuthStore()
    auth.token = ''
    auth.user = null
    auth.team = null
  } catch {
    /* pinia 未就绪（极早期请求）则只清 localStorage */
  }
  if (!location.hash.includes('/login')) {
    location.hash = '#/login'
    ElMessage.error('登录已过期，请重新登录')
  }
}

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/** 401 统一处理：刷新 token 重试一次，仍失败则强制登出。
 *  注意必须在 fulfilled 拦截器里就地调用——promise.then(f, r) 中 f 抛出的错不会进同一个 use() 的 r，
 *  旧实现把 code:401 reject 出去指望"下方错误处理"接住，实际直接漏成调用方 uncaught（点了没反应的根源） */
async function handleUnauthorized(
  config: (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined,
): Promise<unknown> {
  if (config && !config._retried) {
    config._retried = true
    refreshing = refreshing ?? doRefresh().finally(() => (refreshing = null))
    const token = await refreshing
    if (token) {
      config.headers = { ...config.headers, Authorization: `Bearer ${token}` } as typeof config.headers
      return http.request(config)
    }  }
  // 无 refresh token / 刷新失败 / 重试后仍 401：强制登出让用户重新登录
  await forceLogout()
  throw new AxiosError('unauthorized', '401', config)
}

http.interceptors.response.use(
  (resp) => {
    // 文件下载等二进制响应直接透出
    if (resp.config.responseType === 'blob') return resp
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 401) return handleUnauthorized(resp.config)
      if (body.code !== 0) {
        ElMessage.error(body.message || '请求失败')
        return Promise.reject(body)
      }
    }
    return body
  },
  async (error: AxiosError) => {
    const config = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    // 真实 HTTP 401（未经过包装层）同样走统一处理
    if (error.response?.status === 401) return handleUnauthorized(config)
    ElMessage.error(error.message === 'Network Error' ? '网络错误，请检查服务是否启动' : `请求异常：${error.message}`)
    return Promise.reject(error)
  },
)

/** 泛型快捷方法：直接拿到 data */
export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const resp = await http.get<never, { data: T }>(url, { params })
  return resp.data
}

export async function post<T = unknown>(url: string, body?: unknown): Promise<T> {
  const resp = await http.post<never, { data: T }>(url, body)
  return resp.data
}

export async function put<T = unknown>(url: string, body?: unknown): Promise<T> {
  const resp = await http.put<never, { data: T }>(url, body)
  return resp.data
}

export async function del<T = unknown>(url: string): Promise<T> {
  const resp = await http.delete<never, { data: T }>(url)
  return resp.data
}

export async function download(url: string, params?: Record<string, unknown>, filename = 'export.csv'): Promise<void> {
  const resp = await http.get(url, { params, responseType: 'blob' })
  const blobUrl = URL.createObjectURL(resp.data as Blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  a.click()
  URL.revokeObjectURL(blobUrl)
}

export default http
