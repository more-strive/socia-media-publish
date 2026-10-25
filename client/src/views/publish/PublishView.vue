<template>
  <div>
    <el-tabs v-model="tab" @tab-change="onTab">
      <!-- 任务列表 -->
      <el-tab-pane label="发布任务" name="tasks">
        <div class="flex gap-2 mb-4">
          <el-select v-model="statusFilter" placeholder="状态" clearable class="w-36" @change="loadTasks">
            <el-option v-for="s in ['reviewing', 'scheduled', 'publishing', 'published', 'partial', 'failed', 'canceled']" :key="s" :label="STATUS_LABELS[s]" :value="s" />
          </el-select>
          <div class="flex-1" />
          <el-button type="primary" @click="openCreate">创建发布任务</el-button>
        </div>
        <el-table :data="tasks" class="page-card" v-loading="loading">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="content_title" label="内容" min-width="180" show-overflow-tooltip />
          <el-table-column label="模式" width="90">
            <template #default="{ row }">{{ row.mode === 'immediate' ? '立即' : '定时' }}</template>
          </el-table-column>
          <el-table-column label="定时时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.scheduled_at) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">{{ STATUS_LABELS[row.status] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="成功/失败/总数" width="120">
            <template #default="{ row }">{{ row.success_count }}/{{ row.failed_count }}/{{ row.item_count }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="showDetail(row)">详情</el-button>
              <el-button v-if="['reviewing', 'scheduled'].includes(row.status)" link type="danger" @click="cancel(row)">取消</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="taskQuery.page"
          :page-size="taskQuery.page_size"
          :total="taskTotal"
          layout="total, prev, pager, next"
          class="mt-3 justify-end"
          @current-change="loadTasks"
        />
      </el-tab-pane>

      <!-- 待审核 -->
      <el-tab-pane :label="`待审核${reviewTotal ? `(${reviewTotal})` : ''}`" name="reviews">
        <el-table :data="reviews" class="page-card" v-loading="loading">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="content_title" label="内容" min-width="200" show-overflow-tooltip />
          <el-table-column label="账号数" width="80">
            <template #default="{ row }">{{ row.item_count }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="success" @click="reviewTask(row, true)">通过</el-button>
              <el-button link type="danger" @click="reviewTask(row, false)">驳回</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 发布日历 -->
      <el-tab-pane label="发布日历" name="calendar">
        <el-calendar v-model="calendarMonth">
          <template #header>
            <span class="font-bold">发布日历</span>
            <el-button-group>
              <el-button @click="calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1)">上月</el-button>
              <el-button @click="calendarMonth = new Date()">今天</el-button>
              <el-button @click="calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1)">下月</el-button>
            </el-button-group>
          </template>
          <template #date-cell="{ data }">
            <div v-if="calendarMap[data.day]" class="w-full">
              <el-badge :value="calendarMap[data.day].length" type="primary" class="w-full">
                <div class="text-12px truncate w-92px">{{ calendarMap[data.day][0]?.content_title ?? '' }}</div>
              </el-badge>
            </div>
          </template>
        </el-calendar>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建任务 -->
    <el-dialog v-model="createVisible" title="创建发布任务" width="620px">
      <el-form label-width="90px">
        <el-form-item label="内容">
          <el-select v-model="createForm.content_id" class="w-full" placeholder="仅可选已通过审核的内容">
            <el-option v-for="c in approvedContents" :key="c.id" :label="`[${typeLabels[c.type]}] ${c.title}`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标账号">
          <el-select v-model="createForm.account_ids" multiple filterable class="w-full" placeholder="可多选（1 内容 → 多账号）">
            <el-option v-for="a in validAccounts" :key="a.id" :label="`${platformLabel(a.platform)} · ${a.nickname}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="发布模式">
          <el-radio-group v-model="createForm.mode">
            <el-radio-button value="immediate">立即发布</el-radio-button>
            <el-radio-button value="scheduled">定时发布</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="createForm.mode === 'scheduled'" label="发布时间">
          <el-date-picker v-model="createForm.scheduled_at" type="datetime" placeholder="选择时间" />
        </el-form-item>
        <el-form-item label="平台设置">
          <el-checkbox v-model="createForm.original">原创声明</el-checkbox>
          <el-input v-model="createForm.collection" placeholder="合集名（选填）" class="w-44 ml-2" />
        </el-form-item>
      </el-form>
      <div class="text-muted ml-4">提示：开启审核流时，运营创建的任务需审核员通过后才会执行。</div>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="saveCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情 -->
    <el-dialog v-model="detailVisible" :title="`任务 #${detail?.id} 详情`" width="720px">
      <el-descriptions :column="3" border size="small" class="mb-3">
        <el-descriptions-item label="内容">{{ detail?.content_title }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType(detail?.status || '')" size="small">{{ STATUS_LABELS[detail?.status || ''] }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="成功/失败">{{ detail?.success_count }}/{{ detail?.failed_count }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="detail?.items || []" size="small">
        <el-table-column label="账号" min-width="160">
          <template #default="{ row }">{{ accountName(row.account_id) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ STATUS_LABELS[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fail_reason" label="失败原因" min-width="120" show-overflow-tooltip />
        <el-table-column label="发布时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column label="链接" width="80">
          <template #default="{ row }">
            <el-link v-if="row.publish_url" type="primary" :href="row.publish_url" target="_blank">查看</el-link>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accountApi, contentApi, publishApi } from '@/api/modules'
import { fmtTime, platformLabel, statusTagType, STATUS_LABELS } from '@/utils/format'
import type { Content, PublishTask, SocialAccount } from '@/types'

const route = useRoute()
const typeLabels: Record<string, string> = { video: '视频', images: '图文', article: '文章' }

const tab = ref('tasks')
const loading = ref(false)
const tasks = ref<PublishTask[]>([])
const taskTotal = ref(0)
const statusFilter = ref('')
const taskQuery = reactive({ page: 1, page_size: 20 })

const reviews = ref<PublishTask[]>([])
const reviewTotal = ref(0)

const calendarMonth = ref(new Date())
const calendarMap = ref<Record<string, PublishTask[]>>({})

const createVisible = ref(false)
const creating = ref(false)
const approvedContents = ref<Content[]>([])
const validAccounts = ref<SocialAccount[]>([])
const createForm = reactive<Record<string, unknown>>({ content_id: null, account_ids: [], mode: 'immediate', scheduled_at: null, original: false, collection: '' })

const detailVisible = ref(false)
const detail = ref<PublishTask | null>(null)
const accountMap = ref<Record<number, SocialAccount>>({})

function accountName(id: number): string {
  const a = accountMap.value[id]
  return a ? `${platformLabel(a.platform)} · ${a.nickname}` : `账号#${id}`
}

async function loadTasks(): Promise<void> {
  loading.value = true
  try {
    const params = { ...taskQuery, ...(statusFilter.value ? { status: statusFilter.value } : {}) }
    const data = await publishApi.list(params)
    tasks.value = data.items
    taskTotal.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadReviews(): Promise<void> {
  loading.value = true
  try {
    const data = await publishApi.reviews()
    reviews.value = data.items
    reviewTotal.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadCalendar(): Promise<void> {
  const d = calendarMonth.value
  const start = new Date(d.getFullYear(), d.getMonth(), 1)
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0)
  const fmt = (x: Date) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`
  const days = await publishApi.calendar(fmt(start), fmt(end))
  const map: Record<string, PublishTask[]> = {}
  for (const day of days) map[day.date] = day.tasks
  calendarMap.value = map
}

watch(calendarMonth, () => void loadCalendar())

function onTab(): void {
  if (tab.value === 'tasks') void loadTasks()
  else if (tab.value === 'reviews') void loadReviews()
  else void loadCalendar()
}

async function openCreate(): Promise<void> {
  const [contents, accounts] = await Promise.all([
    contentApi.list({ page: 1, page_size: 100, status: 'approved' }),
    accountApi.list({ page: 1, page_size: 200, auth_status: 'valid' }),
  ])
  approvedContents.value = contents.items
  validAccounts.value = accounts.items
  accountMap.value = Object.fromEntries(accounts.items.map((a) => [a.id, a]))
  Object.assign(createForm, { content_id: route.query.content_id ? Number(route.query.content_id) : null, account_ids: [], mode: 'immediate', scheduled_at: null, original: false, collection: '' })
  createVisible.value = true
}

async function saveCreate(): Promise<void> {
  if (!createForm.content_id) return void ElMessage.warning('请选择内容')
  if (!(createForm.account_ids as number[]).length) return void ElMessage.warning('请选择目标账号')
  if (createForm.mode === 'scheduled' && !createForm.scheduled_at) return void ElMessage.warning('请选择定时时间')
  creating.value = true
  try {
    const extras: Record<string, unknown> = {}
    if (createForm.original) extras.original = true
    if ((createForm.collection as string)?.trim()) extras.collection = createForm.collection
    await publishApi.create({
      content_id: createForm.content_id,
      account_ids: createForm.account_ids,
      mode: createForm.mode,
      scheduled_at: createForm.mode === 'scheduled' ? createForm.scheduled_at : undefined,
      extras,
    })
    ElMessage.success('任务已创建')
    createVisible.value = false
    await loadTasks()
  } finally {
    creating.value = false
  }
}

async function showDetail(row: PublishTask): Promise<void> {
  detail.value = await publishApi.get(row.id)
  detailVisible.value = true
}

async function cancel(row: PublishTask): Promise<void> {
  await ElMessageBox.confirm(`确定取消任务 #${row.id}？`, '提示', { type: 'warning' })
  await publishApi.cancel(row.id)
  ElMessage.success('已取消')
  await loadTasks()
}

async function reviewTask(row: PublishTask, approve: boolean): Promise<void> {
  const note = approve ? '' : await ElMessageBox.prompt('驳回原因', '驳回', { inputPlaceholder: '选填' }).then((r) => r.value).catch(() => null)
  if (!approve && note === null) return
  await publishApi.review(row.id, approve, note || undefined)
  ElMessage.success('审核完成')
  await loadReviews()
}

onMounted(() => {
  void loadTasks()
  void loadCalendar()
  if (route.query.content_id) void openCreate()
  // 执行中任务自动刷新
  setInterval(() => {
    if (tab.value === 'tasks' && tasks.value.some((t) => ['scheduled', 'publishing'].includes(t.status))) void loadTasks()
  }, 5000)
})
</script>
