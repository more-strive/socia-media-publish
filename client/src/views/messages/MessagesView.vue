<template>
  <el-tabs v-model="tab">
    <!-- 收件箱 -->
    <el-tab-pane :label="`收件箱${unreadTotal ? `（${unreadTotal} 未读）` : ''}`" name="inbox">
      <div class="flex flex-wrap gap-2 mb-4">
        <el-select v-model="query.msg_type" placeholder="类型" clearable class="w-32" @change="load">
          <el-option label="评论" value="comment" />
          <el-option label="私信" value="dm" />
        </el-select>
        <el-select v-model="query.account_id" placeholder="账号" clearable filterable class="w-48" @change="load">
          <el-option v-for="a in accounts" :key="a.id" :label="`${platformLabel(a.platform)} · ${a.nickname}`" :value="a.id" />
        </el-select>
        <el-select v-model="query.is_read" placeholder="已读状态" clearable class="w-32" @change="load">
          <el-option label="未读" :value="false" />
          <el-option label="已读" :value="true" />
        </el-select>
        <div class="flex-1" />
        <el-button @click="mockVisible = true">模拟入站消息</el-button>
        <el-button :disabled="!selected.length" @click="markRead">标记已读</el-button>
      </div>

      <el-table :data="rows" class="page-card" v-loading="loading" @selection-change="(v: Message[]) => (selected = v)">
        <el-table-column type="selection" width="45" />
        <el-table-column label="类型" width="70">
          <template #default="{ row }">
            <el-tag size="small" :type="row.msg_type === 'dm' ? 'primary' : 'info'">{{ row.msg_type === 'dm' ? '私信' : '评论' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来自" prop="from_name" width="110" />
        <el-table-column label="内容" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'font-bold': !row.is_read }">{{ row.content }}</span>
          </template>
        </el-table-column>
        <el-table-column label="账号" width="150">
          <template #default="{ row }">{{ accountName(row.account_id) }}</template>
        </el-table-column>
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openReply(row)">回复</el-button>
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
    </el-tab-pane>

    <!-- 自动回复规则 -->
    <el-tab-pane label="自动回复规则" name="rules">
      <div class="flex mb-4">
        <el-button type="primary" @click="openRule()">新建规则</el-button>
      </div>
      <el-table :data="rules" class="page-card">
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ ruleTypeLabels[row.rule_type] }}</template>
        </el-table-column>
        <el-table-column label="关键词" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="k in row.keywords || []" :key="k" size="small" class="mr-1">{{ k }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="回复内容" min-width="220" show-overflow-tooltip />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch :model-value="row.status" @change="(v: boolean) => toggleRule(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openRule(row)">编辑</el-button>
            <el-button link type="danger" @click="removeRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <!-- 话术库 -->
    <el-tab-pane label="话术库" name="scripts">
      <div class="flex gap-2 mb-4">
        <el-select v-model="scriptGroup" placeholder="分组" clearable class="w-40" @change="filterScripts">
          <el-option v-for="g in scriptGroups" :key="g" :label="g" :value="g" />
        </el-select>
        <div class="flex-1" />
        <el-button type="primary" @click="openScript()">新建话术</el-button>
      </div>
      <el-table :data="filteredScripts" class="page-card">
        <el-table-column prop="group_name" label="分组" width="110" />
        <el-table-column prop="title" label="标题" width="160" />
        <el-table-column prop="content" label="内容" min-width="260" show-overflow-tooltip />
        <el-table-column label="归属" width="100">
          <template #default="{ row }">{{ row.owner_id ? '个人' : '团队' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="copyScript(row)">复制</el-button>
            <el-button link type="primary" @click="openScript(row)">编辑</el-button>
            <el-button link type="danger" @click="removeScript(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>

  <!-- 回复抽屉 -->
  <el-drawer v-model="replyVisible" title="回复消息" size="420px">
    <div v-if="replyTarget" class="flex flex-col gap-3">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="来自">{{ replyTarget.from_name }}</el-descriptions-item>
        <el-descriptions-item label="内容">{{ replyTarget.content }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ fmtTime(replyTarget.created_at) }}</el-descriptions-item>
      </el-descriptions>
      <el-select v-model="scriptPick" placeholder="从话术库选择" clearable @change="applyScript">
        <el-option v-for="s in scripts" :key="s.id" :label="s.title" :value="s.id" />
      </el-select>
      <el-input v-model="replyContent" type="textarea" :rows="5" placeholder="回复内容" />
      <el-button type="primary" :loading="replying" @click="doReply">发送回复</el-button>
    </div>
  </el-drawer>

  <!-- 规则表单 -->
  <el-dialog v-model="ruleVisible" :title="ruleForm.id ? '编辑规则' : '新建规则'" width="480px">
    <el-form :model="ruleForm" label-width="90px">
      <el-form-item label="类型">
        <el-radio-group v-model="ruleForm.rule_type">
          <el-radio value="keyword">关键词回复</el-radio>
          <el-radio value="welcome">欢迎语</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="ruleForm.rule_type === 'keyword'" label="关键词">
        <el-select v-model="ruleForm.keywords" multiple filterable allow-create class="w-full" placeholder="输入后回车" />
      </el-form-item>
      <el-form-item label="回复内容">
        <el-input v-model="ruleForm.content" type="textarea" :rows="4" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="ruleVisible = false">取消</el-button>
      <el-button type="primary" @click="saveRule">保存</el-button>
    </template>
  </el-dialog>

  <!-- 话术表单 -->
  <el-dialog v-model="scriptVisible" :title="scriptForm.id ? '编辑话术' : '新建话术'" width="480px">
    <el-form :model="scriptForm" label-width="90px">
      <el-form-item label="分组">
        <el-select v-model="scriptForm.group_name" filterable allow-create class="w-full">
          <el-option v-for="g in scriptGroups" :key="g" :label="g" :value="g" />
        </el-select>
      </el-form-item>
      <el-form-item label="标题"><el-input v-model="scriptForm.title" /></el-form-item>
      <el-form-item label="内容"><el-input v-model="scriptForm.content" type="textarea" :rows="5" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="scriptVisible = false">取消</el-button>
      <el-button type="primary" @click="saveScript">保存</el-button>
    </template>
  </el-dialog>

  <!-- 模拟入站（联调用） -->
  <el-dialog v-model="mockVisible" title="模拟平台消息推送（联调用）" width="480px">
    <el-form :model="mockForm" label-width="90px">
      <el-form-item label="账号">
        <el-select v-model="mockForm.account_id" class="w-full">
          <el-option v-for="a in accounts" :key="a.id" :label="`${platformLabel(a.platform)} · ${a.nickname}`" :value="a.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="类型">
        <el-radio-group v-model="mockForm.msg_type">
          <el-radio value="comment">评论</el-radio>
          <el-radio value="dm">私信</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="内容"><el-input v-model="mockForm.content" /></el-form-item>
      <el-form-item label="来自"><el-input v-model="mockForm.from_name" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="mockVisible = false">取消</el-button>
      <el-button type="primary" @click="doMock">推送</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accountApi, messageApi } from '@/api/modules'
import { fmtTime, platformLabel } from '@/utils/format'
import type { Message, ReplyRule, Script, SocialAccount } from '@/types'

const tab = ref('inbox')
const ruleTypeLabels: Record<string, string> = { keyword: '关键词', welcome: '欢迎语', follow: '关注回复' }

const loading = ref(false)
const rows = ref<Message[]>([])
const total = ref(0)
const selected = ref<Message[]>([])
const accounts = ref<SocialAccount[]>([])
const accountMap = ref<Record<number, SocialAccount>>({})
const unreadTotal = ref(0)
const query = reactive<Record<string, unknown>>({ page: 1, page_size: 20, msg_type: '', account_id: '', is_read: '' })

const rules = ref<ReplyRule[]>([])
const scripts = ref<Script[]>([])
const scriptGroup = ref('')
const scriptGroups = computed(() => [...new Set(scripts.value.map((s) => s.group_name))])
const filteredScripts = computed(() =>
  scriptGroup.value ? scripts.value.filter((s) => s.group_name === scriptGroup.value) : scripts.value,
)

const replyVisible = ref(false)
const replyTarget = ref<Message | null>(null)
const replyContent = ref('')
const replying = ref(false)
const scriptPick = ref<number | ''>('')

const ruleVisible = ref(false)
const ruleForm = reactive<Record<string, unknown>>({})

const scriptVisible = ref(false)
const scriptForm = reactive<Record<string, unknown>>({})

const mockVisible = ref(false)
const mockForm = reactive<Record<string, unknown>>({ msg_type: 'dm', content: '请问价格多少？', from_name: '测试用户' })

function accountName(id: number): string {
  const a = accountMap.value[id]
  return a ? `${platformLabel(a.platform)} · ${a.nickname}` : `账号#${id}`
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const params = Object.fromEntries(Object.entries(query).filter(([, v]) => v !== '' && v != null))
    const data = await messageApi.list(params)
    rows.value = data.items
    total.value = data.total
    const unread = await messageApi.unreadCount()
    unreadTotal.value = unread.comment + unread.dm
  } finally {
    loading.value = false
  }
}

async function markRead(): Promise<void> {
  await messageApi.markRead(selected.value.map((m) => m.id))
  ElMessage.success('已标记')
  await load()
}

function openReply(row: Message): void {
  replyTarget.value = row
  replyContent.value = ''
  scriptPick.value = ''
  replyVisible.value = true
}

function applyScript(id: number | ''): void {
  const s = scripts.value.find((x) => x.id === id)
  if (s) replyContent.value = s.content
}

async function doReply(): Promise<void> {
  if (!replyContent.value.trim()) return void ElMessage.warning('请输入回复内容')
  replying.value = true
  try {
    await messageApi.reply(replyTarget.value!.id, replyContent.value)
    ElMessage.success('已回复')
    replyVisible.value = false
    await load()
  } finally {
    replying.value = false
  }
}

async function loadRules(): Promise<void> {
  rules.value = await messageApi.rules()
}

async function toggleRule(row: ReplyRule, v: boolean): Promise<void> {
  await messageApi.updateRule(row.id, { ...row, status: v })
  await loadRules()
}

function openRule(row?: ReplyRule): void {
  Object.assign(ruleForm, row ?? { id: null, rule_type: 'keyword', keywords: [], content: '', status: true })
  ruleVisible.value = true
}

async function saveRule(): Promise<void> {
  if (ruleForm.id) await messageApi.updateRule(ruleForm.id as number, ruleForm)
  else await messageApi.createRule(ruleForm)
  ElMessage.success('已保存')
  ruleVisible.value = false
  await loadRules()
}

async function removeRule(row: ReplyRule): Promise<void> {
  await ElMessageBox.confirm('确定删除该规则？', '提示', { type: 'warning' })
  await messageApi.removeRule(row.id)
  await loadRules()
}

async function loadScripts(): Promise<void> {
  scripts.value = await messageApi.scripts()
}

function filterScripts(): void {
  /* computed 自动响应 */
}

function openScript(row?: Script): void {
  Object.assign(scriptForm, row ?? { id: null, group_name: '默认分组', title: '', content: '' })
  scriptVisible.value = true
}

async function saveScript(): Promise<void> {
  if (scriptForm.id) await messageApi.updateScript(scriptForm.id as number, scriptForm)
  else await messageApi.createScript(scriptForm)
  ElMessage.success('已保存')
  scriptVisible.value = false
  await loadScripts()
}

async function removeScript(row: Script): Promise<void> {
  await ElMessageBox.confirm(`确定删除话术「${row.title}」？`, '提示', { type: 'warning' })
  await messageApi.removeScript(row.id)
  await loadScripts()
}

function copyScript(row: Script): void {
  void navigator.clipboard.writeText(row.content)
  ElMessage.success('已复制')
}

async function doMock(): Promise<void> {
  await messageApi.mockInbound(mockForm)
  ElMessage.success('已推送（命中关键词规则会自动回复）')
  mockVisible.value = false
  await load()
}

onMounted(async () => {
  await load()
  await loadRules()
  await loadScripts()
  const data = await accountApi.list({ page: 1, page_size: 200 })
  accounts.value = data.items
  accountMap.value = Object.fromEntries(data.items.map((a) => [a.id, a]))
})
</script>
