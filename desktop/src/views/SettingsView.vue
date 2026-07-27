<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  CircleCheck,
  Connection,
  Delete,
  Edit,
  Key,
  Plus,
  Refresh,
  Select,
  Timer,
  Warning,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { llmSettingsApi } from '@/api/settings'
import LLMProviderDialog from '@/components/LLMProviderDialog.vue'
import { useSettingsStore } from '@/stores/settings'
import type {
  LLMProvider,
  LLMProviderCreateInput,
  LLMProviderUpdateInput,
} from '@/types/llm'
import { formatDate } from '@/utils/format'

const settings = useSettingsStore()
const dialogVisible = ref(false)
const editingProvider = ref<LLMProvider | null>(null)
const saving = ref(false)
const actionId = ref<string | null>(null)

const currentConfig = computed(() => settings.currentLLMConfig)
const sourceLabel = computed(() => currentConfig.value?.source === 'database' ? '数据库默认配置' : '.env 备用配置')
const currentProviderName = computed(() => {
  if (!currentConfig.value) return '-'
  return currentConfig.value.provider_name || (currentConfig.value.source === 'env' ? '环境变量配置' : '未命名提供商')
})

async function loadSettings(showMessage = false): Promise<void> {
  try {
    await settings.loadLLMSettings()
    if (showMessage) ElMessage.success('大模型设置已刷新')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function openCreateDialog(): void {
  editingProvider.value = null
  dialogVisible.value = true
}

function openEditDialog(provider: LLMProvider): void {
  editingProvider.value = provider
  dialogVisible.value = true
}

async function saveProvider(payload: LLMProviderCreateInput | LLMProviderUpdateInput): Promise<void> {
  saving.value = true
  try {
    if (editingProvider.value) {
      await llmSettingsApi.updateProvider(editingProvider.value.id, payload as LLMProviderUpdateInput)
      ElMessage.success('大模型提供商已更新')
    } else {
      await llmSettingsApi.createProvider(payload as LLMProviderCreateInput)
      ElMessage.success('大模型提供商已新增')
    }
    dialogVisible.value = false
    await settings.loadLLMSettings()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function setDefault(provider: LLMProvider): Promise<void> {
  actionId.value = provider.id
  try {
    await llmSettingsApi.setDefault(provider.id)
    ElMessage.success(`“${provider.name}”已设为默认提供商`)
    await settings.loadLLMSettings()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionId.value = null
  }
}

async function toggleProvider(provider: LLMProvider, enabled: boolean): Promise<void> {
  try {
    if (!enabled && provider.is_default) {
      await ElMessageBox.confirm(
        `禁用“${provider.name}”后，系统会取消其默认状态并回退到 .env 配置。`,
        '确认禁用默认提供商',
        { type: 'warning', confirmButtonText: '确认禁用', cancelButtonText: '取消' },
      )
    }
    actionId.value = provider.id
    await llmSettingsApi.updateProvider(provider.id, { is_enabled: enabled })
    ElMessage.success(enabled ? '提供商已启用' : '提供商已禁用')
    await settings.loadLLMSettings()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getErrorMessage(error))
  } finally {
    actionId.value = null
  }
}

async function deleteProvider(provider: LLMProvider): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `删除“${provider.name}”后无法恢复，保存的 API Key 也会一并清除。`,
      '确认删除提供商',
      { type: 'warning', confirmButtonText: '删除提供商', cancelButtonText: '取消' },
    )
    actionId.value = provider.id
    await llmSettingsApi.removeProvider(provider.id)
    ElMessage.success('大模型提供商已删除')
    await settings.loadLLMSettings()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getErrorMessage(error))
  } finally {
    actionId.value = null
  }
}

onMounted(() => loadSettings())
</script>

<template>
  <div class="page-container settings-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">系统设置</h1>
        <p class="page-subtitle">管理标书解析使用的大模型服务。数据库默认配置优先于后端 .env 配置。</p>
      </div>
      <div class="page-actions">
        <el-button :icon="Refresh" :loading="settings.llmLoading" @click="loadSettings(true)">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增提供商</el-button>
      </div>
    </header>

    <section class="content-surface current-section" v-loading="settings.llmLoading && !currentConfig">
      <div class="section-heading">
        <div>
          <h2 class="section-title">当前生效配置</h2>
          <p class="section-subtitle">解析 Skill 会在每次调用前读取此配置，无需重启后端。</p>
        </div>
        <el-tag v-if="currentConfig" :type="currentConfig.is_configured ? 'success' : 'danger'" effect="plain">
          {{ currentConfig.is_configured ? '已配置' : '缺少 API Key' }}
        </el-tag>
      </div>

      <div v-if="currentConfig" class="runtime-layout">
        <div class="runtime-identity">
          <span class="runtime-icon"><el-icon><Connection /></el-icon></span>
          <div>
            <strong>{{ currentProviderName }}</strong>
            <span>{{ sourceLabel }}</span>
          </div>
        </div>
        <dl class="runtime-facts">
          <div>
            <dt>默认模型</dt>
            <dd>{{ currentConfig.default_model || '-' }}</dd>
          </div>
          <div>
            <dt>服务地址</dt>
            <dd :title="currentConfig.base_url || '-'">{{ currentConfig.base_url || '-' }}</dd>
          </div>
          <div>
            <dt>API Key</dt>
            <dd class="secret-value">{{ currentConfig.api_key || '未配置' }}</dd>
          </div>
          <div>
            <dt>请求超时</dt>
            <dd>{{ currentConfig.timeout_seconds }} 秒</dd>
          </div>
        </dl>
      </div>

      <el-empty v-else-if="!settings.llmLoading" description="暂时无法读取当前大模型配置" :image-size="72" />
    </section>

    <section class="content-surface providers-section">
      <div class="section-heading provider-heading">
        <div>
          <h2 class="section-title">大模型提供商</h2>
          <p class="section-subtitle">API Key 只会显示脱敏值；编辑提供商时留空即可保留原密钥。</p>
        </div>
        <span class="provider-count">{{ settings.llmProviders.length }} 个配置</span>
      </div>

      <el-table v-loading="settings.llmLoading" :data="settings.llmProviders" row-key="id">
        <el-table-column label="提供商" min-width="190">
          <template #default="scope">
            <div class="provider-name-cell">
              <span class="provider-mark"><el-icon><Key /></el-icon></span>
              <div>
                <strong>{{ scope.row.name }}</strong>
                <small>OpenAI 兼容接口</small>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="调用配置" min-width="260">
          <template #default="scope">
            <div class="config-cell">
              <strong>{{ scope.row.default_model }}</strong>
              <small :title="scope.row.base_url">{{ scope.row.base_url }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="密钥" width="170">
          <template #default="scope"><span class="secret-value">{{ scope.row.api_key }}</span></template>
        </el-table-column>
        <el-table-column label="超时" width="95" align="center">
          <template #default="scope">
            <span class="timeout-value"><el-icon><Timer /></el-icon>{{ scope.row.timeout_seconds }}s</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="85" align="center">
          <template #default="scope">
            <el-switch
              :model-value="scope.row.is_enabled"
              :loading="actionId === scope.row.id"
              @change="(value) => toggleProvider(scope.row, Boolean(value))"
            />
          </template>
        </el-table-column>
        <el-table-column label="默认配置" width="130" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.is_default" type="success" effect="plain">
              <el-icon><CircleCheck /></el-icon>
              当前默认
            </el-tag>
            <el-button
              v-else
              link
              type="primary"
              :icon="Select"
              :disabled="!scope.row.is_enabled || actionId === scope.row.id"
              @click="setDefault(scope.row)"
            >
              设为默认
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="165">
          <template #default="scope">{{ formatDate(scope.row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="scope">
            <el-tooltip content="编辑提供商" placement="top">
              <el-button text :icon="Edit" aria-label="编辑提供商" @click="openEditDialog(scope.row)" />
            </el-tooltip>
            <el-tooltip :content="scope.row.is_default ? '请先切换默认提供商' : '删除提供商'" placement="top">
              <span>
                <el-button
                  text
                  type="danger"
                  :icon="Delete"
                  :disabled="scope.row.is_default"
                  :loading="actionId === scope.row.id"
                  aria-label="删除提供商"
                  @click="deleteProvider(scope.row)"
                />
              </span>
            </el-tooltip>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有数据库提供商配置">
            <div class="empty-actions">
              <p>当前会继续使用后端 .env 中的备用配置。</p>
              <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增第一个提供商</el-button>
            </div>
          </el-empty>
        </template>
      </el-table>
    </section>

    <div class="settings-note">
      <el-icon><Warning /></el-icon>
      <span>切换默认提供商只影响后续的大模型请求，已经完成的解析结果不会重新生成。</span>
    </div>

    <LLMProviderDialog
      v-model:visible="dialogVisible"
      :provider="editingProvider"
      :saving="saving"
      @submit="saveProvider"
    />
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 1540px;
}

.current-section,
.providers-section {
  overflow: hidden;
}

.current-section {
  min-height: 180px;
  margin-bottom: 16px;
}

.section-heading {
  display: flex;
  min-height: 70px;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color);
}

.runtime-layout {
  display: grid;
  grid-template-columns: minmax(210px, 0.8fr) minmax(0, 2.2fr);
  min-height: 108px;
  align-items: stretch;
}

.runtime-identity {
  display: flex;
  align-items: center;
  padding: 20px;
  border-right: 1px solid var(--border-color);
  background: var(--surface-muted);
}

.runtime-icon,
.provider-mark {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 6px;
  background: var(--primary-soft);
  color: var(--primary-dark);
}

.runtime-icon {
  width: 38px;
  height: 38px;
  margin-right: 12px;
  font-size: 19px;
}

.runtime-identity strong,
.runtime-identity span,
.provider-name-cell strong,
.provider-name-cell small,
.config-cell strong,
.config-cell small {
  display: block;
}

.runtime-identity strong {
  color: var(--text-primary);
  font-size: 14px;
}

.runtime-identity div > span {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.runtime-facts {
  display: grid;
  min-width: 0;
  grid-template-columns: 1fr 1.8fr 1.1fr 0.7fr;
  margin: 0;
}

.runtime-facts > div {
  min-width: 0;
  padding: 24px 16px;
  border-right: 1px solid var(--border-color);
}

.runtime-facts > div:last-child {
  border-right: 0;
}

.runtime-facts dt {
  margin-bottom: 8px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.runtime-facts dd {
  overflow: hidden;
  margin: 0;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.provider-heading {
  min-height: 66px;
}

.provider-count {
  color: var(--text-tertiary);
  font-size: 12px;
}

.provider-name-cell {
  display: flex;
  min-width: 0;
  align-items: center;
}

.provider-mark {
  width: 32px;
  height: 32px;
  margin-right: 10px;
}

.provider-name-cell strong,
.config-cell strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.provider-name-cell small,
.config-cell small {
  overflow: hidden;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-cell {
  min-width: 0;
}

.secret-value {
  color: var(--text-secondary);
  font-family: Consolas, "SFMono-Regular", monospace;
  font-size: 12px;
}

.timeout-value {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-secondary);
  font-size: 12px;
}

.providers-section :deep(.el-tag .el-icon) {
  margin-right: 4px;
}

.empty-actions {
  text-align: center;
}

.empty-actions p {
  margin: 0 0 14px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.settings-note {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.settings-note .el-icon {
  color: var(--warning-color);
}

@media (max-width: 1180px) {
  .runtime-layout {
    grid-template-columns: 1fr;
  }

  .runtime-identity {
    border-right: 0;
    border-bottom: 1px solid var(--border-color);
  }

  .runtime-facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .runtime-facts > div:nth-child(2) {
    border-right: 0;
  }

  .runtime-facts > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--border-color);
  }
}
</style>
