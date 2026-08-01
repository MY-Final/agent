import { createApp } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './styles/base.css'

import App from './App.vue'
import router from './router'
import { BACKEND_URL_KEY, normalizeBackendUrl } from './utils/settings'

async function resolveDynamicBackendUrl(): Promise<void> {
  try {
    const dynamicUrl = await invoke<string | null>('get_backend_url')
    if (dynamicUrl) {
      localStorage.setItem(BACKEND_URL_KEY, normalizeBackendUrl(dynamicUrl))
    }
  } catch {
    // 纯 Web 调试或侧车不可用时忽略，继续使用默认后端地址。
  }
}

async function bootstrap(): Promise<void> {
  await resolveDynamicBackendUrl()
  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.use(ElementPlus, { locale: zhCn })
  app.mount('#app')
}

void bootstrap()
