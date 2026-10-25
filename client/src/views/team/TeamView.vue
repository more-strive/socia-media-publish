<template>
  <el-tabs v-model="tab" @tab-change="onTab">
    <!-- 团队设置 -->
    <el-tab-pane label="团队设置" name="settings">
      <el-card shadow="never" class="max-w-640px">
        <el-form :model="teamForm" label-width="120px" v-loading="!loaded">
          <el-form-item label="团队名称">
            <el-input v-model="teamForm.name" class="w-64" />
          </el-form-item>
          <el-form-item label="发布前审核流">
            <el-switch v-model="teamForm.audit_enabled" />
            <span class="text-muted ml-2">开启后：内容需审核通过才能发布；运营创建的任务需审核员通过</span>
          </el-form-item>
          <el-form-item label="汇总推送 Webhook">
            <el-input v-model="teamForm.webhook_url" placeholder="飞书/钉钉自定义机器人地址" class="w-96" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="saveTeam">保存</el-button>
            <el-button @click="invite">邀请成员</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </el-tab-pane>

    <!-- 成员管理 -->
    <el-tab-pane label="成员管理" name="members">
      <el-table :data="members" class="page-card">
        <el-table-column label="成员" min-width="160">
          <template #default="{ row }">
            <el-avatar :size="28" class="mr-2">{{ row.nickname?.slice(0, 1) }}</el-avatar>{{ row.nickname }}
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column prop="email" label="邮箱" width="170" />
        <el-table-column label="角色" width="150">
          <template #default="{ row }">
            <el-select
              v-if="row.role !== 'owner' && auth.canManage"
              :model-value="row.role"
              size="small"
              @change="(v: string) => changeRole(row, v)"
            >
              <el-option label="管理员" value="admin" />
              <el-option label="运营" value="operator" />
              <el-option label="审核员" value="auditor" />
            </el-select>
            <el-tag v-else size="small">{{ ROLE_LABELS[row.role] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" width="160">
          <template #default="{ row }">{{ fmtTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.role !== 'owner' && auth.canManage" link type="danger" @click="removeMember(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="text-muted mt-2">席位：{{ seatsUsed }}/{{ team?.seats_total }}（扩容请到「订阅与账单」购买席位）</div>
    </el-tab-pane>

    <!-- 操作日志 -->
    <el-tab-pane label="操作日志" name="logs">
      <el-table :data="logs" class="page-card">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="成员" width="110">
          <template #default="{ row }">{{ memberName(row.user_id) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="操作" width="150" />
        <el-table-column label="详情" min-width="260">
          <template #default="{ row }">{{ row.detail ? JSON.stringify(row.detail) : '-' }}</template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="logQuery.page"
        :page-size="logQuery.page_size"
        :total="logTotal"
        layout="total, prev, pager, next"
        class="mt-3 justify-end"
        @current-change="loadLogs"
      />
    </el-tab-pane>
  </el-tabs>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { teamApi, userApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import { fmtTime } from '@/utils/format'
import { ROLE_LABELS, type AuditLog, type Team, type User } from '@/types'

const auth = useAuthStore()
const tab = ref('settings')
const loaded = ref(false)
const saving = ref(false)
const teamForm = reactive<Pick<Team, 'name' | 'audit_enabled' | 'webhook_url'>>({ name: '', audit_enabled: true, webhook_url: '' })

const members = ref<User[]>([])
const logs = ref<AuditLog[]>([])
const logTotal = ref(0)
const logQuery = reactive({ page: 1, page_size: 20 })

const team = computed(() => auth.team)
const seatsUsed = computed(() => members.value.length)

function memberName(id: number): string {
  return members.value.find((m) => m.id === id)?.nickname ?? `#${id}`
}

async function loadTeam(): Promise<void> {
  const data = await teamApi.get()
  Object.assign(teamForm, { name: data.name, audit_enabled: data.audit_enabled, webhook_url: data.webhook_url ?? '' })
  loaded.value = true
}

async function saveTeam(): Promise<void> {
  saving.value = true
  try {
    await teamApi.update(teamForm)
    ElMessage.success('已保存')
    await auth.fetchMe()
  } finally {
    saving.value = false
  }
}

async function invite(): Promise<void> {
  const data = await teamApi.invite()
  await ElMessageBox.alert(`邀请码：${data.invite_code}（7 天内有效）<br/>新成员注册后在登录页输入邀请码加入团队`, '邀请成员', {
    dangerouslyUseHTMLString: true,
  })
}

async function loadMembers(): Promise<void> {
  members.value = (await userApi.list(1, 100)).items
}

async function changeRole(row: User, role: string): Promise<void> {
  await userApi.updateRole(row.id, role)
  ElMessage.success('角色已更新')
  await loadMembers()
}

async function removeMember(row: User): Promise<void> {
  await ElMessageBox.confirm(`确定移除成员「${row.nickname}」？`, '提示', { type: 'warning' })
  await userApi.remove(row.id)
  ElMessage.success('已移除')
  await loadMembers()
}

async function loadLogs(): Promise<void> {
  const data = await teamApi.logs(logQuery.page, logQuery.page_size)
  logs.value = data.items
  logTotal.value = data.total
}

function onTab(): void {
  if (tab.value === 'settings') void loadTeam()
  else if (tab.value === 'members') void loadMembers()
  else void loadLogs()
}

onMounted(() => {
  void loadTeam()
  void loadMembers()
})
</script>
