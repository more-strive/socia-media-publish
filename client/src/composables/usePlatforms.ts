import { ref } from 'vue'

/** 已接入 RPA 的平台清单（来自主进程适配器注册表，视图据此判断平台能力，替代 platform === 'douyin' 硬编码） */
const platforms = ref<string[]>([])
let loading = false

export function usePlatforms() {
  if (!loading && window.electronAPI?.platforms?.list) {
    loading = true
    void window.electronAPI.platforms
      .list()
      .then((codes) => {
        platforms.value = codes
      })
      .catch(() => undefined)
  }
  /** 表单里的 platform 可能是未收窄的 unknown，这里统一收窄 */
  const isRpa = (platform: unknown): boolean =>
    typeof platform === 'string' && platforms.value.includes(platform)
  return { platforms, isRpa }
}
