<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Collection,
  Connection,
  DataAnalysis,
  DataBoard,
  DocumentChecked,
  Files,
  Medal,
  Plus,
  Reading,
  SetUp,
  Setting,
} from '@element-plus/icons-vue'
import BackendSettingsDialog from './BackendSettingsDialog.vue'
import { useSettingsStore } from '@/stores/settings'

const route = useRoute()
const router = useRouter()
const settings = useSettingsStore()
const settingsVisible = ref(false)

const activeMenu = computed(() => {
  if (route.path === '/' || route.path.startsWith('/dashboard')) return '/'
  if (route.path.startsWith('/settings')) return '/settings'
  if (route.path.startsWith('/templates')) return '/templates'
  if (route.path.startsWith('/knowledge')) return '/knowledge'
  if (route.path.startsWith('/stats')) return '/stats'
  if (route.path.startsWith('/guide')) return '/guide'
  if (route.path.startsWith('/tasks/new')) return '/tasks/new'
  if (route.path.startsWith('/tasks')) return '/tasks'
  return '/'
})
const connectionLabel = computed(() => {
  if (settings.checking) return '正在检测'
  if (settings.isHealthy) return '服务正常'
  return '连接设置'
})

onMounted(() => {
  void settings.checkHealth().catch(() => undefined)
})

function navigate(path: string): void {
  void router.push(path)
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <button class="brand" type="button" aria-label="返回任务列表" @click="navigate('/')">
        <span class="brand-mark"><el-icon><DocumentChecked /></el-icon></span>
        <span>
          <strong>投标分析</strong>
          <small>Agent 工作台</small>
        </span>
      </button>

      <nav class="sidebar-nav" aria-label="主导航">
        <span class="nav-label">工作区</span>
        <button
          type="button"
          class="nav-item"
          :class="{ active: activeMenu === '/' }"
          @click="navigate('/')"
        >
          <el-icon><DataBoard /></el-icon>
          <span>工作台</span>
        </button>
        <button
          type="button"
          class="nav-item"
          :class="{ active: activeMenu === '/tasks' }"
          @click="navigate('/tasks')"
        >
          <el-icon><Files /></el-icon>
          <span>任务列表</span>
        </button>
        <button
          type="button"
          class="nav-item"
          :class="{ active: activeMenu === '/tasks/new' }"
          @click="navigate('/tasks/new')"
        >
          <el-icon><Plus /></el-icon>
          <span>新建任务</span>
        </button>
        <button
          type="button"
          class="nav-item"
          :class="{ active: activeMenu === '/guide' }"
          @click="navigate('/guide')"
        >
          <el-icon><Reading /></el-icon>
          <span>使用指南</span>
        </button>

        <span class="nav-label nav-label-secondary">配置</span>
        <button
          type="button"
          class="nav-item"
          :class="{ active: activeMenu === '/stats' }"
          @click="navigate('/stats')"
        >
          <el-icon><DataAnalysis /></el-icon>
          <span>统计与成本</span>
        </button>
        <button
          type="button"
          class="nav-item"
          :class="{ active: activeMenu === '/knowledge' }"
          @click="navigate('/knowledge')"
        >
          <el-icon><Medal /></el-icon>
          <span>资质知识库</span>
        </button>
        <button
          type="button"
          class="nav-item"
          :class="{ active: activeMenu === '/templates' }"
          @click="navigate('/templates')"
        >
          <el-icon><Collection /></el-icon>
          <span>解析模板</span>
        </button>
        <button
          type="button"
          class="nav-item"
          :class="{ active: activeMenu === '/settings' }"
          @click="navigate('/settings')"
        >
          <el-icon><SetUp /></el-icon>
          <span>系统设置</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <button class="connection-button" type="button" @click="settingsVisible = true">
          <span class="connection-icon"><el-icon><Connection /></el-icon></span>
          <span class="connection-text">
            <strong>{{ connectionLabel }}</strong>
            <small>{{ settings.displayBackendUrl }}</small>
          </span>
          <el-icon><Setting /></el-icon>
        </button>
      </div>
    </aside>

    <main class="main-panel">
      <slot />
    </main>

    <BackendSettingsDialog v-model:visible="settingsVisible" />
  </div>
</template>

<style scoped>
.app-shell {
  min-width: 900px;
  min-height: 100vh;
  background: var(--app-background);
}

.sidebar {
  position: fixed;
  z-index: 20;
  inset: 0 auto 0 0;
  display: flex;
  width: 224px;
  flex-direction: column;
  border-right: 1px solid var(--border-color);
  background: var(--surface-color);
}

.brand {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 84px;
  padding: 0 22px;
  border: 0;
  border-bottom: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
}

.brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  margin-right: 12px;
  place-items: center;
  border-radius: 7px;
  background: var(--primary-color);
  color: white;
  font-size: 20px;
}

.brand strong,
.brand small {
  display: block;
}

.brand strong {
  font-size: 16px;
  font-weight: 700;
}

.brand small {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.sidebar-nav {
  flex: 1;
  padding: 20px 12px;
}

.nav-label {
  display: block;
  padding: 0 10px 8px;
  color: var(--text-tertiary);
  font-size: 11px;
  font-weight: 600;
}

.nav-label-secondary {
  margin-top: 20px;
}

.nav-item {
  display: flex;
  align-items: center;
  width: 100%;
  height: 42px;
  margin-bottom: 4px;
  padding: 0 11px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.16s ease, color 0.16s ease;
}

.nav-item .el-icon {
  margin-right: 10px;
  font-size: 17px;
}

.nav-item:hover {
  background: var(--surface-muted);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--primary-soft);
  color: var(--primary-dark);
  font-weight: 600;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border-color);
}

.connection-button {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 54px;
  padding: 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  text-align: left;
}

.connection-button:hover {
  background: var(--surface-muted);
}

.connection-icon {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  margin-right: 8px;
  place-items: center;
  border-radius: 6px;
  background: var(--surface-strong);
  color: v-bind("settings.isHealthy ? 'var(--success-color)' : 'var(--text-tertiary)'");
}

.connection-text {
  min-width: 0;
  flex: 1;
}

.connection-text strong,
.connection-text small {
  display: block;
}

.connection-text strong {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.connection-text small {
  overflow: hidden;
  margin-top: 2px;
  color: var(--text-tertiary);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main-panel {
  min-height: 100vh;
  margin-left: 224px;
}
</style>
