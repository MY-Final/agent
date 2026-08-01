<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Delete,
  EditPen,
  MagicStick,
  Plus,
  Refresh,
  Search,
  Star,
  StarFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ApiRequestError, getErrorMessage } from '@/api/client'
import { templateApi } from '@/api/templates'
import TemplateEditorDrawer from '@/components/TemplateEditorDrawer.vue'
import type { SectionDefinition } from '@/types/results'
import type { ParseTemplateRecord, TemplateSuggestion } from '@/types/template'
import { formatDate } from '@/utils/format'

const templates = ref<ParseTemplateRecord[]>([])
const loading = ref(false)
const templateKeyword = ref('')
const editorVisible = ref(false)
const editingTemplate = ref<ParseTemplateRecord | null>(null)
const suggestion = ref<TemplateSuggestion | null>(null)
const suggestDialogVisible = ref(false)
const suggesting = ref(false)
const suggestStreamingVisible = ref(false)
const suggestStreaming = ref('')
const suggestionDescription = ref('')
const suggestionReference = ref('')

const defaultSections = ref<SectionDefinition[]>([])

const SUGGEST_EXAMPLES = [
  '重点关注投标保证金、付款方式和工期违约条款',
  '提取评分办法、废标条款和联合体投标要求',
  '关注项目工期、质量标准和验收要求',
]

const filteredTemplates = computed(() => {
  const keyword = templateKeyword.value.trim().toLowerCase()
  if (!keyword) return templates.value
  return templates.value.filter((template) =>
    [template.name, template.description ?? '', template.version].some((text) =>
      text.toLowerCase().includes(keyword),
    ),
  )
})

async function loadTemplates(): Promise<void> {
  loading.value = true
  try {
    templates.value = await templateApi.list()
    const defaultTemplate = templates.value.find((item) => item.is_default)
    defaultSections.value = defaultTemplate?.sections ?? []
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  editingTemplate.value = null
  suggestion.value = null
  editorVisible.value = true
}

function openEdit(template: ParseTemplateRecord): void {
  editingTemplate.value = template
  suggestion.value = null
  editorVisible.value = true
}

function openSuggest(): void {
  suggestionDescription.value = ''
  suggestionReference.value = ''
  suggestDialogVisible.value = true
}

async function generateSuggestion(): Promise<void> {
  const description = suggestionDescription.value.trim()
  if (!description) {
    ElMessage.warning('请先用自然语言描述要提取哪些字段')
    return
  }
  suggesting.value = true
  suggestStreamingVisible.value = true
  suggestStreaming.value = ''
  try {
    let finalSuggestion: TemplateSuggestion | null = null
    for await (const event of templateApi.suggestStream({
      description,
      reference_text: suggestionReference.value.trim() || null,
    })) {
      if (event.type === 'delta') {
        suggestStreaming.value += String(event.content ?? '')
      } else if (event.type === 'result') {
        finalSuggestion = event.data as TemplateSuggestion
      } else if (event.type === 'error') {
        throw new ApiRequestError(
          String(event.message ?? '模板建议生成失败'),
          typeof event.code === 'number' ? event.code : undefined,
        )
      }
    }
    if (!finalSuggestion) throw new ApiRequestError('模板建议未返回结果')
    suggestion.value = finalSuggestion
    suggestDialogVisible.value = false
    editingTemplate.value = null
    editorVisible.value = true
    ElMessage.success('模板建议已生成，请在编辑器中确认后点击「保存模板」')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    suggesting.value = false
    suggestStreamingVisible.value = false
  }
}

async function setDefault(template: ParseTemplateRecord): Promise<void> {
  try {
    await templateApi.update(template.id, { is_default: true })
    ElMessage.success(`「${template.name}」已设为默认模板`)
    await loadTemplates()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function removeTemplate(template: ParseTemplateRecord): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `删除后，已引用该模板的任务会自动回退到默认模板或内置模板。确定删除「${template.name}」吗？`,
      '删除解析模板',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await templateApi.remove(template.id)
    ElMessage.success('解析模板已删除')
    await loadTemplates()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function sectionSummary(template: ParseTemplateRecord): string {
  const gridFields = template.sections.reduce(
    (total, section) => total + (section.fields?.length ?? 0),
    0,
  )
  const tableColumns = template.sections.reduce(
    (total, section) => total + (section.columns?.length ?? 0),
    0,
  )
  const parts: string[] = [`${template.sections.length} 个区块`]
  if (gridFields) parts.push(`${gridFields} 个字段`)
  if (tableColumns) parts.push(`${tableColumns} 个表格列`)
  return parts.join(' · ')
}

onMounted(() => {
  void loadTemplates()
})
</script>

<template>
  <div class="page-container templates-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">解析模板</h1>
        <p class="page-subtitle">
          模板决定标书解析提取哪些字段、前端如何展示。修改模板后，新启动的解析立即生效。
        </p>
      </div>
      <div class="page-actions">
        <el-tooltip content="刷新列表">
          <el-button
            :icon="Refresh"
            circle
            :loading="loading"
            aria-label="刷新列表"
            @click="loadTemplates"
          />
        </el-tooltip>
        <el-button :icon="MagicStick" class="ai-button" @click="openSuggest">AI 生成模板</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建模板</el-button>
      </div>
    </header>

    <section class="content-surface">
      <el-alert
        class="templates-tip"
        title="模板选择规则"
        description="解析时按「任务指定模板 → 默认模板 → 内置种子模板」的顺序选用。新建任务时可以指定模板。"
        type="info"
        :closable="false"
        show-icon
      />

      <div class="templates-toolbar">
        <div>
          <h2 class="section-title">模板列表</h2>
          <p class="section-subtitle">共 {{ templates.length }} 套模板，默认模板用于未指定模板的任务。</p>
        </div>
        <el-input
          v-model="templateKeyword"
          class="template-search"
          :prefix-icon="Search"
          placeholder="搜索模板名称、描述或版本"
          clearable
        />
      </div>

      <el-table v-loading="loading" :data="filteredTemplates" stripe class="templates-table">
        <el-table-column label="模板" min-width="260">
          <template #default="scope">
            <div class="template-name-cell">
              <strong>{{ scope.row.name }}</strong>
              <small v-if="scope.row.description">{{ scope.row.description }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="90">
          <template #default="scope">
            <span class="version-chip">{{ scope.row.version }}</span>
          </template>
        </el-table-column>
        <el-table-column label="内容" min-width="180">
          <template #default="scope">{{ sectionSummary(scope.row) }}</template>
        </el-table-column>
        <el-table-column label="默认" width="90" align="center">
          <template #default="scope">
            <span v-if="scope.row.is_default" class="default-pill">
              <el-icon><StarFilled /></el-icon>
              默认
            </span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="180">
          <template #default="scope">{{ formatDate(scope.row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="center">
          <template #default="scope">
            <div class="row-actions">
              <el-tooltip content="编辑模板">
                <el-button
                  text
                  class="action-btn"
                  :icon="EditPen"
                  aria-label="编辑模板"
                  @click="openEdit(scope.row)"
                />
              </el-tooltip>
              <el-tooltip v-if="!scope.row.is_default" content="设为默认模板">
                <el-button
                  text
                  class="action-btn star-btn"
                  :icon="Star"
                  aria-label="设为默认模板"
                  @click="setDefault(scope.row)"
                />
              </el-tooltip>
              <el-tooltip content="删除模板">
                <el-button
                  text
                  class="action-btn danger-btn"
                  :icon="Delete"
                  aria-label="删除模板"
                  @click="removeTemplate(scope.row)"
                />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无解析模板，点击右上角新建" :image-size="80" />
        </template>
      </el-table>
    </section>

    <TemplateEditorDrawer
      v-model="editorVisible"
      :template="editingTemplate"
      :default-sections="defaultSections"
      :suggestion="suggestion"
      @saved="loadTemplates"
    />

    <el-dialog
      v-model="suggestDialogVisible"
      class="suggest-dialog"
      width="760px"
      align-center
    >
      <template #header>
        <div class="suggest-header">
          <span class="suggest-header-icon">
            <el-icon><MagicStick /></el-icon>
          </span>
          <div>
            <h2>AI 生成模板</h2>
            <p>用一句话描述要提取的重点，AI 先生成建议，你确认后再保存。</p>
          </div>
        </div>
      </template>
      <div class="suggest-body">
        <div class="suggest-examples">
          <span class="suggest-examples-label">试试</span>
          <button
            v-for="example in SUGGEST_EXAMPLES"
            :key="example"
            type="button"
            class="example-chip"
            @click="suggestionDescription = example"
          >
            {{ example }}
          </button>
        </div>
        <label class="suggest-field">
          <span class="suggest-field-label">
            提取重点
            <em class="required-mark">必填</em>
          </span>
          <el-input
            v-model="suggestionDescription"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="例如：重点关注投标保证金、付款方式、工期违约条款"
          />
        </label>
        <label class="suggest-field">
          <span class="suggest-field-label">
            参考原文
            <em class="optional-mark">可选</em>
          </span>
          <el-input
            v-model="suggestionReference"
            type="textarea"
            :rows="5"
            maxlength="20000"
            show-word-limit
            placeholder="粘贴一段标书原文，AI 会生成更准确的字段"
          />
        </label>
        <p class="suggest-note">系统会自动补充「资格要求」表格区块，用于后续资质匹配。</p>
        <section v-if="suggestStreamingVisible" class="suggest-stream">
          <div class="suggest-stream-title">
            <span class="suggest-stream-dot" />
            AI 实时生成中…
          </div>
          <pre class="suggest-stream-content">{{ suggestStreaming || '等待大模型输出…' }}</pre>
        </section>
      </div>
      <template #footer>
        <el-button @click="suggestDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :icon="MagicStick"
          :loading="suggesting"
          @click="generateSuggestion"
        >
          生成建议
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.templates-page {
  max-width: 1280px;
}

.templates-tip {
  margin: 0;
  border: 0;
  border-bottom: 1px solid var(--border-color);
  border-radius: 0;
}

.templates-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border-color);
}

.template-search {
  width: 280px;
}

.templates-table {
  width: 100%;
}

.template-name-cell strong,
.template-name-cell small {
  display: block;
}

.template-name-cell strong {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.template-name-cell small {
  max-width: 480px;
  overflow: hidden;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-muted {
  color: var(--text-tertiary);
}

.ai-button {
  color: var(--text-secondary);
}

.ai-button .el-icon {
  color: var(--warning-color);
}

.version-chip {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid var(--border-color);
  border-radius: 5px;
  background: var(--surface-muted);
  color: var(--text-secondary);
  font-family: "Cascadia Mono", "JetBrains Mono", Consolas, monospace;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.default-pill {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--warning-soft);
  color: var(--warning-color);
  font-size: 11px;
  font-weight: 600;
}

.default-pill .el-icon {
  font-size: 12px;
}

.row-actions {
  display: inline-flex;
  gap: 2px;
  align-items: center;
}

.action-btn {
  width: 30px;
  height: 30px;
  padding: 0;
  color: var(--text-tertiary);
  font-size: 15px;
}

.action-btn:hover {
  background: var(--primary-soft);
  color: var(--primary-dark);
}

.action-btn.star-btn:hover {
  background: var(--warning-soft);
  color: var(--warning-color);
}

.action-btn.danger-btn:hover {
  background: var(--danger-soft);
  color: var(--danger-color);
}

.suggest-header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.suggest-header-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 8px;
  background: var(--primary-soft);
  color: var(--primary-color);
  font-size: 19px;
}

.suggest-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 700;
}

.suggest-header p {
  margin: 5px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.suggest-body {
  display: grid;
  gap: 18px;
  padding-top: 2px;
}

.suggest-examples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.suggest-examples-label {
  color: var(--text-tertiary);
  font-size: 12px;
}

.example-chip {
  height: 26px;
  padding: 0 10px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 11px;
  transition: border-color 0.15s ease, background-color 0.15s ease,
    color 0.15s ease;
}

.example-chip:hover {
  border-color: var(--primary-color);
  background: var(--primary-soft);
  color: var(--primary-dark);
}

.suggest-field {
  display: grid;
  gap: 8px;
}

.suggest-field-label {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.required-mark {
  color: var(--danger-color);
  font-size: 11px;
  font-style: normal;
}

.optional-mark {
  color: var(--text-tertiary);
  font-size: 11px;
  font-style: normal;
  font-weight: 400;
}

.suggest-note {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.6;
}

.suggest-stream {
  margin-top: 14px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 10px;
}

.suggest-stream-title {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 9px 12px;
  background: var(--bg-secondary, #fafafa);
  border-bottom: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.suggest-stream-dot {
  width: 8px;
  height: 8px;
  background: var(--primary-color);
  border-radius: 50%;
  animation: suggest-stream-blink 1s ease-in-out infinite;
}

.suggest-stream-content {
  max-height: 220px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
}

@keyframes suggest-stream-blink {
  50% { opacity: 0.3; }
}
</style>
