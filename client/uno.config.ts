import { defineConfig, presetIcons, presetWind3 } from 'unocss'
import carbon from '@iconify-json/carbon/icons.json'

export default defineConfig({
  presets: [
    presetWind3(),
    // 显式注入图标集：presetIcons 的文件系统自动解析在当前环境不可用
    presetIcons({ scale: 1.2, warn: true, collections: { carbon: () => carbon } }),
  ],
  // 常用快捷类
  shortcuts: {
    'flex-center': 'flex items-center justify-center',
    'flex-between': 'flex items-center justify-between',
    'page-card': 'bg-white rounded-4px shadow-sm p-4',
    'text-muted': 'text-gray-400 text-13px',
  },
  theme: {
    colors: {
      primary: '#409eff',
    },
  },
})
