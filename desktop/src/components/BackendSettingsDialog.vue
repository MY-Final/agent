<script setup lang="ts">
import { ref, watch } from 'vue'
import { Connection, CircleCheck, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { useSettingsStore } from '@/stores/settings'
import type { HealthData } from '@/types/api'

const visible = defineModel<boolean>('visible', { required: true })
const settings = useSettingsStore()
const candidateUrl = ref(settings.backendUrl)
const testResult = ref<HealthData | null>(null)

watch(visible, (value) => {
  if (value) {
    candidateUrl.value = settings.backendUrl
    testResult.value = settings.health
  }
})

async function testConnection(): Promise<void> {
  try {
    testResult.value = await settings.checkHealth(candidateUrl.value)
    ElMessage.success(testResult.value.status === 'healthy' ? '后端连接正常' : '后端可访问，但部分基础服务异常')
  } catch (error) {
    testResult.value = null
    ElMessage.error(getErrorMessage(error))
  }
}

function save(): void {
  settings.saveBackendUrl(candidateUrl.value)
  visible.value = false
  ElMessage.success('后端地址已保存')
  void settings.checkHealth().catch(() => undefined)
}
</script>

<template>
  <el-dialog v-model="visible" title="后端连接设置" width="520px" destroy-on-close>
    <div class="settings-copy">
      桌面端会把该地址保存在本机浏览器存储中。修改后，新的请求立即使用该地址。
    </div>

    <el-form label-position="top" @submit.prevent>
      <el-form-item label="后端地址">
        <el-input
          v-model="candidateUrl"
          placeholder="http://127.0.0.1:8000"
          :prefix-icon="Connection"
          clearable
        />
      </el-form-item>
    </el-form>

    <div v-if="testResult" class="health-grid">
      <div class="health-row">
        <span>API</span>
        <span :class="testResult.status === 'healthy' ? 'health-up' : 'health-down'">
          <el-icon><CircleCheck v-if="testResult.status === 'healthy'" /><Warning v-else /></el-icon>
          {{ testResult.status === 'healthy' ? '正常' : '异常' }}
        </span>
      </div>
      <div v-for="name in ['postgres', 'redis', 'minio'] as const" :key="name" class="health-row">
        <span>{{ name }}</span>
        <span :class="testResult[name] === 'up' ? 'health-up' : 'health-down'">
          {{ testResult[name] === 'up' ? '正常' : '异常' }}
        </span>
      </div>
    </div>

    <template #footer>
      <el-button :loading="settings.checking" @click="testConnection">测试连接</el-button>
      <el-button type="primary" :disabled="!candidateUrl.trim()" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.settings-copy {
  margin: -4px 0 20px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--surface-muted);
}

.health-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 42px;
  padding: 0 12px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 13px;
}

.health-row:nth-child(odd) {
  border-right: 1px solid var(--border-color);
}

.health-row:nth-last-child(-n + 2) {
  border-bottom: 0;
}

.health-up,
.health-down {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  font-weight: 600;
}

.health-up {
  color: var(--success-color);
}

.health-down {
  color: var(--danger-color);
}
</style>
