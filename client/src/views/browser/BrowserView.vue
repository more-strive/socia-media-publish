<template>
  <div class="flex flex-col h-full">
    <!-- 标签条 -->
    <div class="flex items-center gap-2 mb-2 flex-wrap flex-shrink-0">
      <div
        v-for="t in tabs"
        :key="t.id"
        class="tab-chip"
        :class="{ 'tab-chip-active': t.id === activeId }"
        @click="activate(t.id)"
      >
        <span class="truncate max-w-160px">{{ t.title }}</span>
        <el-icon class="ml-1 flex-shrink-0" @click.stop="close(t.id)"><Close /></el-icon>
      </div>
      <span v-if="!tabs.length" class="text-muted text-13px">
        暂无打开的第三方页面——RPA 扫码登录、自动发布会在右侧以标签页打开
      </span>
      <div class="flex-1" />
      <el-button v-if="tabs.length" link type="danger" size="small" @click="closeAll">关闭全部</el-button>
    </div>

    <!-- 页面容器：区域实时上报给主进程，WebContentsView 覆盖在此 -->
    <div ref="host" class="flex-1 min-h-0 bg-white rounded-4px border border-solid border-gray-200 overflow-hidden" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Close } from '@element-plus/icons-vue'

interface TabItem {
  id: number
  title: string
  url: string
}

const host = ref<HTMLElement>()
const tabs = ref<TabItem[]>([])
const activeId = ref<number | null>(null)

/** 把容器在窗口内的位置（DIP=CSS px）上报主进程；元素不在时传 null 隐藏全部标签 */
function sendRect(): void {
  const el = host.value
  const r = el?.getBoundingClientRect()
  void window.electronAPI?.tabs?.rect(
    r && r.width > 0
      ? { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) }
      : null,
  )
}

function activate(id: number): void {
  void window.electronAPI?.tabs?.activate(id)
}

function close(id: number): void {
  void window.electronAPI?.tabs?.close(id)
}

function closeAll(): void {
  for (const t of tabs.value) close(t.id)
}

let ro: ResizeObserver | undefined
let unsubscribe: (() => void) | undefined

onMounted(() => {
  void window.electronAPI?.tabs?.state().then((s) => {
    tabs.value = s.tabs
    activeId.value = s.activeId
    requestAnimationFrame(sendRect)
  })
  unsubscribe = window.electronAPI?.tabs?.onChanged((s) => {
    tabs.value = s.tabs
    activeId.value = s.activeId
    requestAnimationFrame(sendRect)
  })
  if (host.value) {
    ro = new ResizeObserver(() => sendRect())
    ro.observe(host.value)
  }
  window.addEventListener('resize', sendRect)
})

onUnmounted(() => {
  ro?.disconnect()
  window.removeEventListener('resize', sendRect)
  unsubscribe?.()
  void window.electronAPI?.tabs?.rect(null) // 离开页面：隐藏覆盖层，标签后台保活
})
</script>

<style scoped>
.tab-chip {
  display: flex;
  align-items: center;
  padding: 4px 10px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  background: #fff;
  max-width: 240px;
}
.tab-chip-active {
  color: #409eff;
  border-color: #409fffaa;
  background: #ecf5ff;
}
</style>
