<template>
  <div class="flex flex-col gap-4">
    <!-- 汇总卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div v-for="c in cards" :key="c.label" class="page-card">
        <div class="text-muted">{{ c.label }}</div>
        <div class="text-26px font-bold mt-2">{{ c.value }}</div>
        <div v-if="c.sub" class="text-muted mt-1">{{ c.sub }}</div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- 今日汇总 -->
      <el-card shadow="never">
        <template #header>今日数据（昨日对比）</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="新增粉丝">{{ today?.new_followers ?? '-' }} / {{ yesterday?.new_followers ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="播放量">{{ fmtNum(today?.views) }} / {{ fmtNum(yesterday?.views) }}</el-descriptions-item>
          <el-descriptions-item label="点赞">{{ fmtNum(today?.likes) }} / {{ fmtNum(yesterday?.likes) }}</el-descriptions-item>
          <el-descriptions-item label="发布作品">{{ today?.published_count ?? 0 }} / {{ yesterday?.published_count ?? 0 }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 最近发布 -->
      <el-card shadow="never">
        <template #header>
          <div class="flex-between">
            <span>最近发布任务</span>
            <el-link type="primary" @click="router.push('/publish')">查看全部</el-link>
          </div>
        </template>
        <el-table :data="recentTasks" size="small" :show-header="false">
          <el-table-column prop="content_title" label="内容" min-width="140" show-overflow-tooltip />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">{{ STATUS_LABELS[row.status] ?? row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="成功/总数" width="90">
            <template #default="{ row }">{{ row.success_count }}/{{ row.item_count }}</template>
          </el-table-column>
          <el-table-column label="时间" width="140">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 快捷入口 -->
    <div class="page-card flex gap-3">
      <el-button type="primary" @click="router.push('/contents')">新建内容</el-button>
      <el-button @click="router.push('/publish')">创建发布任务</el-button>
      <el-button @click="router.push('/ai')">AI 文案生成</el-button>
      <el-button @click="router.push('/accounts')">添加托管账号</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { publishApi, statsApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import { fmtNum, fmtTime, statusTagType, STATUS_LABELS } from '@/utils/format'
import type { PublishTask, Summary } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const today = ref<Summary | null>(null)
const yesterday = ref<Summary | null>(null)
const recentTasks = ref<PublishTask[]>([])

function dayOffset(offset: number): string {
  const d = new Date(Date.now() - offset * 86400000)
  return d.toISOString().slice(0, 10)
}

const cards = computed(() => [
  { label: '托管账号', value: today.value?.account_count ?? '-', sub: '' },
  { label: '总粉丝', value: fmtNum(today.value?.total_followers), sub: '' },
  { label: 'AI 积分余额', value: auth.team?.credits ?? '-', sub: `席位 ${auth.team?.seats_used ?? '-'}/${auth.team?.seats_total ?? '-'}` },
  { label: '未读私信/评论', value: unread.value, sub: '' },
])
const unread = ref(0)

onMounted(async () => {
  const [t, y, tasks, unreadResp] = await Promise.allSettled([
    statsApi.summary(dayOffset(0)),
    statsApi.summary(dayOffset(1)),
    publishApi.list({ page: 1, page_size: 5 }),
    import('@/api/modules').then((m) => m.messageApi.unreadCount()),
  ])
  if (t.status === 'fulfilled') today.value = t.value
  if (y.status === 'fulfilled') yesterday.value = y.value
  if (tasks.status === 'fulfilled') recentTasks.value = tasks.value.items
  if (unreadResp.status === 'fulfilled') unread.value = unreadResp.value.comment + unreadResp.value.dm
})
</script>
