<template>
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

    <el-container>
      <!-- 顶栏 -->
      <el-header class="header flex-between px-6!">
        <div class="text-muted">{{ teamName }}</div>
        <div class="flex items-center gap-4">
          <el-badge :value="unreadTotal" :hidden="unreadTotal === 0" :max="99">
            <el-icon :size="18" class="cursor-pointer" @click="router.push('/messages')">
              <ChatDotRound />
            </el-icon>
          </el-badge>
          <el-dropdown @command="onCommand">
            <span class="flex items-center gap-2 cursor-pointer">
              <el-avatar :size="30">{{ auth.user?.nickname?.slice(0, 1) }}</el-avatar>
              <span>{{ auth.user?.nickname }}</span>
              <el-tag size="small" type="info">{{ roleLabel }}</el-tag>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="team">团队管理</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bell,
  Calendar,
  ChatDotRound,
  Coin,
  DataAnalysis,
  MagicStick,
  Monitor,
  Platform,
  SwitchButton,
  User,
  Document,
  Setting,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { messageApi } from '@/api/modules'
import { useRpaEngine } from '@/composables/useRpaEngine'
import { useAuthStore } from '@/stores/auth'
import { ROLE_LABELS } from '@/types'

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
      { path: '/browser', label: '账号浏览器', icon: Platform },
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

const teamName = computed(() => auth.team?.name ?? '')
const roleLabel = computed(() => ROLE_LABELS[auth.role] ?? auth.role)
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
    router.push('/team')
  }
}

onMounted(() => {
  if (!auth.user) void auth.fetchMe().catch(() => undefined)
  void loadUnread()
  rpa.start() // RPA 引擎随布局启动（是否执行由开关控制）
})
</script>

<style scoped>
.aside {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid #e4e7ed;
}
.logo {
  height: 56px;
  flex-shrink: 0;
}
.header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  height: 56px;
}
.main {
  overflow-y: auto;
}
</style>
