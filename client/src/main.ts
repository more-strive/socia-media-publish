import { createPinia } from 'pinia'
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
// 顺序敏感：reset 必须在 element-plus 之前——reset 的 [type=button]{background:transparent}
// 与 .el-button 同优先级，后引入者胜，会把实底按钮全部洗成透明（白底描边）效果
import '@unocss/reset/tailwind.css'
import 'element-plus/dist/index.css'
import 'virtual:uno.css'
import '@/styles/global.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
