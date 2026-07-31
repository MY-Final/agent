<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import {
  Calendar,
  Collection,
  DataLine,
  Document,
  List,
  Memo,
  Tickets,
  WarningFilled,
} from '@element-plus/icons-vue'
import type {
  ColumnDefinition,
  ParseResultRecord,
  SectionDefinition,
} from '@/types/results'
import { formatDate, formatValue } from '@/utils/format'

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const props = defineProps<{
  records: ParseResultRecord[]
}>()

const base = computed(() => props.records[0])

const iconRegistry: Record<string, Component> = {
  Memo,
  Collection,
  Tickets,
  Calendar,
  WarningFilled,
  List,
  Document,
  DataLine,
}

const kindFallback: Record<SectionDefinition['kind'], Component> = {
  grid: Memo,
  table: Collection,
  key_value: Tickets,
  list: List,
}

const sections = computed<SectionDefinition[]>(() => {
  const seen = new Set<string>()
  const result: SectionDefinition[] = []
  for (const record of props.records) {
    for (const section of record.result?.template.sections ?? []) {
      if (!seen.has(section.id)) {
        seen.add(section.id)
        result.push(section)
      }
    }
  }
  return result
})

function sectionIcon(section: SectionDefinition): Component {
  return (section.icon && iconRegistry[section.icon]) || kindFallback[section.kind]
}

function toneClass(section: SectionDefinition): string {
  return `cp-tone-${section.tone ?? 'default'}`
}

function recordSection(
  record: ParseResultRecord,
  sectionId: string,
): SectionDefinition | null {
  return record.result?.template.sections.find((item) => item.id === sectionId) ?? null
}

function sectionObject(
  record: ParseResultRecord,
  sectionId: string,
): Record<string, unknown> | null {
  const value = record.result?.data?.[sectionId]
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function sectionRows(
  record: ParseResultRecord,
  sectionId: string,
): Record<string, unknown>[] {
  const value = record.result?.data?.[sectionId]
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : []
}

function sectionItems(record: ParseResultRecord, sectionId: string): string[] {
  const value = record.result?.data?.[sectionId]
  return Array.isArray(value)
    ? (value as unknown[]).filter((item): item is string => typeof item === 'string')
    : []
}

function isEmpty(value: unknown): boolean {
  return value === null || value === undefined || value === ''
}

function cellText(value: unknown): string {
  return isEmpty(value) ? '-' : formatValue(value)
}

interface AlignedCell {
  text: string
  diff: boolean
}

interface AlignedRow {
  key: string
  label: string
  cells: Record<string, AlignedCell>
}

function makeAlignedRow(
  key: string,
  label: string,
  getter: (record: ParseResultRecord) => unknown,
): AlignedRow {
  const cells: Record<string, AlignedCell> = {}
  for (const record of props.records) {
    const raw = getter(record)
    const baseRaw = getter(base.value)
    cells[record.id] = {
      text: cellText(raw),
      diff:
        record.id !== base.value.id &&
        !isEmpty(baseRaw) &&
        cellText(raw) !== cellText(baseRaw),
    }
  }
  return { key, label, cells }
}

function alignedGridRows(section: SectionDefinition): AlignedRow[] {
  const keys: string[] = []
  for (const record of props.records) {
    const current = recordSection(record, section.id)
    for (const field of current?.fields ?? []) {
      if (!keys.includes(field.key)) keys.push(field.key)
    }
  }
  return keys.map((key) => {
    const label =
      props.records
        .map((record) =>
          recordSection(record, section.id)?.fields?.find(
            (field) => field.key === key,
          )?.label,
        )
        .find(Boolean) ?? key
    return makeAlignedRow(key, label, (record) =>
      sectionObject(record, section.id)?.[key],
    )
  })
}

function alignedKeyValueRows(section: SectionDefinition): AlignedRow[] {
  const keys: string[] = []
  for (const record of props.records) {
    const object = sectionObject(record, section.id)
    if (object) {
      for (const key of Object.keys(object)) {
        if (!keys.includes(key)) keys.push(key)
      }
    }
  }
  return keys.map((key) =>
    makeAlignedRow(key, key, (record) => sectionObject(record, section.id)?.[key]),
  )
}

interface ListRow {
  index: number
  cells: Record<string, AlignedCell>
}

function listRows(section: SectionDefinition): ListRow[] {
  const maxCount = Math.max(
    0,
    ...props.records.map((record) => sectionItems(record, section.id).length),
  )
  return Array.from({ length: maxCount }, (_, index) => {
    const cells: Record<string, AlignedCell> = {}
    for (const record of props.records) {
      const items = sectionItems(record, section.id)
      const baseItems = sectionItems(base.value, section.id)
      cells[record.id] = {
        text: items[index] || '-',
        diff:
          record.id !== base.value.id &&
          !isEmpty(baseItems[index] ?? null) &&
          (items[index] ?? '') !== (baseItems[index] ?? ''),
      }
    }
    return { index, cells }
  })
}

function columnLabel(record: ParseResultRecord): string {
  return `${record.template_version ?? '内置模板'} · ${formatDate(record.created_at)}`
}

function statusTag(record: ParseResultRecord): { label: string; type: TagType } {
  if (record.id === base.value.id) return { label: '基准', type: 'primary' }
  if (record.status === 'failed') return { label: '失败', type: 'danger' }
  if (record.is_rejected) return { label: '已驳回', type: 'warning' }
  return { label: '历史', type: 'info' }
}

function tableColumns(
  record: ParseResultRecord,
  sectionId: string,
): ColumnDefinition[] {
  return recordSection(record, sectionId)?.columns ?? []
}

function columnValue(row: Record<string, unknown>, column: ColumnDefinition): unknown {
  return row[column.key] ?? null
}

function stackSecondary(
  row: Record<string, unknown>,
  column: ColumnDefinition,
): string | null {
  if (!column.secondary_key) return null
  const value = row[column.secondary_key]
  return isEmpty(value) ? null : String(value)
}

function tagInfo(
  column: ColumnDefinition,
  value: unknown,
): { label: string; type: TagType } {
  if (typeof value === 'boolean') {
    return value
      ? {
          label: column.truthy_label || '是',
          type: (column.truthy_tag as TagType) || 'success',
        }
      : {
          label: column.falsy_label || '否',
          type: (column.falsy_tag as TagType) || 'info',
        }
  }
  return { label: formatValue(value), type: 'info' }
}
</script>

<template>
  <div class="cp-viewer">
    <div class="cp-summary">
      <span>{{ records.length }} 个版本参与对比</span>
      <small>黄色高亮表示与基准版本不同的值</small>
    </div>

    <template v-for="section in sections" :key="section.id">
      <section class="cp-section" :class="toneClass(section)">
        <header class="cp-section-head">
          <span class="cp-accent" />
          <el-icon class="cp-section-icon">
            <component :is="sectionIcon(section)" />
          </el-icon>
          <div class="cp-section-title">
            <h3>{{ section.title }}</h3>
            <p v-if="section.subtitle">{{ section.subtitle }}</p>
          </div>
        </header>

        <el-table
          v-if="section.kind === 'grid' || section.kind === 'key_value'"
          :data="section.kind === 'grid' ? alignedGridRows(section) : alignedKeyValueRows(section)"
          stripe
          border
          class="cp-table"
        >
          <el-table-column label="字段" min-width="170">
            <template #default="scope">
              <strong class="cp-key">{{ scope.row.label }}</strong>
            </template>
          </el-table-column>
          <el-table-column
            v-for="record in records"
            :key="record.id"
            :label="columnLabel(record)"
            min-width="200"
          >
            <template #default="scope">
              <span class="cp-value" :class="{ 'cp-diff': scope.row.cells[record.id]?.diff }">
                {{ scope.row.cells[record.id]?.text ?? '-' }}
              </span>
            </template>
          </el-table-column>
        </el-table>

        <el-table
          v-else-if="section.kind === 'list'"
          :data="listRows(section)"
          stripe
          border
          class="cp-table"
        >
          <el-table-column type="index" label="#" width="54" />
          <el-table-column
            v-for="record in records"
            :key="record.id"
            :label="columnLabel(record)"
            min-width="220"
          >
            <template #default="scope">
              <span class="cp-value" :class="{ 'cp-diff': scope.row.cells[record.id]?.diff }">
                {{ scope.row.cells[record.id]?.text }}
              </span>
            </template>
          </el-table-column>
        </el-table>

        <div
          v-else
          class="cp-tables"
          :style="{ gridTemplateColumns: `repeat(${records.length}, minmax(0, 1fr))` }"
        >
          <div v-for="record in records" :key="record.id" class="cp-table-col">
            <div class="cp-table-col-head">
              <span>{{ columnLabel(record) }}</span>
              <el-tag :type="statusTag(record).type" size="small" effect="plain">
                {{ statusTag(record).label }}
              </el-tag>
            </div>
            <template v-if="tableColumns(record, section.id).length">
              <el-table :data="sectionRows(record, section.id)" stripe border class="cp-table">
                <el-table-column
                  v-for="column in tableColumns(record, section.id)"
                  :key="column.key"
                  :label="column.label"
                  :width="column.width ?? undefined"
                  :min-width="column.min_width ?? undefined"
                >
                  <template #default="scope">
                    <span v-if="column.variant === 'stack'" class="cp-stack">
                      <span>{{ formatValue(columnValue(scope.row, column)) }}</span>
                      <small v-if="stackSecondary(scope.row, column)">
                        {{ column.secondary_prefix ? `${column.secondary_prefix}：` : '' }}
                        {{ stackSecondary(scope.row, column) }}
                      </small>
                    </span>
                    <el-tag
                      v-else-if="column.variant === 'tag'"
                      :type="tagInfo(column, columnValue(scope.row, column)).type"
                      effect="plain"
                      size="small"
                    >
                      {{ tagInfo(column, columnValue(scope.row, column)).label }}
                    </el-tag>
                    <small v-else-if="column.variant === 'muted'" class="cp-muted">
                      {{ formatValue(columnValue(scope.row, column)) }}
                    </small>
                    <span v-else>{{ formatValue(columnValue(scope.row, column)) }}</span>
                  </template>
                </el-table-column>
                <template #empty>
                  <el-empty :description="`暂无${section.title}`" :image-size="48" />
                </template>
              </el-table>
            </template>
            <el-empty
              v-else
              :description="`该版本无${section.title}`"
              :image-size="48"
            />
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.cp-viewer {
  display: grid;
}

.cp-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 11px 24px;
  border-bottom: 1px solid var(--border-color);
  background: var(--surface-muted);
  color: var(--text-secondary);
  font-size: 12px;
}

.cp-summary small {
  color: var(--text-tertiary);
}

.cp-section {
  position: relative;
  padding: 22px 24px 24px;
  border-bottom: 1px solid var(--border-color);
}

.cp-section:last-child {
  border-bottom: 0;
}

.cp-section-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
}

.cp-accent {
  width: 3px;
  height: 36px;
  flex: 0 0 auto;
  margin-top: 1px;
  border-radius: 2px;
  background: var(--border-strong);
}

.cp-section-icon {
  margin-top: 2px;
  font-size: 18px;
  color: var(--border-strong);
}

.cp-section-title {
  min-width: 0;
  flex: 1;
}

.cp-section-title h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
}

.cp-section-title p {
  margin: 3px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.5;
}

.cp-tone-primary .cp-accent {
  background: var(--primary-color);
}

.cp-tone-primary .cp-section-icon {
  color: var(--primary-color);
}

.cp-tone-warning .cp-accent {
  background: var(--warning-color);
}

.cp-tone-warning .cp-section-icon {
  color: var(--warning-color);
}

.cp-tone-danger .cp-accent {
  background: var(--danger-color);
}

.cp-tone-danger .cp-section-icon {
  color: var(--danger-color);
}

.cp-tone-info .cp-accent {
  background: var(--info-color);
}

.cp-tone-info .cp-section-icon {
  color: var(--info-color);
}

.cp-tone-success .cp-accent {
  background: var(--success-color);
}

.cp-tone-success .cp-section-icon {
  color: var(--success-color);
}

.cp-table {
  width: 100%;
}

.cp-key {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.cp-value {
  display: inline-block;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.cp-diff {
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--warning-soft);
  color: var(--warning-color);
  font-weight: 600;
}

.cp-stack span,
.cp-stack small {
  display: block;
}

.cp-stack span {
  color: var(--text-primary);
  line-height: 1.6;
}

.cp-stack small {
  margin-top: 4px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

.cp-muted {
  color: var(--text-tertiary);
}

.cp-tables {
  display: grid;
  gap: 0;
}

.cp-table-col {
  min-width: 0;
}

.cp-table-col + .cp-table-col {
  padding-left: 16px;
  border-left: 1px solid var(--border-color);
}

.cp-table-col:not(:last-child) {
  padding-right: 16px;
}

.cp-table-col-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 1280px) {
  .cp-tables {
    grid-template-columns: 1fr !important;
  }

  .cp-table-col + .cp-table-col {
    padding-top: 16px;
    padding-left: 0;
    border-top: 1px solid var(--border-color);
    border-left: 0;
  }
}
</style>
