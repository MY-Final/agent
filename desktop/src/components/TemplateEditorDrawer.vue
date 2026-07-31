<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowUp,
  Delete,
  Plus,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { templateApi } from '@/api/templates'
import type {
  ColumnDefinition,
  FieldDefinition,
  FieldType,
  SectionDefinition,
  SectionKind,
  SectionTone,
} from '@/types/results'
import type {
  ParseTemplateRecord,
  TemplateDraft,
  TemplateSuggestion,
} from '@/types/template'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  template: ParseTemplateRecord | null
  defaultSections: SectionDefinition[]
  suggestion: TemplateSuggestion | null
}>()

const emit = defineEmits<{ saved: [] }>()

const saving = ref(false)
const draft = ref<TemplateDraft>(createEmptyDraft())

const isEditing = computed(() => props.template !== null)
const isSuggestionMode = computed(() => !props.template && props.suggestion !== null)

const FIELD_TYPE_OPTIONS: { value: FieldType; label: string }[] = [
  { value: 'text', label: '文本' },
  { value: 'number', label: '数字' },
  { value: 'money', label: '金额' },
  { value: 'date', label: '日期' },
  { value: 'boolean', label: '布尔' },
]

const KIND_OPTIONS: { value: SectionKind; label: string }[] = [
  { value: 'grid', label: '字段描述' },
  { value: 'table', label: '表格' },
  { value: 'key_value', label: '键值对' },
  { value: 'list', label: '要点列表' },
]

const TONE_OPTIONS: { value: SectionTone; label: string }[] = [
  { value: 'default', label: '中性' },
  { value: 'primary', label: '品牌绿' },
  { value: 'warning', label: '琥珀' },
  { value: 'danger', label: '红色' },
  { value: 'success', label: '绿色' },
  { value: 'info', label: '蓝灰' },
]

const ICON_OPTIONS = [
  { value: 'Memo', label: '概览' },
  { value: 'Collection', label: '表格' },
  { value: 'Tickets', label: '评分' },
  { value: 'Calendar', label: '时间' },
  { value: 'WarningFilled', label: '警告' },
  { value: 'List', label: '列表' },
  { value: 'Document', label: '文档' },
  { value: 'DataLine', label: '数据' },
]

const VARIANT_OPTIONS = [
  { value: 'text', label: '文本' },
  { value: 'muted', label: '弱化' },
  { value: 'stack', label: '主值+副键' },
  { value: 'tag', label: '标签' },
]

const TAG_TYPE_OPTIONS = [
  { value: 'danger', label: '红' },
  { value: 'warning', label: '琥珀' },
  { value: 'success', label: '绿' },
  { value: 'info', label: '蓝灰' },
  { value: 'primary', label: '主色' },
]

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function createEmptyDraft(): TemplateDraft {
  return {
    name: '',
    description: '',
    version: 'v1',
    is_default: false,
    sections: [],
  }
}

function newField(): FieldDefinition {
  return { key: '', label: '', type: 'text', required: false }
}

function newColumn(): ColumnDefinition {
  return {
    key: '',
    label: '',
    type: 'text',
    required: false,
    variant: 'text',
    secondary_key: null,
    secondary_prefix: null,
    truthy_label: null,
    falsy_label: null,
    truthy_tag: null,
    falsy_tag: null,
    width: null,
    min_width: null,
  }
}

function newSection(kind: SectionKind): SectionDefinition {
  return {
    id: '',
    title: '',
    subtitle: '',
    kind,
    tone: 'default',
    icon: null,
    fields: kind === 'grid' ? [newField()] : undefined,
    columns: kind === 'table' ? [newColumn()] : undefined,
  }
}

function initDraft(): void {
  if (props.template) {
    draft.value = {
      name: props.template.name,
      description: props.template.description ?? '',
      version: props.template.version,
      is_default: props.template.is_default,
      sections: clone(props.template.sections),
    }
    return
  }
  if (props.suggestion) {
    draft.value = {
      name: props.suggestion.suggested_name,
      description: props.suggestion.description ?? '',
      version: 'v1',
      is_default: false,
      sections: clone(props.suggestion.sections),
    }
    return
  }
  draft.value = {
    name: '',
    description: '',
    version: 'v1',
    is_default: false,
    sections: clone(props.defaultSections.length ? props.defaultSections : []),
  }
  if (!draft.value.sections.length) {
    draft.value.sections.push(newSection('grid'))
  }
}

watch(visible, (open) => {
  if (open) initDraft()
})

function addSection(): void {
  draft.value.sections.push(newSection('grid'))
}

function removeSection(index: number): void {
  draft.value.sections.splice(index, 1)
}

function moveSection(index: number, delta: number): void {
  const target = index + delta
  if (target < 0 || target >= draft.value.sections.length) return
  const sections = draft.value.sections
  const item = sections[index]
  sections.splice(index, 1)
  sections.splice(target, 0, item)
}

function onKindChange(section: SectionDefinition): void {
  if (section.kind === 'grid') {
    if (!section.fields?.length) section.fields = [newField()]
    section.columns = undefined
  } else if (section.kind === 'table') {
    if (!section.columns?.length) section.columns = [newColumn()]
    section.fields = undefined
  } else {
    section.fields = undefined
    section.columns = undefined
  }
}

function addField(section: SectionDefinition): void {
  if (!section.fields) section.fields = []
  section.fields.push(newField())
}

function removeField(section: SectionDefinition, index: number): void {
  section.fields?.splice(index, 1)
}

function addColumn(section: SectionDefinition): void {
  if (!section.columns) section.columns = []
  section.columns.push(newColumn())
}

function removeColumn(section: SectionDefinition, index: number): void {
  section.columns?.splice(index, 1)
}

const KEY_PATTERN = /^[a-z][a-z0-9_]*$/

function validateDraft(): string | null {
  const template = draft.value
  if (!template.name.trim()) return '请填写模板名称'
  if (!template.version.trim()) return '请填写模板版本号'
  if (!template.sections.length) return '模板至少需要一个 section'

  const sectionIds = new Set<string>()
  for (const section of template.sections) {
    if (!section.id.trim()) return '存在未填写 id 的 section'
    if (!KEY_PATTERN.test(section.id)) {
      return `section id「${section.id}」只能包含小写字母、数字和下划线，且以字母开头`
    }
    if (sectionIds.has(section.id)) return `section id「${section.id}」重复`
    sectionIds.add(section.id)
    if (!section.title.trim()) return '存在未填写标题的 section'

    if (section.kind === 'grid') {
      if (!section.fields?.length) return `section「${section.title}」至少需要一个字段`
      const keys = new Set<string>()
      for (const field of section.fields) {
        if (!KEY_PATTERN.test(field.key)) {
          return `字段 key「${field.key}」只能包含小写字母、数字和下划线，且以字母开头`
        }
        if (!field.label.trim()) return `字段「${field.key}」缺少显示名称`
        if (keys.has(field.key)) return `字段 key「${field.key}」重复`
        keys.add(field.key)
      }
    }

    if (section.kind === 'table') {
      if (!section.columns?.length) return `section「${section.title}」至少需要一列`
      const keys = new Set<string>()
      for (const column of section.columns) {
        if (!KEY_PATTERN.test(column.key)) {
          return `列 key「${column.key}」只能包含小写字母、数字和下划线，且以字母开头`
        }
        if (!column.label.trim()) return `列「${column.key}」缺少显示名称`
        if (keys.has(column.key)) return `列 key「${column.key}」重复`
        keys.add(column.key)
        if (column.variant === 'stack' && column.secondary_key && !KEY_PATTERN.test(column.secondary_key)) {
          return `副键 key「${column.secondary_key}」只能包含小写字母、数字和下划线，且以字母开头`
        }
      }
    }
  }
  return null
}

function buildPayload(): {
  name: string
  description: string | null
  version: string
  is_default: boolean
  sections: SectionDefinition[]
} {
  const template = draft.value
  return {
    name: template.name.trim(),
    description: template.description.trim() || null,
    version: template.version.trim(),
    is_default: template.is_default,
    sections: template.sections.map((section) => ({
      id: section.id.trim(),
      title: section.title.trim(),
      subtitle: section.subtitle?.trim() || null,
      kind: section.kind,
      tone: section.tone ?? 'default',
      icon: section.icon || null,
      fields:
        section.kind === 'grid'
          ? section.fields?.map((field) => ({
              key: field.key.trim(),
              label: field.label.trim(),
              type: field.type,
              required: field.required,
            }))
          : undefined,
      columns:
        section.kind === 'table'
          ? section.columns?.map((column) => ({
              key: column.key.trim(),
              label: column.label.trim(),
              type: column.type,
              required: column.required,
              variant: column.variant ?? 'text',
              secondary_key: column.secondary_key?.trim() || null,
              secondary_prefix: column.secondary_prefix?.trim() || null,
              truthy_label: column.truthy_label?.trim() || null,
              falsy_label: column.falsy_label?.trim() || null,
              truthy_tag: column.truthy_tag || null,
              falsy_tag: column.falsy_tag || null,
              width: column.width ?? null,
              min_width: column.min_width ?? null,
            }))
          : undefined,
    })),
  }
}

async function save(): Promise<void> {
  const error = validateDraft()
  if (error) {
    ElMessage.warning(error)
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (props.template) {
      await templateApi.update(props.template.id, payload)
    } else {
      await templateApi.create(payload)
    }
    emit('saved')
    visible.value = false
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-drawer v-model="visible" :size="'min(920px, 94vw)'" class="template-editor">
    <template #header>
      <div class="editor-heading">
        <h2>{{ isEditing ? '编辑解析模板' : isSuggestionMode ? '确认 AI 生成的模板' : '新建解析模板' }}</h2>
        <p>
          {{
            isSuggestionMode
              ? 'AI 已按你的描述生成字段建议，可以逐项修改后保存；保存后才会成为正式模板。'
              : '模板决定标书解析时提取哪些字段，以及前端如何展示；保存后对新建解析生效。'
          }}
        </p>
      </div>
    </template>

    <div class="editor-body">
      <section class="editor-card">
        <header class="editor-card-head">
          <h3>基本信息</h3>
          <p>名称用于任务选择模板时识别，版本号建议随改动递增。</p>
        </header>
        <div class="basic-grid">
          <label class="editor-field">
            <span>模板名称</span>
            <el-input v-model="draft.name" maxlength="100" placeholder="例如：市政工程标书模板" />
          </label>
          <label class="editor-field">
            <span>版本号</span>
            <el-input v-model="draft.version" maxlength="32" placeholder="例如：v2" />
          </label>
          <label class="editor-field editor-field-wide">
            <span>描述（可选）</span>
            <el-input
              v-model="draft.description"
              type="textarea"
              :rows="2"
              maxlength="500"
              placeholder="说明这套模板适用于哪类标书"
            />
          </label>
          <label class="editor-switch">
            <span>设为默认模板</span>
            <el-switch v-model="draft.is_default" />
          </label>
        </div>
      </section>

      <section class="editor-card">
        <header class="editor-card-head section-list-head">
          <div>
            <h3>Section 配置</h3>
            <p>每个 section 是结果页里的一个展示块；顺序即展示顺序。</p>
          </div>
          <el-button type="primary" plain :icon="Plus" @click="addSection">添加 Section</el-button>
        </header>

        <div class="section-list">
          <article
            v-for="(section, sectionIndex) in draft.sections"
            :key="sectionIndex"
            class="section-editor"
          >
            <header class="section-editor-head">
              <span class="section-order">{{ sectionIndex + 1 }}</span>
              <el-input
                v-model="section.title"
                maxlength="60"
                placeholder="Section 标题"
                class="section-title-input"
              />
              <el-tag size="small" effect="plain">
                {{ KIND_OPTIONS.find((item) => item.value === section.kind)?.label }}
              </el-tag>
              <div class="section-head-actions">
                <el-tooltip content="上移">
                  <el-button text :icon="ArrowUp" :disabled="sectionIndex === 0" @click="moveSection(sectionIndex, -1)" />
                </el-tooltip>
                <el-tooltip content="下移">
                  <el-button text :icon="ArrowDown" :disabled="sectionIndex === draft.sections.length - 1" @click="moveSection(sectionIndex, 1)" />
                </el-tooltip>
                <el-tooltip content="删除 Section">
                  <el-button text type="danger" :icon="Delete" @click="removeSection(sectionIndex)" />
                </el-tooltip>
              </div>
            </header>

            <div class="section-config-grid">
              <label class="editor-field">
                <span>标识（id）</span>
                <el-input v-model="section.id" maxlength="60" placeholder="overview" />
              </label>
              <label class="editor-field">
                <span>类型</span>
                <el-select v-model="section.kind" class="editor-select" @change="onKindChange(section)">
                  <el-option v-for="option in KIND_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
              </label>
              <label class="editor-field">
                <span>语义色</span>
                <el-select v-model="section.tone" class="editor-select">
                  <el-option v-for="option in TONE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
              </label>
              <label class="editor-field">
                <span>图标</span>
                <el-select v-model="section.icon" class="editor-select" clearable placeholder="自动">
                  <el-option v-for="option in ICON_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
              </label>
              <label class="editor-field editor-field-wide">
                <span>副标题（可选）</span>
                <el-input v-model="section.subtitle" maxlength="120" placeholder="展示在标题下方的说明文字" />
              </label>
            </div>

            <div v-if="section.kind === 'grid'" class="sub-editor">
              <div class="sub-editor-head">
                <strong>字段</strong>
                <el-button size="small" text type="primary" :icon="Plus" @click="addField(section)">添加字段</el-button>
              </div>
              <div v-for="(field, fieldIndex) in section.fields" :key="fieldIndex" class="sub-editor-row grid-fields-row">
                <el-input v-model="field.key" placeholder="key（英文）" />
                <el-input v-model="field.label" placeholder="显示名称" />
                <el-select v-model="field.type" class="field-type-select">
                  <el-option v-for="option in FIELD_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
                <el-tooltip content="必填">
                  <el-switch v-model="field.required" />
                </el-tooltip>
                <el-button text type="danger" :icon="Delete" aria-label="删除字段" @click="removeField(section, fieldIndex)" />
              </div>
            </div>

            <div v-else-if="section.kind === 'table'" class="sub-editor">
              <div class="sub-editor-head">
                <strong>列</strong>
                <el-button size="small" text type="primary" :icon="Plus" @click="addColumn(section)">添加列</el-button>
              </div>
              <div v-for="(column, columnIndex) in section.columns" :key="columnIndex" class="column-editor">
                <div class="column-editor-head">
                  <strong>列 {{ columnIndex + 1 }}</strong>
                  <el-button text type="danger" :icon="Delete" aria-label="删除列" @click="removeColumn(section, columnIndex)" />
                </div>
                <div class="column-grid">
                  <label class="editor-field">
                    <span>key（英文）</span>
                    <el-input v-model="column.key" placeholder="category" />
                  </label>
                  <label class="editor-field">
                    <span>显示名称</span>
                    <el-input v-model="column.label" placeholder="类别" />
                  </label>
                  <label class="editor-field">
                    <span>类型</span>
                    <el-select v-model="column.type" class="editor-select">
                      <el-option v-for="option in FIELD_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                    </el-select>
                  </label>
                  <label class="editor-field">
                    <span>展示方式</span>
                    <el-select v-model="column.variant" class="editor-select">
                      <el-option v-for="option in VARIANT_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                    </el-select>
                  </label>
                  <label class="editor-switch">
                    <span>必填</span>
                    <el-switch v-model="column.required" />
                  </label>
                  <template v-if="column.variant === 'stack'">
                    <label class="editor-field">
                      <span>副键 key</span>
                      <el-input v-model="column.secondary_key" placeholder="original_text" />
                    </label>
                    <label class="editor-field">
                      <span>副键前缀</span>
                      <el-input v-model="column.secondary_prefix" placeholder="原文" />
                    </label>
                  </template>
                  <template v-if="column.variant === 'tag'">
                    <label class="editor-field">
                      <span>真值文案</span>
                      <el-input v-model="column.truthy_label" placeholder="强制" />
                    </label>
                    <label class="editor-field">
                      <span>假值文案</span>
                      <el-input v-model="column.falsy_label" placeholder="一般" />
                    </label>
                    <label class="editor-field">
                      <span>真值颜色</span>
                      <el-select v-model="column.truthy_tag" class="editor-select" clearable>
                        <el-option v-for="option in TAG_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                      </el-select>
                    </label>
                    <label class="editor-field">
                      <span>假值颜色</span>
                      <el-select v-model="column.falsy_tag" class="editor-select" clearable>
                        <el-option v-for="option in TAG_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                      </el-select>
                    </label>
                  </template>
                  <label class="editor-field">
                    <span>固定宽度（px）</span>
                    <el-input-number
                      :model-value="column.width ?? undefined"
                      :min="0"
                      :controls="false"
                      placeholder="留空自动"
                      class="editor-number"
                      @update:model-value="(value) => (column.width = value ?? null)"
                    />
                  </label>
                  <label class="editor-field">
                    <span>最小宽度（px）</span>
                    <el-input-number
                      :model-value="column.min_width ?? undefined"
                      :min="0"
                      :controls="false"
                      placeholder="留空自动"
                      class="editor-number"
                      @update:model-value="(value) => (column.min_width = value ?? null)"
                    />
                  </label>
                </div>
              </div>
            </div>

            <div v-else class="sub-editor hint-block">
              <p>{{ section.kind === 'key_value' ? '键值对：LLM 返回任意维度名与标量值，前端逐行展示。' : '要点列表：LLM 返回字符串数组，前端逐条展示。' }}</p>
            </div>
          </article>
        </div>
      </section>
    </div>

    <template #footer>
      <div class="editor-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ isEditing ? '保存修改' : isSuggestionMode ? '保存模板' : '创建模板' }}
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.editor-heading h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 17px;
  font-weight: 700;
}

.editor-heading p {
  margin: 5px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.editor-body {
  display: grid;
  gap: 16px;
}

.editor-card {
  padding: 20px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
}

.editor-card-head {
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border-color);
}

.editor-card-head h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}

.editor-card-head p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.section-list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.basic-grid,
.section-config-grid,
.column-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.editor-field,
.editor-switch {
  display: grid;
  min-width: 0;
  gap: 7px;
}

.editor-field > span,
.editor-switch > span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.editor-field-wide {
  grid-column: 1 / -1;
}

.editor-switch {
  align-content: end;
  padding-bottom: 2px;
}

.editor-select {
  width: 100%;
}

.editor-number {
  width: 100%;
}

.section-list {
  display: grid;
  gap: 14px;
}

.section-editor {
  padding: 16px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: var(--surface-muted);
}

.section-editor-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.section-order {
  display: grid;
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: var(--surface-strong);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
}

.section-title-input {
  min-width: 0;
  flex: 1;
}

.section-head-actions {
  display: flex;
  flex: 0 0 auto;
}

.sub-editor {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--border-strong);
}

.sub-editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.sub-editor-head strong {
  color: var(--text-secondary);
  font-size: 12px;
}

.grid-fields-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) minmax(120px, 1fr) 130px 42px 32px;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.field-type-select {
  width: 100%;
}

.column-editor {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--surface-color);
}

.column-editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.column-editor-head strong {
  color: var(--text-secondary);
  font-size: 12px;
}

.hint-block p {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.editor-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 760px) {
  .basic-grid,
  .section-config-grid,
  .column-grid {
    grid-template-columns: 1fr;
  }

  .grid-fields-row {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
