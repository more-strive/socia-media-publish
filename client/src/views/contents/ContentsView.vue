<template>
  <div class="flex flex-col gap-3">
    <div class="flex flex-wrap gap-2">
      <el-select v-model="query.type_" placeholder="类型" clearable class="w-32">
        <el-option label="视频" value="video" />
        <el-option label="图文" value="images" />
        <el-option label="文章" value="article" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable class="w-32">
        <el-option label="草稿" value="draft" />
        <el-option label="待审核" value="reviewing" />
        <el-option label="已通过" value="approved" />
        <el-option label="已驳回" value="rejected" />
      </el-select>
      <el-input v-model="query.keyword" placeholder="搜索标题" clearable class="w-44" @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
      <div class="flex-1" />
      <el-upload :show-file-list="false" accept=".docx" multiple :http-request="doImportDocx">
        <el-button>导入 DOCX</el-button>
      </el-upload>
      <el-button @click="openAi">AI 生成文案</el-button>
      <el-button type="primary" @click="openCreate">新建内容</el-button>
    </div>

    <el-table :data="rows" class="page-card" v-loading="loading">
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column label="类型" width="80">
        <template #default="{ row }">{{ typeLabels[row.type] }}</template>
      </el-table-column>
      <el-table-column label="标签" min-width="140">
        <template #default="{ row }">
          <el-tag v-for="t in row.tags || []" :key="t" size="small" class="mr-1">{{ t }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ STATUS_LABELS[row.status] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="审核意见" prop="review_note" width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.review_note ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="['draft', 'rejected'].includes(row.status)" link type="warning" @click="submit(row)">提交审核</el-button>
          <el-button v-if="row.status === 'reviewing' && auth.canReview" link type="success" @click="review(row, true)">通过</el-button>
          <el-button v-if="row.status === 'reviewing' && auth.canReview" link type="danger" @click="review(row, false)">驳回</el-button>
          <el-button link type="primary" @click="router.push({ path: '/publish', query: { content_id: row.id } })">去发布</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-model:current-page="query.page"
      :page-size="query.page_size"
      :total="total"
      layout="total, prev, pager, next"
      class="justify-end"
      @current-change="load"
    />

    <!-- 编辑器 -->
    <el-dialog v-model="formVisible" :title="form.id ? '编辑内容' : '新建内容'" width="720px" top="5vh">
      <el-form :model="form" label-width="90px">
        <el-form-item label="类型">
          <el-radio-group v-model="form.type" :disabled="!!form.id">
            <el-radio-button value="video">视频</el-radio-button>
            <el-radio-button value="images">图文</el-radio-button>
            <el-radio-button value="article">文章</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="255" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" type="textarea" :rows="2" placeholder="公众号/头条摘要" />
        </el-form-item>
        <el-form-item v-if="form.type === 'article'" label="正文">
          <el-input v-model="form.body" type="textarea" :rows="10" placeholder="支持 HTML / Markdown 文本" />
        </el-form-item>
        <el-form-item v-else label="素材">
          <div class="w-full">
            <div class="flex items-center gap-2">
              <el-upload :show-file-list="false" multiple :accept="acceptOf" :http-request="doUploadMedia">
                <el-button :loading="uploading.length > 0">
                  上传{{ form.type === 'video' ? '视频' : '图片' }}<span class="text-muted text-12px ml-1">（存本地服务）</span>
                </el-button>
              </el-upload>
              <el-input v-model="manualUrl" placeholder="或粘贴外部素材链接，回车添加" class="flex-1" @keyup.enter="addManualUrl">
                <template #append>
                  <el-button @click="addManualUrl">添加</el-button>
                </template>
              </el-input>
            </div>
            <div v-for="u in uploading" :key="u.name" class="mt-2 text-12px text-muted">
              {{ u.name }} 上传中 {{ u.percent }}%
            </div>
            <div v-if="mediaList.length" class="flex flex-wrap gap-3 mt-3">
              <div v-for="(u, i) in mediaList" :key="u" class="relative">
                <el-image
                  v-if="isImage(u)"
                  :src="fileUrl(u)"
                  :preview-src-list="imageUrls"
                  fit="cover"
                  preview-teleported
                  class="w-16 h-16 rounded border"
                />
                <div v-else class="w-16 h-16 rounded border bg-gray-100 flex flex-col items-center justify-center text-11px text-center px-1">
                  <span>视频</span>
                  <span class="truncate w-full">{{ nameOf(u) }}</span>
                </div>
                <el-button
                  size="small"
                  circle
                  class="absolute -top-2 -right-2 z-10"
                  @click="mediaList.splice(i, 1)"
                >
                  ×
                </el-button>
              </div>
            </div>
            <div v-else class="text-muted text-12px mt-2">暂无素材；视频发布时取列表第一个视频</div>
          </div>
        </el-form-item>
        <el-form-item label="封面">
          <div class="flex items-center gap-2 w-full">
            <el-input v-model="form.cover" placeholder="封面图 URL，或点右侧上传" />
            <el-upload :show-file-list="false" accept="image/*" :http-request="doUploadCover">
              <el-button :loading="coverUploading">上传封面</el-button>
            </el-upload>
            <el-image
              v-if="form.cover"
              :src="fileUrl(String(form.cover))"
              :preview-src-list="[fileUrl(String(form.cover))]"
              fit="cover"
              preview-teleported
              class="w-10 h-10 rounded border shrink-0"
            />
          </div>
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="form.tags" multiple filterable allow-create class="w-full" placeholder="输入后回车创建" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存草稿</el-button>
      </template>
    </el-dialog>

    <!-- AI 生成 -->
    <el-dialog v-model="aiVisible" title="AI 文案生成" width="520px">
      <el-form label-width="90px">
        <el-form-item label="主题">
          <el-input v-model="aiForm.topic" placeholder="如：百元耳机推荐" />
        </el-form-item>
        <el-form-item label="平台风格">
          <el-select v-model="aiForm.platform" class="w-full">
            <el-option label="小红书" value="xhs" />
            <el-option label="抖音" value="douyin" />
            <el-option label="公众号" value="wechat_gzh" />
          </el-select>
        </el-form-item>
        <el-form-item label="语气">
          <el-input v-model="aiForm.tone" placeholder="如：专业、轻松幽默（可选）" />
        </el-form-item>
      </el-form>
      <el-input v-if="aiResult" v-model="aiResult" type="textarea" :rows="8" class="mt-2" />
      <template #footer>
        <el-button @click="aiVisible = false">关闭</el-button>
        <el-button type="primary" plain :loading="aiLoading" @click="doAiGenerate">生成</el-button>
        <el-button v-if="aiResult" type="primary" @click="saveAiAsDraft">存为草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { contentApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import { fmtTime, statusTagType, STATUS_LABELS } from '@/utils/format'
import type { Content } from '@/types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const typeLabels: Record<string, string> = { video: '视频', images: '图文', article: '文章' }
const loading = ref(false)
const saving = ref(false)
const rows = ref<Content[]>([])
const total = ref(0)
const query = reactive<Record<string, unknown>>({ page: 1, page_size: 20, type_: '', status: '', keyword: '' })

const formVisible = ref(false)
const form = reactive<Record<string, unknown>>({ type: 'video', tags: [] })
/** 素材列表（本地上传的相对路径 / 外部绝对 URL 混存，保存时整体提交 media） */
const mediaList = ref<string[]>([])
const manualUrl = ref('')
const uploading = ref<{ name: string; percent: number }[]>([])
const coverUploading = ref(false)

const imageExts = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp']
const acceptOf = computed(() => (form.type === 'video' ? 'video/*' : 'image/*'))

/** 本地上传素材是 /api 前缀相对路径，展示/预览时拼当前 origin（开发态走 vite 代理） */
function fileUrl(u: string): string {
  return /^https?:/.test(u) ? u : `${location.origin}${u}`
}
function isImage(u: string): boolean {
  const ext = u.split('?')[0].split('.').pop()?.toLowerCase() ?? ''
  return imageExts.includes(ext)
}
function nameOf(u: string): string {
  return decodeURIComponent(u.split('?')[0].split('/').pop() ?? u)
}
const imageUrls = computed(() => mediaList.value.filter(isImage).map(fileUrl))

async function doUploadMedia(option: { file: File }): Promise<void> {
  const entry = { name: option.file.name, percent: 0 }
  uploading.value = [...uploading.value, entry]
  try {
    const data = await contentApi.upload(option.file, (p) => {
      entry.percent = p
    })
    mediaList.value = [...mediaList.value, data.url]
    ElMessage.success(`已上传 ${option.file.name}`)
  } finally {
    uploading.value = uploading.value.filter((x) => x !== entry)
  }
}

async function doUploadCover(option: { file: File }): Promise<void> {
  coverUploading.value = true
  try {
    const data = await contentApi.upload(option.file)
    form.cover = data.url
  } finally {
    coverUploading.value = false
  }
}

function addManualUrl(): void {
  const u = manualUrl.value.trim()
  if (!u) return
  if (!/^(https?:\/\/|\/api\/)/.test(u)) return void ElMessage.warning('请粘贴 http(s) 链接')
  mediaList.value = [...mediaList.value, u]
  manualUrl.value = ''
}

const aiVisible = ref(false)
const aiLoading = ref(false)
const aiResult = ref('')
const aiForm = reactive({ topic: '', platform: 'xhs', tone: '' })

async function load(): Promise<void> {
  loading.value = true
  try {
    const params = Object.fromEntries(Object.entries(query).filter(([, v]) => v !== '' && v != null))
    const data = await contentApi.list(params)
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  Object.assign(form, { id: null, type: 'video', title: '', summary: '', body: '', cover: '', tags: [] })
  mediaList.value = []
  manualUrl.value = ''
  formVisible.value = true
}

function openEdit(row: Content): void {
  if (!['draft', 'rejected'].includes(row.status)) {
    ElMessage.warning('仅草稿/驳回状态可编辑')
    return
  }
  Object.assign(form, { ...row })
  mediaList.value = [...(row.media || [])]
  manualUrl.value = ''
  formVisible.value = true
}

async function save(): Promise<void> {
  form.title = (form.title as string)?.trim()
  if (!form.title) return void ElMessage.warning('请填写标题')
  if (form.type !== 'article' && !mediaList.value.length) return void ElMessage.warning('请上传或添加至少一个素材')
  form.media = [...mediaList.value]
  saving.value = true
  try {
    if (form.id) await contentApi.update(form.id as number, form)
    else await contentApi.create(form)
    ElMessage.success('已保存')
    formVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function submit(row: Content): Promise<void> {
  await contentApi.submit(row.id)
  ElMessage.success('已提交审核')
  await load()
}

async function review(row: Content, approve: boolean): Promise<void> {
  const note = approve ? '' : await ElMessageBox.prompt('驳回原因', '驳回', { inputPlaceholder: '选填' }).then((r) => r.value).catch(() => null)
  if (!approve && note === null) return
  await contentApi.review(row.id, approve, note || undefined)
  ElMessage.success('审核完成')
  await load()
}

async function remove(row: Content): Promise<void> {
  await ElMessageBox.confirm(`确定删除「${row.title}」？`, '提示', { type: 'warning' })
  await contentApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

async function doImportDocx(option: { file: File }): Promise<void> {
  const data = await contentApi.importDocx([option.file])
  ElMessage.success(`成功导入 ${data.imported} 篇：${data.titles.join('、')}`)
  await load()
}

function openAi(): void {
  aiResult.value = ''
  aiVisible.value = true
}

async function doAiGenerate(): Promise<void> {
  if (!aiForm.topic.trim()) return void ElMessage.warning('请填写主题')
  aiLoading.value = true
  try {
    const data = await contentApi.aiGenerate(aiForm.topic, aiForm.platform, aiForm.tone || undefined)
    aiResult.value = data.content
  } finally {
    aiLoading.value = false
  }
}

async function saveAiAsDraft(): Promise<void> {
  await contentApi.create({ type: 'article', title: aiForm.topic, body: aiResult.value, tags: [] })
  ElMessage.success('已存为文章草稿')
  aiVisible.value = false
  await load()
}

onMounted(() => {
  void load()
  // 从发布页跳转过来直接发布
  const cid = route.query.content_id
  if (cid) router.replace({ path: '/publish', query: { content_id: cid } })
})
</script>
