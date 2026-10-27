<template>
  <!-- RPA 自动发布引擎 -->
  <el-card shadow="never" class="mb-4">
    <div class="flex-between">
      <div>
        <span class="font-bold">RPA 自动发布引擎</span>
        <span class="text-muted ml-2 text-12px">抖音等无开放 API 平台由本机浏览器自动执行；先给 RPA 通道账号扫码绑定，再开启引擎；扫码/发布页面以顶部标签页打开</span>
      </div>
      <div class="flex items-center gap-3">
        <el-tag v-if="current" size="small" type="warning">执行中：{{ current.account.nickname }}</el-tag>
        <el-button
          v-if="pendingCount > 0 && !enabled"
          size="small" type="warning" :disabled="!canRun"
          @click="toggle(true)"
        >有 {{ pendingCount }} 条待执行，点击开启</el-button>
        <span v-if="!canRun" class="text-muted text-12px">仅桌面端可用</span>
        <el-switch :model-value="enabled" :disabled="!canRun" @change="toggle" />
      </div>
    </div>
    <div v-if="logs.length" class="mt-2 text-12px text-muted max-h-90px overflow-y-auto">
      <div v-for="(l, i) in logs.slice(0, 8)" :key="i">{{ l }}</div>
    </div>
  </el-card>

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
<el-button @click="probeAll">批量检测登录态</el-button>
        <div class="flex-1" />
        <el-button @click="groupDialogVisible = true">分组管理</el-button>
        <el-button type="primary" @click="openCreate">添加账号</el-button>
      </div>

      <el-table :data="rows" class="page-card" v-loading="loading">
        <el-table-column label="昵称" min-width="160">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <el-image v-if="row.avatar" :src="row.avatar" fit="cover" class="w-6 h-6 rounded-full shrink-0" />
              <span
                class="font-medium"
                :title="row.platform_account_id ? `平台 UID：${row.platform_account_id}` : undefined"
              >{{ row.nickname }}</span>
              <el-tag size="small">{{ platformLabel(row.platform) }}</el-tag>
            </div>
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
        <el-table-column label="代理" width="120">
          <template #default="{ row }">
            <span v-if="proxyNameOf(row)" class="text-12px">{{ proxyNameOf(row) }}</span>
            <span v-else class="text-muted text-12px">直连</span>
          </template>
        </el-table-column>
        <el-table-column label="最近检测" width="150">
          <template #default="{ row }">
            <div class="flex items-center gap-1">
              <span>{{ fmtTime(row.last_active_at) }}</span>
              <el-image
                v-if="row.last_probe_screenshot"
                :src="fileUrl(row.last_probe_screenshot)"
                :preview-src-list="[fileUrl(row.last_probe_screenshot)]"
                preview-teleported
                fit="cover"
                class="w-5 h-5 rounded cursor-pointer"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="isRpa(row.platform) && row.channel === 'rpa'" link type="success" @click="bind(row)">
              扫码绑定
            </el-button>
<el-button v-if="isRpa(row.platform) && row.channel === 'rpa'" link type="info" :disabled="probing.has(row.id)" @click="probe(row)">{{ probing.has(row.id) ? '检测中…' : '检测登录' }}</el-button>
            <el-button v-else-if="row.auth_status !== 'valid'" link type="warning" @click="reAuth(row)">重新授权</el-button>
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
          <el-input v-model="form.nickname" placeholder="选填；RPA 扫码成功后自动回填平台昵称" />
        </el-form-item>
        <el-form-item label="发布通道">
          <el-select v-model="form.channel" class="w-full">
            <el-option v-for="c in channelOptions" :key="c" :label="channelLabels[c] ?? c" :value="c" />
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
      <el-form-item label="绑定代理">
        <el-select v-model="form.proxy_id" clearable placeholder="不绑定则直连" class="w-full">
          <el-option v-for="px in proxies" :key="px.id" :label="px.name + ' · ' + px.host + ':' + px.port" :value="px.id" />
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
      <el-button type="primary" :loading="saving" @click="save">
        {{ editing ? '保存' : isRpa(form.platform) && form.channel === 'rpa' ? '添加并扫码绑定' : '添加（mock 授权）' }}
      </el-button>
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accountApi, proxyApi, userApi } from '@/api/modules'
import { usePlatforms } from '@/composables/usePlatforms'
import { useRpaEngine } from '@/composables/useRpaEngine'
import { fmtNum, fmtTime, platformLabel, statusTagType, STATUS_LABELS } from '@/utils/format'
import { PLATFORM_LABELS, type AccountGroup, type ProxyConfig, type ProxyIP, type SocialAccount, type User } from '@/types'

const rpa = useRpaEngine()
const { isRpa } = usePlatforms()
const { enabled, current, logs, canRun, pendingCount, toggle, bindPlatform, probeLogin } = rpa

const probing = ref<Set<number>>(new Set())
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
/** 有官方发布 API 的平台（公众号/TikTok/YouTube）；其余平台（抖音/快手/小红书等）无公开发布 API，只能走 RPA/云发布 */
const API_CHANNEL_PLATFORMS = new Set(['wechat_gzh', 'tiktok', 'youtube'])
// 依赖 form，必须声明在 form 之后（watch 注册即求值，提前会 TDZ 报错导致整页白屏）
const channelOptions = computed(() =>
  API_CHANNEL_PLATFORMS.has(String(form.platform)) ? ['open_api'] : ['rpa', 'cloud_app'],
)
// 切换平台后当前通道不可用时，回落到首个可用通道
watch(channelOptions, (opts) => {
  if (!opts.includes(String(form.channel))) form.channel = opts[0]
})

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
  Object.assign(form, { platform: 'douyin', nickname: '', channel: 'rpa', fans_count: 0, group_id: null, operator_id: null, proxy_id: null, region: '', note: '' })
  formVisible.value = true
}

function openEdit(row: SocialAccount): void {
  editing.value = row
  Object.assign(form, { nickname: row.nickname, group_id: row.group_id, operator_id: row.operator_id, proxy_id: row.proxy_id, region: row.region, note: row.note })
  formVisible.value = true
}

async function save(): Promise<void> {
  // RPA 扫码账号昵称选填：扫码前本就不知道是谁的号，扫成功后回填平台昵称
  // （只看通道选择，不依赖 isRpa 能力查询——网页端无 electron IPC 时同样放行，桌面端扫码后回填）
  const rpaCreate = !editing.value && form.channel === 'rpa'
  if (!editing.value && !String(form.nickname ?? '').trim() && !rpaCreate) {
    ElMessage.warning('请填写账号昵称')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await accountApi.update(editing.value.id, form)
      ElMessage.success('已保存')
      formVisible.value = false
      await load()
    } else {
      // 服务端要求昵称非空：RPA 留空时先占位，扫码回填时覆盖
      const payload = { ...form }
      if (rpaCreate && !String(payload.nickname ?? '').trim()) {
        payload.nickname = `${PLATFORM_LABELS[String(payload.platform)] ?? String(payload.platform)}·待识别`
      }
      const created = await accountApi.create(payload)
      formVisible.value = false
      await load()
      // RPA 渠道账号：创建后直接进入扫码绑定，并回填平台身份（昵称/UID/头像）
      if (isRpa(created.platform) && created.channel === 'rpa' && canRun.value) {
        ElMessage.info(`账号已创建，正在打开${platformLabel(created.platform)}扫码页（账号浏览器标签页）`)
        const res = await bindPlatform(created.platform, created.id, proxyOf(created))
        ElMessage[res.ok ? 'success' : 'warning'](res.message)
        if (res.ok) {
          await accountApi.reAuth(created.id).catch(() => undefined)
          await backfillIdentity(created.id, res)
        }
      } else {
        ElMessage.success('已保存')
      }
    }
  } finally {
    saving.value = false
  }
}

/** RPA 登录态探测：开标签页验证，并把结果与归档截图回写服务端 */
async function probe(row: SocialAccount): Promise<void> {
  if (!canRun.value) {
    ElMessage.warning('仅桌面端可用')
    return
  }
  probing.value = new Set(probing.value).add(row.id)
  try {
    const res = await probeLogin(row.platform, row.id, proxyOf(row))
    if (!res.ok) {
      ElMessage.warning(res.message)
      return
    }
    ElMessage[res.valid ? 'success' : 'warning'](res.message)
    await accountApi
      .update(row.id, {
        auth_status: res.valid ? 'valid' : 'expired',
        ...(res.screenshotUrl ? { last_probe_screenshot: res.screenshotUrl } : {}),
      })
      .catch(() => undefined)
    await load()
  } finally {
    const next = new Set(probing.value)
    next.delete(row.id)
    probing.value = next
  }
}
/** 账号绑定的代理 → 结构化配置（含认证账密；主进程 setProxy + 407 挑战应答） */
function proxyOf(row: SocialAccount): ProxyConfig | undefined {
  const p = proxies.value.find((x) => x.id === row.proxy_id)
  return p ? { scheme: p.scheme, host: p.host, port: p.port, username: p.username, password: p.password } : undefined
}

function proxyNameOf(row: SocialAccount): string | undefined {
  return proxies.value.find((x) => x.id === row.proxy_id)?.name
}

/** 截图归档 URL 是 /api 前缀的相对路径，展示时拼当前 origin（开发态走 vite 代理） */
function fileUrl(u: string): string {
  return /^https?:/.test(u) ? u : `${location.origin}${u}`
}

/** 批量探测当前页：逐个开页验证 RPA 账号登录态并回写（顺序执行，避免同时开 N 个标签页） */
async function probeAll(): Promise<void> {
  if (!canRun.value) {
    ElMessage.warning('仅桌面端可用')
    return
  }
  const targets = rows.value.filter((a) => isRpa(a.platform) && a.channel === 'rpa')
  if (!targets.length) {
    ElMessage.info('当前页没有 RPA 渠道账号')
    return
  }
  let valid = 0
  for (const row of targets) {
    probing.value = new Set(probing.value).add(row.id)
    try {
      // eslint-disable-next-line no-await-in-loop
      const res = await probeLogin(row.platform, row.id, proxyOf(row))
      if (res.ok) {
        if (res.valid) valid += 1
        await accountApi
          .update(row.id, {
            auth_status: res.valid ? 'valid' : 'expired',
            ...(res.screenshotUrl ? { last_probe_screenshot: res.screenshotUrl } : {}),
          })
          .catch(() => undefined)
      }
    } finally {
      const next = new Set(probing.value)
      next.delete(row.id)
      probing.value = next
    }
  }
  await load()
  ElMessage.success(`批量探测完成：${valid}/${targets.length} 个有效`)
}

/** 扫码成功后回填平台身份（UID/昵称/头像）；同一平台账号绑到别的记录时服务端报错由 http 层统一弹出 */
async function backfillIdentity(
  accountId: number,
  res: { nickname?: string; platformUid?: string; avatar?: string },
): Promise<void> {
  const patch: Record<string, unknown> = {}
  if (res.platformUid) patch.platform_account_id = res.platformUid
  if (res.nickname) patch.nickname = res.nickname
  if (res.avatar) patch.avatar = res.avatar
  if (!Object.keys(patch).length) return
  await accountApi.update(accountId, patch).catch(() => undefined)
  await load()
}

/** 已有 RPA 账号重新扫码绑定 */
async function bind(row: SocialAccount): Promise<void> {
  if (!canRun.value) {
    ElMessage.warning('仅桌面端可用')
    return
  }
  const res = await bindPlatform(row.platform, row.id, proxyOf(row))
  ElMessage[res.ok ? 'success' : 'warning'](res.message)
  if (res.ok) {
    await accountApi.reAuth(row.id).catch(() => undefined)
    await backfillIdentity(row.id, res)
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
  try {
    proxies.value = (await proxyApi.list({ page: 1, page_size: 100 })).items
  } catch {
    // 代理含凭据仅运营角色可见；无权限时账号相关功能退化为直连
    proxies.value = []
  }
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
