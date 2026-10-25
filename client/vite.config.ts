import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import UnoCSS from 'unocss/vite'
import electron from 'vite-plugin-electron/simple'
import { defineConfig } from 'vite'

// WEB_ONLY=1 时仅启动 web 开发服务器（浏览器直接访问，不拉起 Electron）
const electronPlugins = process.env.WEB_ONLY ? [] : [electron({
  main: { entry: 'electron/main.ts' },
  preload: {
    input: fileURLToPath(new URL('./electron/preload.ts', import.meta.url)),
    // 插件默认 preload 输出 cjs 却命名 .mjs，ESM 包下必炸；这里覆盖为真 ESM
    vite: { build: { rollupOptions: { output: { format: 'es' } } } },
  },
})]

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    UnoCSS(),
    ...electronPlugins,
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      // 开发环境把 /api 代理到本地 server
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 2048,
  },
})
