<template>
  <div class="flex flex-col gap-4">
    <!-- 筛选 -->
    <div class="page-card flex flex-wrap gap-3 items-center">
      <el-date-picker
        v-model="range"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        :clearable="false"
      />
      <el-button type="primary" @click="load">查询</el-button>
      <div class="flex-1" />
      <el-button @click="doExport">导出 CSV</el-button>
      <el-button :loading="pushing" @click="doPush">推送昨日汇总到飞书/钉钉</el-button>
    </div>

    <!-- 汇总卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div v-for="c in summaryCards" :key="c.label" class="page-card">
        <div class="text-muted">{{ c.label }}</div>
        <div class="text-24px font-bold mt-1">{{ c.value }}</div>
      </div>
    </div>

    <!-- 趋势图 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <el-card shadow="never" header="粉丝增长趋势">
        <div ref="fansChartEl" class="h-320px" />
      </el-card>
      <el-card shadow="never" header="播放 / 点赞趋势（全账号汇总）">
        <div ref="viewsChartEl" class="h-320px" />
      </el-card>
    </div>

    <!-- 账号明细 -->
    <el-card shadow="never" header="账号数据明细">
      <el-table :data="accountRows">
        <el-table-column label="账号" min-width="160">
          <template #default="{ row }">
            <el-tag size="small" class="mr-2">{{ platformLabel(row.platform) }}</el-tag>{{ row.nickname }}
          </template>
        </el-table-column>
        <el-table-column label="粉丝总量" width="110">
          <template #default="{ row }">{{ fmtNum(row.followers) }}</template>
        </el-table-column>
        <el-table-column label="新增粉丝" width="110">
          <template #default="{ row }">{{ sum(row, 'new_followers') }}</template>
        </el-table-column>
        <el-table-column label="播放" width="110">
          <template #default="{ row }">{{ fmtNum(sum(row, 'views')) }}</template>
        </el-table-column>
        <el-table-column label="点赞" width="110">
          <template #default="{ row }">{{ fmtNum(sum(row, 'likes')) }}</template>
        </el-table-column>
        <el-table-column label="评论" width="110">
          <template #default="{ row }">{{ fmtNum(sum(row, 'comments')) }}</template>
        </el-table-column>
        <el-table-column label="分享" width="110">
          <template #default="{ row }">{{ fmtNum(sum(row, 'shares')) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 作品排行 -->
    <el-card shadow="never" header="作品数据排行（按播放量）">
      <el-table :data="contentRows">
        <el-table-column prop="content_id" label="任务" width="80" />
        <el-table-column label="账号" width="170">
          <template #default="{ row }">{{ accountName(row.account_id) }}</template>
        </el-table-column>
        <el-table-column label="播放" width="100">
          <template #default="{ row }">{{ fmtNum(row.views) }}</template>
        </el-table-column>
        <el-table-column label="点赞" width="100">
          <template #default="{ row }">{{ fmtNum(row.likes) }}</template>
        </el-table-column>
        <el-table-column label="评论" width="100">
          <template #default="{ row }">{{ fmtNum(row.comments) }}</template>
        </el-table-column>
        <el-table-column label="发布时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column label="链接" width="80">
          <template #default="{ row }">
            <el-link v-if="row.publish_url" type="primary" :href="row.publish_url" target="_blank">查看</el-link>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { accountApi, statsApi } from '@/api/modules'
import { fmtNum, fmtTime, platformLabel } from '@/utils/format'
import type { AccountStat, SocialAccount } from '@/types'

function dayOffset(offset: number): string {
  return new Date(Date.now() - offset * 86400000).toISOString().slice(0, 10)
}

const range = ref<[string, string]>([dayOffset(29), dayOffset(0)])
const accountRows = ref<AccountStat[]>([])
const contentRows = ref<{ account_id: number; publish_url: string | null; views: number; likes: number; comments: number; published_at: string | null; content_id: number }[]>([])
const accountMap = ref<Record<number, SocialAccount>>({})
const pushing = ref(false)

const fansChartEl = ref<HTMLElement>()
const viewsChartEl = ref<HTMLElement>()
let fansChart: echarts.ECharts | null = null
let viewsChart: echarts.ECharts | null = null

const summaryCards = computed(() => {
  const all = accountRows.value
  const sumOf = (key: 'new_followers' | 'views' | 'likes' | 'comments' | 'shares') =>
    all.reduce((acc, a) => acc + a.series.reduce((s, p) => s + (p[key] as number), 0), 0)
  const followers = all.reduce((acc, a) => acc + a.followers, 0)
  return [
    { label: '账号数', value: all.length },
    { label: '总粉丝', value: fmtNum(followers) },
    { label: '新增粉丝', value: fmtNum(sumOf('new_followers')) },
    { label: '总播放', value: fmtNum(sumOf('views')) },
    { label: '总点赞', value: fmtNum(sumOf('likes')) },
  ]
})

function sum(row: AccountStat, key: 'new_followers' | 'views' | 'likes' | 'comments' | 'shares'): number {
  return row.series.reduce((s, p) => s + (p[key] as number), 0)
}

function accountName(id: number): string {
  const a = accountMap.value[id]
  return a ? `${platformLabel(a.platform)} · ${a.nickname}` : `账号#${id}`
}

function renderCharts(): void {
  const rows = accountRows.value
  const dates = [...new Set(rows.flatMap((a) => a.series.map((p) => p.date)))].sort()
  const sumByDate = (key: 'new_followers' | 'views' | 'likes') =>
    dates.map(
      (d) => rows.reduce((acc, a) => acc + (a.series.find((p) => p.date === d)?.[key] ?? 0), 0),
    )

  if (fansChartEl.value) {
    fansChart ??= echarts.init(fansChartEl.value)
    fansChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: { type: 'category', data: dates },
      yAxis: { type: 'value' },
      series: [{ name: '新增粉丝', type: 'line', smooth: true, areaStyle: { opacity: 0.15 }, data: sumByDate('new_followers') }],
    })
  }
  if (viewsChartEl.value) {
    viewsChart ??= echarts.init(viewsChartEl.value)
    viewsChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['播放', '点赞'] },
      grid: { left: 50, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: dates },
      yAxis: { type: 'value' },
      series: [
        { name: '播放', type: 'bar', data: sumByDate('views') },
        { name: '点赞', type: 'line', smooth: true, data: sumByDate('likes') },
      ],
    })
  }
}

async function load(): Promise<void> {
  const [start, end] = range.value
  const [stats, contents, accounts] = await Promise.all([
    statsApi.accounts({ start, end }),
    statsApi.contents({ start, end, limit: 50 }),
    accountApi.list({ page: 1, page_size: 200 }),
  ])
  accountRows.value = stats
  contentRows.value = contents as typeof contentRows.value
  accountMap.value = Object.fromEntries(accounts.items.map((a) => [a.id, a]))
  renderCharts()
}

async function doExport(): Promise<void> {
  const [start, end] = range.value
  await statsApi.export(start, end)
  ElMessage.success('已导出')
}

async function doPush(): Promise<void> {
  pushing.value = true
  try {
    const data = await statsApi.push()
    ElMessage.success(`已推送：${data.text.slice(0, 30)}...`)
  } finally {
    pushing.value = false
  }
}

function onResize(): void {
  fansChart?.resize()
  viewsChart?.resize()
}

onMounted(() => {
  void load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  fansChart?.dispose()
  viewsChart?.dispose()
})
</script>
