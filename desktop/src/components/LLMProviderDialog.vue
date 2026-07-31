<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { Check, Connection, Key, Lock, Refresh, View } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { llmSettingsApi } from '@/api/settings'
import type {
  LLMConnectionInput,
  LLMProvider,
  LLMProviderCreateInput,
  LLMProviderUpdateInput,
} from '@/types/llm'

interface ProviderForm {
  name: string
  providerType: 'openai_compatible'
  baseUrl: string
  apiKey: string
  defaultModel: string
  timeoutSeconds: number
  isEnabled: boolean
  isDefault: boolean
  temperatureEnabled: boolean
  temperature: number
}

interface ProviderPreset {
  key: string
  name: string
  baseUrl: string
  note: string
}

const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    key: 'openai',
    name: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    note: '官方 API',
  },
  {
    key: 'deepseek',
    name: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com/v1',
    note: '高性价比',
  },
  {
    key: 'volcengine',
    name: '火山方舟',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    note: '豆包/DeepSeek，模型 ID 可填接入点 ep-xxx',
  },
  {
    key: 'zhipu',
    name: '智谱 AI',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    note: 'GLM 系列',
  },
  {
    key: 'dashscope',
    name: '阿里云百炼',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    note: '通义千问',
  },
  {
    key: 'hunyuan',
    name: '腾讯混元',
    baseUrl: 'https://api.hunyuan.cloud.tencent.com/v1',
    note: '混元大模型',
  },
  {
    key: 'qianfan',
    name: '百度千帆',
    baseUrl: 'https://qianfan.baidubce.com/v2',
    note: '文心系列',
  },
  {
    key: 'moonshot',
    name: 'Moonshot Kimi',
    baseUrl: 'https://api.moonshot.cn/v1',
    note: 'Kimi',
  },
  {
    key: 'siliconflow',
    name: '硅基流动',
    baseUrl: 'https://api.siliconflow.cn/v1',
    note: '多模型聚合',
  },
]

const props = defineProps<{
  provider: LLMProvider | null
  saving: boolean
}>()

const emit = defineEmits<{
  submit: [payload: LLMProviderCreateInput | LLMProviderUpdateInput]
}>()

const visible = defineModel<boolean>('visible', { required: true })
const formRef = ref<FormInstance>()
const form = reactive<ProviderForm>(createEmptyForm())
const selectedPreset = ref<ProviderPreset | null>(null)
const modelOptions = ref<string[]>([])
const loadingModels = ref(false)
const testingConnection = ref(false)
const testResult = ref<{ model: string; latencyMs: number } | null>(null)
const isEditing = computed(() => props.provider !== null)
const dialogTitle = computed(() => isEditing.value ? '编辑大模型提供商' : '新增大模型提供商')
const baseUrlChanged = computed(() => {
  if (!props.provider) return false
  return normalizeBaseUrl(form.baseUrl) !== normalizeBaseUrl(props.provider.base_url)
})

const rules: FormRules<ProviderForm> = {
  name: [
    { required: true, message: '请输入显示名称', trigger: 'blur' },
    { max: 255, message: '显示名称不能超过 255 个字符', trigger: 'blur' },
  ],
  baseUrl: [
    { required: true, message: '请输入服务地址', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        try {
          const url = new URL(value)
          if (!['http:', 'https:'].includes(url.protocol)) throw new Error()
          callback()
        } catch {
          callback(new Error('请输入有效的 HTTP 或 HTTPS 地址'))
        }
      },
      trigger: 'blur',
    },
  ],
  apiKey: [{
    validator: (_rule, value: string, callback) => {
      if (!isEditing.value && !value.trim()) {
        callback(new Error('请输入 API Key'))
        return
      }
      if (baseUrlChanged.value && !value.trim()) {
        callback(new Error('服务地址已修改，请重新输入 API Key'))
        return
      }
      callback()
    },
    trigger: 'blur',
  }],
  defaultModel: [
    { required: true, message: '请输入默认模型', trigger: 'blur' },
    { max: 255, message: '模型名称不能超过 255 个字符', trigger: 'blur' },
  ],
}

watch(visible, async (value) => {
  if (!value) return
  selectedPreset.value = null
  Object.assign(form, props.provider ? formFromProvider(props.provider) : createEmptyForm())
  modelOptions.value = form.defaultModel ? [form.defaultModel] : []
  testResult.value = null
  await nextTick()
  formRef.value?.clearValidate()
})

function applyPreset(preset: ProviderPreset): void {
  selectedPreset.value = preset
  form.name = preset.name
  form.baseUrl = preset.baseUrl
  form.defaultModel = ''
  modelOptions.value = []
  testResult.value = null
  void formRef.value?.clearValidate(['baseUrl'])
}

watch(() => form.isEnabled, (enabled) => {
  if (!enabled) form.isDefault = false
})

watch(
  () => [form.baseUrl, form.apiKey, form.defaultModel, form.timeoutSeconds],
  () => {
    testResult.value = null
  },
)

function createEmptyForm(): ProviderForm {
  return {
    name: '',
    providerType: 'openai_compatible',
    baseUrl: '',
    apiKey: '',
    defaultModel: '',
    timeoutSeconds: 120,
    isEnabled: true,
    isDefault: false,
    temperatureEnabled: false,
    temperature: 0.2,
  }
}

function formFromProvider(provider: LLMProvider): ProviderForm {
  const temperature = provider.extra_config.temperature
  return {
    name: provider.name,
    providerType: provider.provider_type,
    baseUrl: provider.base_url,
    apiKey: '',
    defaultModel: provider.default_model,
    timeoutSeconds: provider.timeout_seconds,
    isEnabled: provider.is_enabled,
    isDefault: provider.is_default,
    temperatureEnabled: typeof temperature === 'number',
    temperature: typeof temperature === 'number' ? temperature : 0.2,
  }
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

function connectionPayload(): LLMConnectionInput {
  const payload: LLMConnectionInput = {
    base_url: normalizeBaseUrl(form.baseUrl),
    timeout_seconds: form.timeoutSeconds,
  }
  if (props.provider) payload.provider_id = props.provider.id
  if (form.apiKey.trim()) payload.api_key = form.apiKey.trim()
  return payload
}

async function validateConnectionFields(includeModel = false): Promise<boolean> {
  const fields = includeModel
    ? ['baseUrl', 'apiKey', 'defaultModel']
    : ['baseUrl', 'apiKey']
  return formRef.value?.validateField(fields).then(() => true).catch(() => false) ?? false
}

async function loadModels(): Promise<void> {
  if (!await validateConnectionFields()) return
  loadingModels.value = true
  try {
    const result = await llmSettingsApi.listModels(connectionPayload())
    modelOptions.value = Array.from(
      new Set([form.defaultModel, ...result.models].filter(Boolean)),
    )
    if (result.count > 0) {
      ElMessage.success(`已获取 ${result.count} 个可用模型`)
    } else {
      ElMessage.warning('服务没有返回模型，请手动输入模型名称')
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loadingModels.value = false
  }
}

async function testConnection(): Promise<void> {
  if (!await validateConnectionFields(true)) return
  testingConnection.value = true
  try {
    const result = await llmSettingsApi.testConnection({
      ...connectionPayload(),
      model: form.defaultModel.trim(),
    })
    testResult.value = {
      model: result.model,
      latencyMs: result.latency_ms,
    }
    ElMessage.success('模型连接测试成功')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    testingConnection.value = false
  }
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const extraConfig: Record<string, unknown> = { ...(props.provider?.extra_config ?? {}) }
  if (form.temperatureEnabled) {
    extraConfig.temperature = form.temperature
  } else {
    delete extraConfig.temperature
  }

  const common = {
    name: form.name.trim(),
    provider_type: form.providerType,
    base_url: normalizeBaseUrl(form.baseUrl),
    default_model: form.defaultModel.trim(),
    timeout_seconds: form.timeoutSeconds,
    is_enabled: form.isEnabled,
    is_default: form.isDefault,
    extra_config: extraConfig,
  }

  if (isEditing.value) {
    const payload: LLMProviderUpdateInput = { ...common }
    if (form.apiKey.trim()) payload.api_key = form.apiKey.trim()
    emit('submit', payload)
    return
  }

  emit('submit', {
    ...common,
    api_key: form.apiKey.trim(),
  })
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="640px"
    destroy-on-close
    :close-on-click-modal="!saving"
    :close-on-press-escape="!saving"
  >
    <div v-if="!isEditing" class="preset-section">
      <div class="preset-head">
        <strong>从常用平台快速选择</strong>
        <small>点击自动填入服务地址，模型请点「获取模型」拉取最新列表</small>
      </div>
      <div class="preset-list">
        <button
          v-for="preset in PROVIDER_PRESETS"
          :key="preset.key"
          type="button"
          class="preset-chip"
          :class="{ active: selectedPreset?.key === preset.key }"
          @click="applyPreset(preset)"
        >
          <span class="preset-name">{{ preset.name }}</span>
          <small>{{ preset.note }}</small>
        </button>
      </div>
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
      <div class="form-grid">
        <el-form-item label="显示名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：Kuncode" maxlength="255" />
        </el-form-item>
        <el-form-item label="接口类型">
          <el-select v-model="form.providerType" disabled>
            <el-option label="OpenAI 兼容接口" value="openai_compatible" />
          </el-select>
        </el-form-item>
      </div>

      <el-form-item label="服务地址" prop="baseUrl">
        <el-input v-model="form.baseUrl" placeholder="https://api.example.com/v1" :prefix-icon="View" />
      </el-form-item>

      <el-form-item prop="apiKey" :required="!isEditing || baseUrlChanged">
        <template #label>
          <span>API Key</span>
          <span v-if="isEditing && !baseUrlChanged" class="label-hint">留空则保留当前密钥</span>
          <span v-else-if="baseUrlChanged" class="label-hint warning-hint">服务地址已修改，需要重新输入</span>
        </template>
        <el-input
          v-model="form.apiKey"
          type="password"
          show-password
          autocomplete="new-password"
          :placeholder="isEditing && !baseUrlChanged ? `当前密钥：${provider?.api_key || '已配置'}` : '请输入完整 API Key'"
          :prefix-icon="Key"
        />
      </el-form-item>

      <div class="form-grid">
        <el-form-item label="默认模型" prop="defaultModel">
          <div class="model-picker">
            <el-select
              v-model="form.defaultModel"
              filterable
              allow-create
              default-first-option
              placeholder="先获取模型，或直接输入模型名称"
              no-data-text="暂无模型，可直接输入"
            >
              <el-option v-for="model in modelOptions" :key="model" :label="model" :value="model" />
            </el-select>
            <el-button :icon="Refresh" :loading="loadingModels" @click="loadModels">
              获取模型
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="请求超时">
          <el-input-number v-model="form.timeoutSeconds" :min="1" :max="600" controls-position="right" />
          <span class="input-unit">秒</span>
        </el-form-item>
      </div>

      <div class="connection-test-row">
        <div class="connection-test-status">
          <template v-if="testResult">
            <el-icon><Check /></el-icon>
            <span>已验证 {{ testResult.model }}，响应 {{ testResult.latencyMs }} ms</span>
          </template>
          <span v-else>选择模型后可发送一次最小请求，确认地址、密钥和模型均可用。</span>
        </div>
        <el-button
          type="primary"
          plain
          :icon="Connection"
          :loading="testingConnection"
          :disabled="!form.defaultModel.trim()"
          @click="testConnection"
        >
          测试连接
        </el-button>
      </div>

      <div class="switch-panel">
        <div class="switch-row">
          <div>
            <strong>启用提供商</strong>
            <small>禁用后不会被设为默认，也不会参与实际调用。</small>
          </div>
          <el-switch v-model="form.isEnabled" />
        </div>
        <div class="switch-row">
          <div>
            <strong>保存后设为当前使用</strong>
            <small>系统始终只保留一个当前使用配置。</small>
          </div>
          <el-switch v-model="form.isDefault" :disabled="!form.isEnabled" />
        </div>
      </div>

      <el-collapse class="advanced-settings">
        <el-collapse-item name="advanced">
          <template #title>
            <span class="advanced-title"><el-icon><Lock /></el-icon>高级调用参数</span>
          </template>
          <div class="switch-row parameter-row">
            <div>
              <strong>Temperature</strong>
              <small>仅在提供商支持时传入；关闭则不发送该参数。</small>
            </div>
            <div class="parameter-control">
              <el-switch v-model="form.temperatureEnabled" />
              <el-input-number
                v-model="form.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                :precision="1"
                controls-position="right"
                :disabled="!form.temperatureEnabled"
              />
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-form>

    <template #footer>
      <el-button :disabled="saving" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">
        {{ isEditing ? '保存修改' : '新增提供商' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.preset-section {
  margin-bottom: 18px;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-muted);
}

.preset-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.preset-head strong {
  color: var(--text-primary);
  font-size: 13px;
}

.preset-head small {
  color: var(--text-tertiary);
  font-size: 11px;
}

.preset-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.preset-chip {
  display: grid;
  gap: 3px;
  min-height: 52px;
  padding: 9px 11px;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: var(--surface-color);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.preset-chip:hover {
  border-color: var(--border-strong);
  background: var(--surface-strong);
}

.preset-chip.active {
  border-color: var(--primary-color);
  background: var(--primary-soft);
}

.preset-name {
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
}

.preset-chip small {
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}

.form-grid :deep(.el-select),
.form-grid :deep(.el-input-number) {
  width: 100%;
}

.model-picker {
  display: grid;
  width: 100%;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.connection-test-row {
  display: flex;
  min-height: 54px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: -2px 0 18px;
  padding: 9px 12px;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: var(--surface-muted);
}

.connection-test-status {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.5;
}

.connection-test-status .el-icon {
  flex: 0 0 auto;
  color: var(--success-color);
  font-size: 16px;
}

.label-hint {
  margin-left: 8px;
  color: var(--text-tertiary);
  font-size: 11px;
  font-weight: 400;
}

.warning-hint {
  color: var(--warning-color);
}

.input-unit {
  position: absolute;
  right: 42px;
  bottom: 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 32px;
  pointer-events: none;
}

.switch-panel {
  overflow: hidden;
  margin-top: 4px;
  border: 1px solid var(--border-color);
  border-radius: 7px;
}

.switch-row {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 10px 14px;
  background: var(--surface-muted);
}

.switch-row + .switch-row {
  border-top: 1px solid var(--border-color);
}

.switch-row strong,
.switch-row small {
  display: block;
}

.switch-row strong {
  color: var(--text-primary);
  font-size: 13px;
}

.switch-row small {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.5;
}

.advanced-settings {
  margin-top: 14px;
  border-top: 0;
  border-bottom: 0;
}

.advanced-settings :deep(.el-collapse-item__header) {
  height: 42px;
  border: 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.advanced-settings :deep(.el-collapse-item__wrap),
.advanced-settings :deep(.el-collapse-item__content) {
  border: 0;
  padding-bottom: 0;
}

.advanced-title {
  display: inline-flex;
  gap: 7px;
  align-items: center;
}

.parameter-row {
  border: 1px solid var(--border-color);
  border-radius: 7px;
}

.parameter-control {
  display: flex;
  align-items: center;
  gap: 12px;
}

.parameter-control :deep(.el-input-number) {
  width: 116px;
}
</style>
