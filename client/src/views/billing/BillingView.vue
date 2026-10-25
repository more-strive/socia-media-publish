<template>
  <el-tabs v-model="tab" @tab-change="onTab">
    <!-- 套餐订阅 -->
    <el-tab-pane label="套餐与订阅" name="plans">
      <el-descriptions v-if="subscription" :column="4" border class="mb-4" size="small">
        <el-descriptions-item label="当前套餐">{{ subscription.plan?.name ?? '未订阅' }}</el-descriptions-item>
        <el-descriptions-item label="到期时间">{{ fmtTime(subscription.plan_expire_at, false) }}</el-descriptions-item>
        <el-descriptions-item label="席位">{{ subscription.seats_used }}/{{ subscription.seats_total }}</el-descriptions-item>
        <el-descriptions-item label="AI 积分">{{ subscription.credits }}</el-descriptions-item>
      </el-descriptions>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <el-card v-for="p in plans" :key="p.id" shadow="hover" :class="{ 'border-primary!': p.code === 'pro' }">
          <div class="flex-between">
            <span class="font-bold text-16px">{{ p.name }}</span>
            <el-tag v-if="subscription?.plan?.id === p.id" type="success" size="small">当前套餐</el-tag>
          </div>
          <div class="my-3">
            <span class="text-28px font-bold text-orange-5">¥{{ p.price_monthly }}</span>
            <span class="text-muted">/月</span>
            <span class="text-muted ml-2">¥{{ p.price_yearly }}/年</span>
          </div>
          <div class="text-muted mb-3">{{ p.seats }} 席位 · {{ p.accounts }} 账号 · {{ p.credits_monthly }} 积分/月</div>
          <div v-for="f in p.features || []" :key="f" class="flex items-center gap-1 text-13px py-0.5">
            <el-icon color="#67c23a"><Select /></el-icon>{{ f }}
          </div>
          <div class="flex gap-2 mt-4">
            <el-button type="primary" size="small" @click="subscribe(p, 'new')">新购</el-button>
            <el-button size="small" @click="subscribe(p, 'renew')">续费</el-button>
          </div>
        </el-card>
      </div>

      <div class="page-card mt-4 flex gap-3 items-center">
        <span>增值购买：</span>
        <el-button @click="buy('seats')">+1 席位（¥99）</el-button>
        <el-button @click="buy('credits')">+1000 积分（¥100）</el-button>
        <span class="text-muted">点击创建订单后，在「订单」标签页完成支付</span>
      </div>
    </el-tab-pane>

    <!-- 订单 -->
    <el-tab-pane label="订单" name="orders">
      <el-table :data="orders" class="page-card">
        <el-table-column prop="order_no" label="订单号" width="170" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ orderTypeLabels[row.type] }}</template>
        </el-table-column>
        <el-table-column label="数量" width="70">
          <template #default="{ row }">{{ row.quantity }}</template>
        </el-table-column>
        <el-table-column label="金额" width="100">
          <template #default="{ row }">¥{{ row.amount }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ STATUS_LABELS[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'unpaid'" link type="success" @click="pay(row)">模拟支付</el-button>
            <el-button v-if="row.status === 'paid' && auth.canManage" link type="primary" @click="openInvoice(row)">申请开票</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="orderQuery.page"
        :page-size="orderQuery.page_size"
        :total="orderTotal"
        layout="total, prev, pager, next"
        class="mt-3 justify-end"
        @current-change="loadOrders"
      />
    </el-tab-pane>

    <!-- 发票 -->
    <el-tab-pane label="发票" name="invoices">
      <el-table :data="invoices" class="page-card">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="抬头" min-width="160" />
        <el-table-column prop="tax_no" label="税号" min-width="140" />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">{{ row.type === 'vat' ? '专票' : '普票' }}</template>
        </el-table-column>
        <el-table-column label="金额" width="100">
          <template #default="{ row }">¥{{ row.amount }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'issued' ? 'success' : 'warning'">
              {{ row.status === 'issued' ? '已开具' : '处理中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="申请时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="PDF" width="80">
          <template #default="{ row }">
            <el-link v-if="row.file_url" type="primary" :href="row.file_url" target="_blank">下载</el-link>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>

  <!-- 开票 -->
  <el-dialog v-model="invoiceVisible" title="申请开票" width="440px">
    <el-form :model="invoiceForm" label-width="90px">
      <el-form-item label="订单">{{ invoiceForm.order_no }}（¥{{ invoiceForm.amount }}）</el-form-item>
      <el-form-item label="发票抬头">
        <el-input v-model="invoiceForm.title" />
      </el-form-item>
      <el-form-item label="税号">
        <el-input v-model="invoiceForm.tax_no" />
      </el-form-item>
      <el-form-item label="类型">
        <el-radio-group v-model="invoiceForm.type">
          <el-radio value="normal">普通发票</el-radio>
          <el-radio value="vat">增值税专票</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="invoiceVisible = false">取消</el-button>
      <el-button type="primary" @click="saveInvoice">提交</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Select } from '@element-plus/icons-vue'
import { billingApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import { fmtTime, statusTagType, STATUS_LABELS } from '@/utils/format'
import type { Invoice, Order, Plan } from '@/types'

const auth = useAuthStore()
const tab = ref('plans')
const orderTypeLabels: Record<string, string> = { new: '新购', renew: '续费', upgrade: '升级', seats: '席位', credits: '积分包' }

const plans = ref<Plan[]>([])
const subscription = ref<Awaited<ReturnType<typeof billingApi.subscription>> | null>(null)

const orders = ref<Order[]>([])
const orderTotal = ref(0)
const orderQuery = reactive({ page: 1, page_size: 20 })

const invoices = ref<Invoice[]>([])

const invoiceVisible = ref(false)
const invoiceForm = reactive<Record<string, unknown>>({ type: 'normal' })

async function loadPlans(): Promise<void> {
  const [p, s] = await Promise.all([billingApi.plans(), billingApi.subscription()])
  plans.value = p
  subscription.value = s
}

async function loadOrders(): Promise<void> {
  const data = await billingApi.orders(orderQuery.page, orderQuery.page_size)
  orders.value = data.items
  orderTotal.value = data.total
}

async function loadInvoices(): Promise<void> {
  invoices.value = (await billingApi.invoices(1, 100)).items
}

function onTab(): void {
  if (tab.value === 'plans') void loadPlans()
  else if (tab.value === 'orders') void loadOrders()
  else void loadInvoices()
}

async function subscribe(p: Plan, type: 'new' | 'renew'): Promise<void> {
  const { value } = await ElMessageBox.prompt(`购买套餐「${p.name}」，输入月数（¥${p.price_monthly}/月）`, '确认下单', {
    inputValue: '1',
    inputPattern: /^[1-9]\d*$/,
    inputErrorMessage: '请输入正整数',
  })
  const order = await billingApi.createOrder({ type, plan_id: p.id, quantity: Number(value) })
  ElMessage.success(`订单已创建：${order.order_no}，请到「订单」页支付`)
  await loadOrders()
}

async function buy(type: 'seats' | 'credits'): Promise<void> {
  const order = await billingApi.createOrder({ type, quantity: 1 })
  ElMessage.success(`订单已创建：${order.order_no}`)
  await loadOrders()
}

async function pay(row: Order): Promise<void> {
  await billingApi.mockPay(row.id)
  ElMessage.success('支付成功，已生效')
  await Promise.all([loadOrders(), loadPlans()])
}

function openInvoice(row: Order): void {
  Object.assign(invoiceForm, { order_id: row.id, order_no: row.order_no, amount: row.amount, title: '', tax_no: '', type: 'normal' })
  invoiceVisible.value = true
}

async function saveInvoice(): Promise<void> {
  if (!(invoiceForm.title as string)?.trim()) return void ElMessage.warning('请填写发票抬头')
  await billingApi.createInvoice(invoiceForm)
  ElMessage.success('开票申请已提交')
  invoiceVisible.value = false
  await loadInvoices()
}

onMounted(() => {
  void loadPlans()
  void loadOrders()
})
</script>
