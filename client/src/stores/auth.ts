/** 登录态：token + 用户/团队信息 */
import { defineStore } from 'pinia'
import { authApi } from '@/api/modules'
import type { Team, User } from '@/types'

// 前期免登录：无 token 时用内置演示账号静默登录（并发去重）
let autoLoginPromise: Promise<void> | null = null

interface AuthState {
  token: string
  user: User | null
  team: Team | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    team: JSON.parse(localStorage.getItem('team') || 'null'),
  }),
  getters: {
    isLogged: (s) => !!s.token,
    role: (s) => s.user?.role || '',
    canReview: (s) => ['owner', 'admin', 'auditor'].includes(s.user?.role || ''),
    canManage: (s) => ['owner', 'admin'].includes(s.user?.role || ''),
  },
  actions: {
    /** 前期免登录：自动登录演示账号，成功返回 true */
    async autoLogin(): Promise<boolean> {
      if (this.token) return true
      if (!autoLoginPromise) {
        const account = import.meta.env.VITE_DEMO_ACCOUNT || '13800000001'
        const password = import.meta.env.VITE_DEMO_PASSWORD || 'demo123456'
        autoLoginPromise = (async () => {
          const res = await authApi.login(account, password)
          this.saveTokens(res.access_token, res.refresh_token)
          await this.fetchMe()
        })().finally(() => {
          autoLoginPromise = null
        })
      }
      try {
        await autoLoginPromise
        return true
      } catch {
        return false
      }
    },
    saveTokens(access: string, refresh: string) {
      this.token = access
      localStorage.setItem('token', access)
      localStorage.setItem('refresh_token', refresh)
    },
    async fetchMe() {
      const data = await authApi.me()
      this.user = data.user
      this.team = data.team
      localStorage.setItem('user', JSON.stringify(data.user))
      localStorage.setItem('team', JSON.stringify(data.team))
    },
    async logout() {
      try {
        await authApi.logout()
      } catch {
        /* 忽略登出接口异常 */
      }
      this.token = ''
      this.user = null
      this.team = null
      localStorage.removeItem('token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      localStorage.removeItem('team')
    },
  },
})
