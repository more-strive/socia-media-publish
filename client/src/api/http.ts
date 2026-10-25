/** axios 实例：token 注入、业务码统一处理、401 静默刷新 */
import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
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

function forceLogout(): void {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
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

http.interceptors.response.use(
  (resp) => {
    // 文件下载等二进制响应直接透出
    if (resp.config.responseType === 'blob') return resp
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 401) {
        // 交给下方错误处理统一刷新
        return Promise.reject(new AxiosError('unauthorized', '401', resp.config, resp, resp))
      }
      if (body.code !== 0) {
        ElMessage.error(body.message || '请求失败')
        return Promise.reject(body)
      }
    }
    return body
  },
  async (error: AxiosError) => {
    const config = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined
    const unauthorized = error.response?.status === 401 || error.message === 'unauthorized'
    if (unauthorized && config && !config._retried) {
      config._retried = true
      refreshing = refreshing ?? doRefresh().finally(() => (refreshing = null))
      const token = await refreshing
      if (token) {
        config.headers = { ...config.headers, Authorization: `Bearer ${token}` }
        return http.request(config)
      }
      forceLogout()
      return Promise.reject(error)
    }
    if (error.response?.status === 401) forceLogout()
    else ElMessage.error(error.message === 'Network Error' ? '网络错误，请检查服务是否启动' : `请求异常：${error.message}`)
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
