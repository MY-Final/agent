<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import type {
  FieldDefinition,
  ParseTemplate,
  SectionDefinition,
} from '@/types/results'

const props = defineProps<{
  template: ParseTemplate
  data: Record<string, unknown>
  summary: string | null
}>()

const emit = defineEmits<{
  save: [data: Record<string, unknown>, summary: string]
}>()

const draft = ref<Record<string, any>>({})
const summary = ref('')
const kvPairs = reactive<Record<string, { key: string; value: string }[]>>({})

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function fieldValue(section: SectionDefinition, field: FieldDefinition): unknown {
  return draft.value[section.id]?.[field.key]
}

function sectionRows(section: SectionDefinition): Record<string, unknown>[] {
  const value = draft.value[section.id]
  return Array.isArray(value) ? value : []
}

function sectionItems(section: SectionDefinition): string[] {
  const value = draft.value[section.id]
  return Array.isArray(value) ? value : []
}

function tableKeys(section: SectionDefinition): string[] {
  const keys = (section.columns ?? []).map((column) => column.key)
  for (const column of section.columns ?? []) {
    if (column.variant === 'stack' && column.secondary_key) {
      keys.push(column.secondary_key)
    }
  }
  return keys
}

function newRow(section: SectionDefinition): Record<string, unknown> {
  const row: Record<string, unknown> = {}
  for (const column of section.columns ?? []) {
    row[column.key] = column.type === 'boolean' ? true : ''
  }
  for (const column of section.columns ?? []) {
    if (column.variant === 'stack' && column.secondary_key) {
      row[column.secondary_key] = ''
    }
  }
  return row
}

function addRow(section: SectionDefinition): void {
  draft.value[section.id] = [...sectionRows(section), newRow(section)]
}

function removeRow(section: SectionDefinition, index: number): void {
  const rows = sectionRows(section)
  rows.splice(index, 1)
}

function addItem(section: SectionDefinition): void {
  draft.value[section.id] = [...sectionItems(section), '']
}

function removeItem(section: SectionDefinition, index: number): void {
  sectionItems(section).splice(index, 1)
}

function addKv(section: SectionDefinition): void {
  if (!kvPairs[section.id]) kvPairs[section.id] = []
  kvPairs[section.id].push({ key: '', value: '' })
}

function removeKv(section: SectionDefinition, index: number): void {
  kvPairs[section.id]?.splice(index, 1)
}

function initDraft(): void {
  draft.value = clone(props.data ?? {})
  summary.value = props.summary ?? ''
  for (const section of props.template.sections) {
    if (!(section.id in draft.value)) {
      draft.value[section.id] =
        section.kind === 'table' || section.kind === 'list' ? [] : {}
    }
    if (section.kind === 'key_value') {
      const object = draft.value[section.id] ?? {}
      kvPairs[section.id] = Object.entries(object).map(([key, value]) => ({
        key,
        value: typeof value === 'string' ? value : String(value ?? ''),
      }))
    }
  }
}

function handleSave(): void {
  const data = clone(draft.value)
  for (const section of props.template.sections) {
    if (section.kind === 'key_value') {
      const pairs = (kvPairs[section.id] ?? []).filter((pair) => pair.key.trim())
      data[section.id] = Object.fromEntries(
        pairs.map((pair) => [pair.key.trim(), pair.value]),
      )
    }
  }
  emit('save', data, summary.value)
}

onMounted(initDraft)
</script>

<template>
  <div class="re-editor">
    <template v-for="section in template.sections" :key="section.id">
      <section class="re-section">
        <header class="re-section-head">
          <span class="re-accent" />
          <div class="re-section-title">
            <h3>{{ section.title }}</h3>
            <p v-if="section.subtitle">{{ section.subtitle }}</p>
          </div>
        </header>

        <div v-if="section.kind === 'grid'" class="re-grid">
          <label v-for="field in section.fields" :key="field.key" class="re-field">
            <span>{{ field.label }}</span>
            <el-input-number
              v-if="field.type === 'number'"
              v-model="draft[section.id][field.key]"
              :controls="false"
              class="re-control"
              placeholder="未填写"
            />
            <el-switch
              v-else-if="field.type === 'boolean'"
              v-model="draft[section.id][field.key]"
            />
            <el-input
              v-else
              v-model="draft[section.id][field.key]"
              :type="field.type === 'money' || field.type === 'date' ? 'text' : 'text'"
              :placeholder="field.type === 'money' ? '例如：800 万元' : field.type === 'date' ? '例如：2026-08-20' : '未填写'"
              class="re-control"
            />
          </label>
        </div>

        <div v-else-if="section.kind === 'table'" class="re-table-editor">
          <div v-for="(row, rowIndex) in sectionRows(section)" :key="rowIndex" class="re-row-card">
            <div class="re-row-grid">
              <label
                v-for="column in section.columns"
                :key="column.key"
                class="re-field"
              >
                <span>{{ column.label }}</span>
                <el-switch
                  v-if="column.type === 'boolean'"
                  v-model="row[column.key]"
                />
                <el-input
                  v-else
                  v-model="row[column.key]"
                  :placeholder="column.label"
                  class="re-control"
                />
              </label>
              <label
                v-for="column in section.columns.filter(
                  (item) => item.variant === 'stack' && item.secondary_key,
                )"
                :key="`secondary-${column.secondary_key}`"
                class="re-field"
              >
                <span>{{ column.secondary_prefix || column.secondary_key }}</span>
                <el-input
                  v-model="row[column.secondary_key!]"
                  :placeholder="column.secondary_prefix || '原文'"
                  class="re-control"
                />
              </label>
            </div>
            <el-button
              text
              type="danger"
              :icon="Delete"
              class="re-row-delete"
              aria-label="删除该行"
              @click="removeRow(section, rowIndex)"
            >
              删除该行
            </el-button>
          </div>
          <el-button type="primary" plain :icon="Plus" @click="addRow(section)">
            添加一行
          </el-button>
        </div>

        <div v-else-if="section.kind === 'key_value'" class="re-kv">
          <div v-for="(pair, index) in kvPairs[section.id] ?? []" :key="index" class="re-kv-row">
            <el-input v-model="pair.key" placeholder="维度名" class="re-kv-key" />
            <el-input v-model="pair.value" placeholder="内容" class="re-kv-value" />
            <el-button
              text
              type="danger"
              :icon="Delete"
              aria-label="删除维度"
              @click="removeKv(section, index)"
            />
          </div>
          <el-button type="primary" plain :icon="Plus" @click="addKv(section)">
            添加维度
          </el-button>
        </div>

        <div v-else class="re-list-editor">
          <div v-for="(item, index) in sectionItems(section)" :key="index" class="re-list-row">
            <el-input v-model="sectionItems(section)[index]" placeholder="内容" />
            <el-button
              text
              type="danger"
              :icon="Delete"
              aria-label="删除该项"
              @click="removeItem(section, index)"
            />
          </div>
          <el-button type="primary" plain :icon="Plus" @click="addItem(section)">
            添加一项
          </el-button>
        </div>
      </section>
    </template>

    <section class="re-section">
      <header class="re-section-head">
        <span class="re-accent" />
        <div class="re-section-title">
          <h3>原始摘要</h3>
          <p>LLM 生成的摘要，可修改</p>
        </div>
      </header>
      <el-input
        v-model="summary"
        type="textarea"
        :rows="3"
        maxlength="4000"
        class="re-control"
        placeholder="可填写或修改原始摘要"
      />
    </section>

    <footer class="re-footer">
      <el-button type="primary" @click="handleSave">保存修正</el-button>
    </footer>
  </div>
</template>

<style scoped>
.re-editor {
  display: grid;
  gap: 0;
}

.re-section {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
}

.re-section:last-child {
  border-bottom: 0;
}

.re-section-head {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.re-accent {
  width: 3px;
  height: 34px;
  flex: 0 0 auto;
  margin-top: 1px;
  border-radius: 2px;
  background: var(--primary-color);
}

.re-section-title h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}

.re-section-title p {
  margin: 3px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
}

.re-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.re-field {
  display: grid;
  min-width: 0;
  gap: 7px;
}

.re-field > span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.re-control {
  width: 100%;
}

.re-table-editor,
.re-kv,
.re-list-editor {
  display: grid;
  gap: 10px;
}

.re-row-card {
  position: relative;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: var(--surface-muted);
}

.re-row-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding-right: 96px;
}

.re-row-delete {
  position: absolute;
  top: 10px;
  right: 8px;
}

.re-kv-row,
.re-list-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.re-kv-key {
  width: 220px;
}

.re-kv-value {
  flex: 1;
}

.re-list-row > .el-input {
  flex: 1;
}

.re-footer {
  display: flex;
  justify-content: flex-end;
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
  background: var(--surface-muted);
}

@media (max-width: 1100px) {
  .re-grid,
  .re-row-grid {
    grid-template-columns: 1fr;
  }

  .re-row-grid {
    padding-right: 0;
  }
}
</style>
