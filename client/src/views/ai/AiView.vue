<template>
  <div class="flex flex-col gap-4">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="page-card">
        <div class="text-muted">积分余额</div>
        <div class="text-26px font-bold mt-1">{{ credits }}</div>
      </div>
      <div class="page-card col-span-2 flex items-center gap-4">
        <el-button type="primary" @click="openCreate">创建 AI 任务</el-button>
        <el-button @click="router.push('/billing')">购买积分包</el-button>
        <div class="text-muted">
          文案 1 积分 · 视频 100 · 数字人 200 · 声音克隆 50（失败自动退还）
        </div>
      </div>
    </div>

    <el-card shadow="never" header="任务列表">
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ typeLabels[row.task_type] }}</template>
        </el-table-column>
        <el-table-column prop="prompt" label="提示词" min-width="200" show-overflow-tooltip />
        <el-table-column label="提供商" width="90">
          <template #default="{ row }">{{ providerLabels[row.provider] ?? row.provider }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ STATUS_LABELS[row.status] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="credits_cost" label="积分" width="70" />
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="结果" width="100" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'succeeded'" link type="primary" @click="showResult(row)">查看</el-button>
            <el-tooltip v-else-if="row.status === 'failed'" :content="row.error || '失败'">
              <el-button link type="danger">原因</el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="query.page"
        :page-size="query.page_size"
        :total="total"
        layout="total, prev, pager, next"
        class="mt-3 justify-end"
        @current-change="load"
      />
    </el-card>

    <!-- 创建任务 -->
    <el-dialog v-model="createVisible" title="创建 AI 任务" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="类型">
          <el-radio-group v-model="form.task_type">
            <el-radio-button value="copy">AI 文案</el-radio-button>
            <el-radio-button value="video">视频生成</el-radio-button>
            <el-radio-button value="digital_human">数字人</el-radio-button>
            <el-radio-button value="voice_clone">声音克隆</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="form.task_type === 'copy' ? '主题' : '提示词'">
          <el-input v-model="form.prompt" type="textarea" :rows="4" :placeholder="placeholder" />
        </el-form-item>
        <el-form-item v-if="form.task_type === 'copy'" label="平台风格">
          <el-select v-model="platform" class="w-full">
            <el-option label="小红书" value="xhs" />
            <el-option label="抖音" value="douyin" />
            <el-option label="公众号" value="wechat_gzh" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="text-muted ml-4">
        预计消耗 {{ costHint }} 积分，当前余额 {{ credits }}。文案同步返回；视频/数字人为异步任务，完成后在此列表查看结果。
      </div>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="doCreate">创建（扣积分）</el-button>
      </template>
    </el-dialog>

    <!-- 结果 -->
    <el-dialog v-model="resultVisible" title="生成结果" width="560px">
      <div v-if="resultTask?.result?.text" class="whitespace-pre-wrap">{{ resultTask.result.text }}</div>
      <div v-else-if="resultTask?.result?.video_url">
        <video :src="String(resultTask.result.video_url)" controls class="w-full" />
      </div>
      <pre v-else class="whitespace-pre-wrap">{{ JSON.stringify(resultTask?.result, null, 2) }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { aiApi } from '@/api/modules'
import { fmtTime, statusTagType, STATUS_LABELS } from '@/utils/format'
import type { AITask } from '@/types'

const router = useRouter()
const typeLabels: Record<string, string> = { copy: '文案', video: '视频', digital_human: '数字人', voice_clone: '声音克隆' }
const providerLabels: Record<string, string> = { mock: '内置', ark: '火山方舟', seedance: 'Seedance' }
const creditsTable: Record<string, number> = { copy: 1, video: 100, digital_human: 200, voice_clone: 50 }

const credits = ref(0)
const rows = ref<AITask[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 20 })

const createVisible = ref(false)
const creating = ref(false)
const platform = ref('xhs')
const form = reactive<{ task_type: string; prompt: string }>({ task_type: 'copy', prompt: '' })

const resultVisible = ref(false)
const resultTask = ref<AITask | null>(null)
let timer: number | undefined

const costHint = computed(() => creditsTable[form.task_type] ?? '-')
const placeholder = computed(() =>
  form.task_type === 'copy'
    ? '如：千元以内蓝牙耳机推荐'
    : form.task_type === 'video'
      ? '如：一段 10 秒的产品开箱短视频，节奏明快'
      : '描述需求...',
)

async function loadCredits(): Promise<void> {
  credits.value = (await aiApi.credits()).credits
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await aiApi.list({ ...query })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  Object.assign(form, { task_type: 'copy', prompt: '' })
  createVisible.value = true
}

async function doCreate(): Promise<void> {
  if (!form.prompt.trim()) return void ElMessage.warning('请填写提示词')
  creating.value = true
  try {
    const task = await aiApi.create({
      task_type: form.task_type,
      prompt: form.prompt,
      ...(form.task_type === 'copy' ? { params: { platform: platform.value } } : {}),
    })
    ElMessage.success(task.task_type === 'copy' && task.status === 'succeeded' ? '已生成' : '任务已创建')
    createVisible.value = false
    if (task.task_type === 'copy' && task.status === 'succeeded') {
      resultTask.value = task
      resultVisible.value = true
    }
    await Promise.all([load(), loadCredits()])
  } finally {
    creating.value = false
  }
}

function showResult(row: AITask): void {
  resultTask.value = row
  resultVisible.value = true
}

onMounted(() => {
  void load()
  void loadCredits()
  // 有执行中任务时轮询
  timer = window.setInterval(() => {
    if (rows.value.some((t) => ['pending', 'running'].includes(t.status))) {
      void load()
      void loadCredits()
    }
  }, 5000)
})

onBeforeUnmount(() => clearInterval(timer))
</script>
