<template>
  <div class="h-full flex flex-col">
    <!-- 浏览器 Shell 顶栏（对标蚁小二桌面端：标签条 + 导航工具条） -->
    <div class="shell flex-shrink-0">
      <!-- 标签条：控制台是常驻首标签，平台页/RPA 自动化页都是同级标签 -->
      <div class="tabstrip flex items-end gap-1 px-2 pt-1.5">
        <div class="tab" :class="{ 'tab-active': activeId === null }" @click="activate(null)">
          <el-icon :size="13"><Monitor /></el-icon>
          <span>控制台</span>
        </div>
        <div
          v-for="t in tabs"
          :key="t.id"
          class="tab"
          :class="{ 'tab-active': t.id === activeId }"
          :title="t.url"
          @click="activate(t.id)"
        >
          <span v-if="t.loading" class="i-carbon:circle-dash w-3 h-3 flex-shrink-0 text-blue-5 animate-spin" />
          <!-- 静默执行中的 RPA 发布标签：机器人角标，点击可查看自动化过程 -->
          <span
            v-else-if="t.background"
            class="i-carbon:robot w-3 h-3 flex-shrink-0 text-green-5"
            title="RPA 静默执行中，点击查看"
          />
          <span class="truncate max-w-140px">{{ t.title }}</span>
          <el-icon class="tab-close" :size="12" @click.stop="close(t.id)"><Close /></el-icon>
        </div>
        <!-- 新标签：各平台创作者中心快捷入口 -->
        <el-dropdown trigger="click" @command="openQuick">
          <div class="tab tab-plus" title="新建标签页"><el-icon :size="13"><Plus /></el-icon></div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="q in links" :key="q.code" :command="q">
                {{ q.name }}创作者中心
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <!-- 导航工具条：后退/前进/刷新 + 地址栏 + 用户区 -->
      <div class="toolbar flex items-center gap-2 px-3">
        <el-button text :disabled="!activeTab || !activeTab.canBack" @click="nav('back')">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <el-button text :disabled="!activeTab || !activeTab.canFwd" @click="nav('forward')">
          <el-icon><ArrowRight /></el-icon>
        </el-button>
        <el-button text :disabled="!activeTab" @click="nav('reload')">
          <el-icon><RefreshRight /></el-icon>
        </el-button>
        <el-input
          v-model="address"
          class="flex-1"
          size="small"
          :disabled="!activeTab"
          :placeholder="activeTab ? '搜索或输入网址' : '控制台（矩阵运营中台）'"
          clearable
          @keyup.enter="onAddress"
        >
          <template #prefix><el-icon><Link /></el-icon></template>
        </el-input>
        <el-badge :value="unreadTotal" :hidden="unreadTotal === 0" :max="99">
          <el-icon :size="18" class="cursor-pointer" @click="router.push('/messages')">
            <ChatDotRound />
          </el-icon>
        </el-badge>
        <el-dropdown @command="onCommand">
          <span class="flex items-center gap-2 cursor-pointer">
            <el-avatar :size="28">{{ auth.user?.nickname?.slice(0, 1) }}</el-avatar>
            <span class="text-14px">{{ auth.user?.nickname }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="team">团队管理</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 内容区：控制台标签 = 侧边栏+页面；平台标签 = WebContentsView 覆盖层（host 上报区域） -->
    <div class="flex-1 min-h-0 relative">
      <div v-show="activeId === null" class="h-full">
        <el-container class="h-full">
          <!-- 侧边栏 -->
          <el-aside width="210px" class="aside">
            <div class="logo flex-center gap-2">
              <div class="i-carbon:analytics w-6 h-6 text-blue-5" />
              <span class="font-bold text-16px">矩阵运营平台</span>
            </div>
            <el-menu :default-active="route.path" router class="border-none! flex-1 overflow-y-auto">
              <el-menu-item v-for="m in topMenus" :key="m.path" :index="m.path">
                <el-icon><component :is="m.icon" /></el-icon>
                <span>{{ m.label }}</span>
              </el-menu-item>
              <el-menu-item-group v-for="g in menuGroups" :key="g.label" :title="g.label">
                <el-menu-item v-for="m in g.items" :key="m.path" :index="m.path">
                  <el-icon><component :is="m.icon" /></el-icon>
                  <span>{{ m.label }}</span>
                </el-menu-item>
              </el-menu-item-group>
            </el-menu>
          </el-aside>
          <el-main class="main">
            <router-view />
          </el-main>
        </el-container>
      </div>
      <!-- 平台标签宿主：仅用于向主进程上报覆盖区域坐标（WebContentsView 是原生层，输入由原生路由），
           自身必须穿透鼠标事件，否则控制台激活时会盖住菜单/页面点击 -->
      <div ref="host" class="absolute inset-0 pointer-events-none" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowRight,
  Calendar,
  ChatDotRound,
  Close,
  Coin,
  DataAnalysis,
  Link,
  MagicStick,
  Monitor,
  Plus,
  RefreshRight,
  User,
  Document,
  Setting,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { messageApi } from '@/api/modules'
import { useRpaEngine } from '@/composables/useRpaEngine'
import { useAuthStore } from '@/stores/auth'

interface TabItem {
  id: number
  title: string
  url: string
  loading: boolean
  canBack: boolean
  canFwd: boolean
  /** 静默执行中的 RPA 发布标签（藏在控制台 UI 之下渲染） */
  background: boolean
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const rpa = useRpaEngine()

const topMenus = [{ path: '/dashboard', label: '工作台', icon: Monitor }]
// 侧边栏按业务域分组（对标蚁小二信息架构：分发 / 账号 / 互动 / 数据 / 创作 / 管理）
const menuGroups = [
  {
    label: '内容分发',
    items: [
      { path: '/publish', label: '一键分发', icon: Calendar },
      { path: '/contents', label: '内容中心', icon: Document },
    ],
  },
  {
    label: '账号运营',
    items: [
      { path: '/accounts', label: '账号管理', icon: User },
    ],
  },
  { label: '互动', items: [{ path: '/messages', label: '私信评论', icon: ChatDotRound }] },
  { label: '数据', items: [{ path: '/stats', label: '数据统计', icon: DataAnalysis }] },
  { label: '创作', items: [{ path: '/ai', label: 'AI 创作', icon: MagicStick }] },
  {
    label: '管理',
    items: [
      { path: '/team', label: '团队管理', icon: Setting },
      { path: '/billing', label: '订阅与账单', icon: Coin },
    ],
  },
]

// ---- 平台标签（浏览器 Shell）：状态镜像 + 导航 ----
const host = ref<HTMLElement>()
const tabs = ref<TabItem[]>([])
const activeId = ref<number | null>(null)
const links = ref<{ code: string; name: string; url: string }[]>([])
const address = ref('')

const activeTab = computed(() => tabs.value.find((t) => t.id === activeId.value) ?? null)

watch(
  () => activeTab.value?.url,
  (u) => {
    address.value = u ?? ''
  },
)

function activate(id: number | null): void {
  void window.electronAPI?.tabs?.activate(id)
}

function close(id: number): void {
  void window.electronAPI?.tabs?.close(id)
}

function nav(action: 'back' | 'forward' | 'reload'): void {
  if (activeTab.value) void window.electronAPI?.tabs?.nav(activeTab.value.id, action)
}

function onAddress(): void {
  if (activeTab.value && address.value.trim()) {
    void window.electronAPI?.tabs?.navigate(activeTab.value.id, address.value.trim())
  }
}

function openQuick(q: { code: string; name: string; url: string }): void {
  void window.electronAPI?.tabs?.open({ url: q.url, title: `${q.name}创作者中心` })
}

/** 把平台标签覆盖区域（DIP=CSS px）上报主进程；控制台激活时传 null 隐藏全部平台标签 */
function sendRect(): void {
  const el = host.value
  const r = el?.getBoundingClientRect()
  const show = activeId.value !== null && !!r && r.width > 0
  void window.electronAPI?.tabs?.rect(
    show && r
      ? { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) }
      : null,
  )
}

let ro: ResizeObserver | undefined
let unsubscribe: (() => void) | undefined

onMounted(() => {
  if (!auth.user) void auth.fetchMe().catch(() => undefined)
  rpa.start() // RPA 引擎随布局启动（是否执行由开关控制）
  void window.electronAPI?.tabs?.state().then((s) => {
    tabs.value = s.tabs
    activeId.value = s.activeId
    requestAnimationFrame(sendRect)
  })
  void window.electronAPI?.tabs?.quickLinks().then((l) => {
    links.value = l
  })
  unsubscribe = window.electronAPI?.tabs?.onChanged((s) => {
    tabs.value = s.tabs
    activeId.value = s.activeId
    requestAnimationFrame(sendRect)
  })
  if (host.value) {
    ro = new ResizeObserver(() => sendRect())
    ro.observe(host.value)
  }
  window.addEventListener('resize', sendRect)
})

onUnmounted(() => {
  ro?.disconnect()
  window.removeEventListener('resize', sendRect)
  unsubscribe?.()
})

// ---- 顶栏用户区 ----
const unreadTotal = ref(0)

async function loadUnread(): Promise<void> {
  try {
    const data = await messageApi.unreadCount()
    unreadTotal.value = data.comment + data.dm
  } catch {
    /* 静默 */
  }
}

async function onCommand(cmd: string): Promise<void> {
  if (cmd === 'logout') {
    await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
    await auth.logout()
    ElMessage.success('已退出')
    router.push('/login')
  } else if (cmd === 'team') {
    activate(null)
    router.push('/team')
  }
}

void loadUnread()
</script>

<style scoped>
.shell {
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}
.tabstrip {
  min-height: 34px;
}
.tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  font-size: 13px;
  color: #606266;
  background: #eceef2;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
  max-width: 220px;
  user-select: none;
}
.tab-active {
  background: #fff;
  color: #409eff;
  border-color: #e4e7ed;
}
.tab-close {
  border-radius: 3px;
  color: #909399;
}
.tab-close:hover {
  color: #f56c6c;
  background: #fde2e2;
}
.tab-plus {
  padding: 5px 8px;
}
.toolbar {
  height: 42px;
  background: #fff;
}
.aside {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid #e4e7ed;
}
.logo {
  height: 48px;
  flex-shrink: 0;
}
.main {
  overflow-y: auto;
}
</style>
