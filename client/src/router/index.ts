import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Electron 使用 hash 路由（生产环境 loadFile 加载）
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/login/LoginView.vue'), meta: { title: '登录' } },
    {
      path: '/',
      component: () => import('@/layouts/AdminLayout.vue'),
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', name: 'dashboard', component: () => import('@/views/dashboard/DashboardView.vue'), meta: { title: '工作台' } },
        { path: 'accounts', name: 'accounts', component: () => import('@/views/accounts/AccountsView.vue'), meta: { title: '账号管理' } },
        { path: 'contents', name: 'contents', component: () => import('@/views/contents/ContentsView.vue'), meta: { title: '内容中心' } },
        { path: 'publish', name: 'publish', component: () => import('@/views/publish/PublishView.vue'), meta: { title: '一键分发' } },
        { path: 'messages', name: 'messages', component: () => import('@/views/messages/MessagesView.vue'), meta: { title: '私信评论' } },
        { path: 'stats', name: 'stats', component: () => import('@/views/stats/StatsView.vue'), meta: { title: '数据统计' } },
        { path: 'browser', name: 'browser', component: () => import('@/views/browser/BrowserView.vue'), meta: { title: '账号浏览器' } },
        { path: 'ai', name: 'ai', component: () => import('@/views/ai/AiView.vue'), meta: { title: 'AI 创作' } },
        { path: 'billing', name: 'billing', component: () => import('@/views/billing/BillingView.vue'), meta: { title: '订阅与账单' } },
        { path: 'team', name: 'team', component: () => import('@/views/team/TeamView.vue'), meta: { title: '团队管理' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // 前期免登录：无 token 时自动登录演示账号直接进业务页，失败（server 未启动等）才落到登录页
  if (to.path !== '/login' && !auth.isLogged) {
    if (!(await auth.autoLogin())) return '/login'
  }
  if (to.path === '/login' && auth.isLogged) return '/dashboard'
  document.title = `${to.meta.title ?? ''} - 社媒矩阵运营平台`
})

export default router
