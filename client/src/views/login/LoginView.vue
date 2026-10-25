<template>
  <div class="h-full flex-center bg-gradient-to-br from-blue-1 to-blue-3">
    <el-card class="w-400px" shadow="always">
      <div class="flex-center flex-col mb-4">
        <div class="i-carbon:analytics w-10 h-10 text-blue-5 mb-2" />
        <div class="text-20px font-bold">社媒矩阵运营平台</div>
        <div class="text-muted mt-1">矩阵管理 · 一键发布 · AI 创作 · 数据统计</div>
      </div>

      <el-tabs v-model="tab" stretch>
        <el-tab-pane label="密码登录" name="password">
          <el-form :model="pwdForm" label-position="top" @keyup.enter="doPwdLogin">
            <el-form-item label="手机号 / 邮箱">
              <el-input v-model="pwdForm.account" placeholder="13800000001" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="pwdForm.password" type="password" show-password placeholder="demo123456" />
            </el-form-item>
            <el-button type="primary" class="w-full" :loading="loading" @click="doPwdLogin">登 录</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="验证码登录" name="sms">
          <el-form :model="smsForm" label-position="top" @keyup.enter="doSmsLogin">
            <el-form-item label="手机号">
              <el-input v-model="smsForm.phone" placeholder="请输入手机号" />
            </el-form-item>
            <el-form-item label="验证码">
              <div class="flex w-full gap-2">
                <el-input v-model="smsForm.code" placeholder="6 位验证码" />
                <el-button :disabled="cooldown > 0" @click="sendSms">
                  {{ cooldown > 0 ? `${cooldown}s 后重发` : '获取验证码' }}
                </el-button>
              </div>
              <div v-if="devCode" class="text-muted mt-1">开发环境验证码：{{ devCode }}</div>
            </el-form-item>
            <el-button type="primary" class="w-full" :loading="loading" @click="doSmsLogin">登 录</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div class="text-center mt-2">
        <el-link type="primary" @click="registerVisible = true">没有账号？注册团队</el-link>
      </div>
    </el-card>

    <!-- 注册 -->
    <el-dialog v-model="registerVisible" title="注册（自动创建团队）" width="440px">
      <el-form :model="regForm" label-width="80px">
        <el-form-item label="手机号">
          <el-input v-model="regForm.phone" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="regForm.nickname" />
        </el-form-item>
        <el-form-item label="团队名称">
          <el-input v-model="regForm.team_name" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="regForm.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="registerVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="doRegister">注册并登录</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const tab = ref('password')
const loading = ref(false)
const registerVisible = ref(false)
const cooldown = ref(0)
const devCode = ref('')

const pwdForm = reactive({ account: '', password: '' })
const smsForm = reactive({ phone: '', code: '' })
const regForm = reactive({ phone: '', nickname: '', team_name: '', password: '' })

async function afterLogin(tokens: { access_token: string; refresh_token: string }): Promise<void> {
  auth.saveTokens(tokens.access_token, tokens.refresh_token)
  await auth.fetchMe()
  ElMessage.success(`欢迎回来，${auth.user?.nickname}`)
  router.push('/dashboard')
}

async function doPwdLogin(): Promise<void> {
  if (!pwdForm.account || !pwdForm.password) return void ElMessage.warning('请输入账号和密码')
  loading.value = true
  try {
    await afterLogin(await authApi.login(pwdForm.account, pwdForm.password))
  } finally {
    loading.value = false
  }
}

async function sendSms(): Promise<void> {
  if (!/^1\d{10}$/.test(smsForm.phone)) return void ElMessage.warning('请输入正确手机号')
  const data = await authApi.smsSend(smsForm.phone)
  if (data.code) devCode.value = data.code
  cooldown.value = 60
  const timer = setInterval(() => {
    cooldown.value--
    if (cooldown.value <= 0) clearInterval(timer)
  }, 1000)
}

async function doSmsLogin(): Promise<void> {
  if (!smsForm.phone || !smsForm.code) return void ElMessage.warning('请输入手机号和验证码')
  loading.value = true
  try {
    await afterLogin(await authApi.smsLogin(smsForm.phone, smsForm.code))
  } finally {
    loading.value = false
  }
}

async function doRegister(): Promise<void> {
  if (!regForm.phone || !regForm.nickname || !regForm.team_name || regForm.password.length < 8) {
    return void ElMessage.warning('请完整填写，密码至少 8 位')
  }
  loading.value = true
  try {
    await afterLogin(await authApi.register(regForm))
    registerVisible.value = false
  } finally {
    loading.value = false
  }
}
</script>
