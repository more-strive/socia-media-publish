<template>
  <el-tabs v-model="tab">
    <!-- 账号列表 -->
    <el-tab-pane label="账号列表" name="accounts">
      <div class="flex flex-wrap gap-2 mb-4">
        <el-select v-model="query.platform" placeholder="平台" clearable class="w-36">
          <el-option v-for="(label, key) in PLATFORM_LABELS" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select v-model="query.group_id" placeholder="分组" clearable class="w-36">
          <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
        <el-select v-model="query.auth_status" placeholder="授权状态" clearable class="w-32">
          <el-option label="有效" value="valid" />
          <el-option label="已失效" value="expired" />
        </el-select>
        <el-input v-model="query.keyword" placeholder="搜索昵称" clearable class="w-44" @keyup.enter="load" />
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="batchCheck">批量检测有效性</el-button>
        <div class="flex-1" />
        <el-button @click="groupDialogVisible = true">分组管理</el-button>
        <el-button type="primary" @click="openCreate">添加账号</el-button>
      </div>

      <el-table :data="rows" class="page-card" v-loading="loading">
        <el-table-column label="昵称" min-width="160">
          <template #default="{ row }">
            <span class="font-medium">{{ row.nickname }}</span>
            <el-tag size="small" class="ml-2">{{ platformLabel(row.platform) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分组" width="100">
          <template #default="{ row }">{{ row.group_name ?? '未分组' }}</template>
        </el-table-column>
        <el-table-column label="粉丝" width="90">
          <template #default="{ row }">{{ fmtNum(row.fans_count) }}</template>
        </el-table-column>
        <el-table-column label="授权状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.auth_status)" size="small">{{ STATUS_LABELS[row.auth_status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="通道" width="90">
          <template #default="{ row }">{{ channelLabels[row.channel] ?? row.channel }}</template>
        </el-table-column>
        <el-table-column label="最近检测" width="150">
          <template #default="{ row }">{{ fmtTime(row.last_active_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="row.auth_status !== 'valid'" link type="warning" @click="reAuth(row)">重新授权</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
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

    <!-- 代理 IP -->
    <el-tab-pane label="代理 IP" name="proxies">
      <div class="flex mb-4">
        <el-button type="primary" @click="openProxy()">添加代理</el-button>
      </div>
      <el-table :data="proxies" class="page-card">
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column label="地址" min-width="200">
          <template #default="{ row }">{{ row.scheme }}://{{ row.host }}:{{ row.port }}</template>
        </el-table-column>
        <el-table-column prop="region" label="归属地" width="110" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ STATUS_LABELS[row.status] ?? row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="检测时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.last_check_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="checkProxy(row)">检测连通</el-button>
            <el-button link type="primary" @click="openProxy(row)">编辑</el-button>
            <el-button link type="danger" @click="removeProxy(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>

  <!-- 新增/编辑账号 -->
  <el-dialog v-model="formVisible" :title="editing ? '编辑账号' : '添加托管账号'" width="480px">
    <el-form :model="form" label-width="90px">
      <template v-if="!editing">
        <el-form-item label="平台">
          <el-select v-model="form.platform" class="w-full">
            <el-option v-for="(label, key) in PLATFORM_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号昵称">
          <el-input v-model="form.nickname" />
        </el-form-item>
        <el-form-item label="发布通道">
          <el-select v-model="form.channel" class="w-full">
            <el-option label="开放平台 API" value="open_api" />
            <el-option label="浏览器 RPA" value="rpa" />
            <el-option label="App 云发布" value="cloud_app" />
          </el-select>
        </el-form-item>
        <el-form-item label="粉丝数">
          <el-input-number v-model="form.fans_count" :min="0" />
        </el-form-item>
      </template>
      <template v-else>
        <el-form-item label="账号昵称">
          <el-input v-model="form.nickname" />
        </el-form-item>
      </template>
      <el-form-item label="分组">
        <el-select v-model="form.group_id" clearable class="w-full">
          <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="运营人">
        <el-select v-model="form.operator_id" clearable class="w-full">
          <el-option v-for="m in members" :key="m.id" :label="m.nickname" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="网络区域">
        <el-input v-model="form.region" placeholder="如：广东深圳" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.note" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="formVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">{{ editing ? '保存' : '添加（mock 授权）' }}</el-button>
    </template>
  </el-dialog>

  <!-- 分组管理 -->
  <el-dialog v-model="groupDialogVisible" title="分组管理" width="440px">
    <div v-for="g in groups" :key="g.id" class="flex-between mb-2">
      <el-input v-model="g.name" class="w-56" />
      <el-button link type="danger" @click="removeGroup(g)">删除</el-button>
    </div>
    <div class="flex gap-2">
      <el-input v-model="newGroupName" placeholder="新分组名称" />
      <el-button @click="addGroup">添加</el-button>
    </div>
  </el-dialog>

  <!-- 代理表单 -->
  <el-dialog v-model="proxyVisible" :title="proxyForm.id ? '编辑代理' : '添加代理'" width="440px">
    <el-form :model="proxyForm" label-width="80px">
      <el-form-item label="名称"><el-input v-model="proxyForm.name" /></el-form-item>
      <el-form-item label="协议">
        <el-select v-model="proxyForm.scheme" class="w-full">
          <el-option label="http" value="http" />
          <el-option label="https" value="https" />
          <el-option label="socks5" value="socks5" />
        </el-select>
      </el-form-item>
      <el-form-item label="主机"><el-input v-model="proxyForm.host" /></el-form-item>
      <el-form-item label="端口"><el-input-number v-model="proxyForm.port" :min="1" :max="65535" /></el-form-item>
      <el-form-item label="用户名"><el-input v-model="proxyForm.username" /></el-form-item>
      <el-form-item label="密码"><el-input v-model="proxyForm.password" show-password /></el-form-item>
      <el-form-item label="归属地"><el-input v-model="proxyForm.region" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="proxyVisible = false">取消</el-button>
      <el-button type="primary" @click="saveProxy">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accountApi, proxyApi, userApi } from '@/api/modules'
import { fmtNum, fmtTime, platformLabel, statusTagType, STATUS_LABELS } from '@/utils/format'
import { PLATFORM_LABELS, type AccountGroup, type ProxyIP, type SocialAccount, type User } from '@/types'

const channelLabels: Record<string, string> = { open_api: '开放 API', rpa: 'RPA', cloud_app: '云发布' }
const tab = ref('accounts')
const loading = ref(false)
const saving = ref(false)
const rows = ref<SocialAccount[]>([])
const total = ref(0)
const query = reactive<Record<string, unknown>>({ page: 1, page_size: 20, platform: '', group_id: '', auth_status: '', keyword: '' })

const groups = ref<AccountGroup[]>([])
const members = ref<User[]>([])
const groupDialogVisible = ref(false)
const newGroupName = ref('')

const formVisible = ref(false)
const editing = ref<SocialAccount | null>(null)
const form = reactive<Record<string, unknown>>({})

const proxies = ref<ProxyIP[]>([])
const proxyVisible = ref(false)
const proxyForm = reactive<Record<string, unknown>>({ scheme: 'http', port: 8080 })

async function load(): Promise<void> {
  loading.value = true
  try {
    const params = Object.fromEntries(Object.entries(query).filter(([, v]) => v !== '' && v != null))
    const data = await accountApi.list(params)
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadMeta(): Promise<void> {
  const [g, m] = await Promise.all([accountApi.groups(), userApi.list()])
  groups.value = g
  members.value = m.items
}

function openCreate(): void {
  editing.value = null
  Object.assign(form, { platform: 'douyin', nickname: '', channel: 'open_api', fans_count: 0, group_id: null, operator_id: null, region: '', note: '' })
  formVisible.value = true
}

function openEdit(row: SocialAccount): void {
  editing.value = row
  Object.assign(form, { nickname: row.nickname, group_id: row.group_id, operator_id: row.operator_id, region: row.region, note: row.note })
  formVisible.value = true
}

async function save(): Promise<void> {
  saving.value = true
  try {
    if (editing.value) await accountApi.update(editing.value.id, form)
    else await accountApi.create(form)
    ElMessage.success('已保存')
    formVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row: SocialAccount): Promise<void> {
  await ElMessageBox.confirm(`确定删除账号「${row.nickname}」？`, '提示', { type: 'warning' })
  await accountApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

async function batchCheck(): Promise<void> {
  const data = await accountApi.batchCheck()
  ElMessage.success(`检测完成：共 ${data.total} 个，失效 ${data.expired} 个`)
  await load()
}

async function reAuth(row: SocialAccount): Promise<void> {
  await accountApi.reAuth(row.id)
  ElMessage.success('已重新授权')
  await load()
}

async function addGroup(): Promise<void> {
  if (!newGroupName.value.trim()) return
  await accountApi.createGroup({ name: newGroupName.value.trim() })
  newGroupName.value = ''
  await loadMeta()
}

async function removeGroup(g: AccountGroup): Promise<void> {
  await ElMessageBox.confirm(`删除分组「${g.name}」，其中账号将变为未分组`, '提示', { type: 'warning' })
  await accountApi.removeGroup(g.id)
  await loadMeta()
  await load()
}

async function loadProxies(): Promise<void> {
  proxies.value = (await proxyApi.list({ page: 1, page_size: 100 })).items
}

function openProxy(row?: ProxyIP): void {
  Object.assign(proxyForm, row ?? { id: null, name: '', scheme: 'http', host: '', port: 8080, username: '', password: '', region: '' })
  proxyVisible.value = true
}

async function saveProxy(): Promise<void> {
  if (proxyForm.id) await proxyApi.update(proxyForm.id as number, proxyForm)
  else await proxyApi.create(proxyForm)
  ElMessage.success('已保存')
  proxyVisible.value = false
  await loadProxies()
}

async function checkProxy(row: ProxyIP): Promise<void> {
  const data = await proxyApi.check(row.id)
  ElMessage[data.status === 'ok' ? 'success' : 'error'](data.status === 'ok' ? '代理连通' : '代理不可达')
  await loadProxies()
}

async function removeProxy(row: ProxyIP): Promise<void> {
  await ElMessageBox.confirm(`确定删除代理「${row.name}」？`, '提示', { type: 'warning' })
  await proxyApi.remove(row.id)
  await loadProxies()
}

onMounted(() => {
  void load()
  void loadMeta()
  void loadProxies()
})
</script>
