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
  FieldDefinition,
  FieldType,
  ParseTemplate,
  SectionDefinition,
} from '@/types/results'
import { formatValue } from '@/utils/format'

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const props = defineProps<{
  template: ParseTemplate | null
  data: Record<string, unknown> | null
  summary?: string | null
  confidence?: number | null
  generatedAt?: string | null
  locate?: (text: string) => void
}>()

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

const sections = computed(() => props.template?.sections ?? [])

function sectionIcon(section: SectionDefinition): Component {
  return (section.icon && iconRegistry[section.icon]) || kindFallback[section.kind]
}

function toneClass(section: SectionDefinition): string {
  return `rv-tone-${section.tone ?? 'default'}`
}

function sectionObject(section: SectionDefinition): Record<string, unknown> | null {
  const value = props.data?.[section.id]
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function sectionRows(section: SectionDefinition): Record<string, unknown>[] {
  const value = props.data?.[section.id]
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : []
}

function sectionEntries(section: SectionDefinition): [string, unknown][] {
  return Object.entries(sectionObject(section) ?? {})
}

function sectionItems(section: SectionDefinition): string[] {
  const value = props.data?.[section.id]
  return Array.isArray(value)
    ? (value as unknown[]).filter((item): item is string => typeof item === 'string')
    : []
}

function sectionCount(section: SectionDefinition): number | null {
  if (section.kind === 'table') return sectionRows(section).length
  if (section.kind === 'list') return sectionItems(section).length
  if (section.kind === 'key_value') return sectionEntries(section).length
  return null
}

function isEmpty(value: unknown): boolean {
  return value === null || value === undefined || value === ''
}

function fieldValue(section: SectionDefinition, field: FieldDefinition): unknown {
  return sectionObject(section)?.[field.key] ?? null
}

function renderField(field: FieldDefinition, value: unknown): string {
  void field
  return isEmpty(value) ? '-' : formatValue(value)
}

function isNumeric(type: FieldType): boolean {
  return type === 'number' || type === 'money'
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

function tagInfo(column: ColumnDefinition, value: unknown): { label: string; type: TagType } {
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

const gridColumns = { xs: 1, sm: 1, md: 2, lg: 3 }
</script>

<template>
  <div v-if="template && data" class="rv-viewer">
    <div v-if="generatedAt || confidence !== null && confidence !== undefined" class="rv-meta">
      <span v-if="generatedAt">结构化结果生成于 {{ generatedAt }}</span>
      <el-tag v-if="confidence !== null && confidence !== undefined" type="success" effect="plain">
        置信度 {{ Math.round(confidence * 100) }}%
      </el-tag>
    </div>

    <template v-for="(section, index) in sections" :key="section.id">
      <section class="rv-section" :class="toneClass(section)">
        <header class="rv-section-head">
          <span class="rv-accent" />
          <el-icon class="rv-section-icon">
            <component :is="sectionIcon(section)" />
          </el-icon>
          <div class="rv-section-title">
            <h3>{{ section.title }}</h3>
            <p v-if="section.subtitle">{{ section.subtitle }}</p>
          </div>
          <el-tag v-if="sectionCount(section) !== null" class="rv-count" size="small" effect="plain">
            {{ sectionCount(section) }} 项
          </el-tag>
        </header>

        <div v-if="section.kind === 'grid'">
          <el-descriptions :column="gridColumns" border class="rv-descriptions">
            <el-descriptions-item
              v-for="field in section.fields"
              :key="field.key"
              :label="field.label"
            >
              <span
                class="rv-value"
                :class="{
                  'rv-empty': isEmpty(fieldValue(section, field)),
                  'rv-num': isNumeric(field.type),
                }"
              >
                {{ renderField(field, fieldValue(section, field)) }}
              </span>
            </el-descriptions-item>
          </el-descriptions>
          <div v-if="index === 0 && summary" class="rv-summary">
            <el-icon><Document /></el-icon>
            <p>{{ summary }}</p>
          </div>
        </div>

        <el-table
          v-else-if="section.kind === 'table'"
          :data="sectionRows(section)"
          stripe
          class="rv-table"
        >
          <el-table-column
            v-for="column in section.columns"
            :key="column.key"
            :label="column.label"
            :width="column.width ?? undefined"
            :min-width="column.min_width ?? undefined"
          >
            <template #default="scope">
              <span v-if="column.variant === 'stack'" class="rv-stack">
                <span>{{ formatValue(columnValue(scope.row, column)) }}</span>
                <small v-if="stackSecondary(scope.row, column)" class="rv-stack-secondary">
                  <span>
                    {{ column.secondary_prefix ? `${column.secondary_prefix}：` : '' }}
                    {{ stackSecondary(scope.row, column) }}
                  </span>
                  <button
                    v-if="locate"
                    type="button"
                    class="rv-locate"
                    @click="locate(stackSecondary(scope.row, column) as string)"
                  >
                    定位原文
                  </button>
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
              <small v-else-if="column.variant === 'muted'" class="rv-muted">
                {{ formatValue(columnValue(scope.row, column)) }}
              </small>
              <span
                v-else
                class="rv-value"
                :class="{
                  'rv-empty': isEmpty(columnValue(scope.row, column)),
                  'rv-num': isNumeric(column.type),
                }"
              >
                {{ formatValue(columnValue(scope.row, column)) }}
              </span>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="`暂无${section.title}`" :image-size="64" />
          </template>
        </el-table>

        <div v-else-if="section.kind === 'key_value'" class="rv-kv">
          <div v-for="([key, value]) in sectionEntries(section)" :key="key" class="rv-kv-row">
            <span>{{ key }}</span>
            <strong class="rv-kv-value">{{ formatValue(value) }}</strong>
          </div>
          <el-empty
            v-if="!sectionEntries(section).length"
            :description="`暂无${section.title}`"
            :image-size="60"
          />
        </div>

        <template v-else>
          <ul v-if="sectionItems(section).length" class="rv-list" :class="toneClass(section)">
            <li v-for="item in sectionItems(section)" :key="item">
              <el-icon v-if="section.tone === 'danger'"><WarningFilled /></el-icon>
              <span>{{ item }}</span>
            </li>
          </ul>
          <el-empty v-else :description="`暂无${section.title}`" :image-size="60" />
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.rv-viewer {
  display: grid;
}

.rv-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 24px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-tertiary);
  font-size: 12px;
}

.rv-section {
  position: relative;
  padding: 22px 24px 24px;
  border-bottom: 1px solid var(--border-color);
}

.rv-section:last-child {
  border-bottom: 0;
}

.rv-section-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
}

.rv-accent {
  width: 3px;
  height: 36px;
  flex: 0 0 auto;
  margin-top: 1px;
  border-radius: 2px;
  background: var(--border-strong);
}

.rv-section-icon {
  margin-top: 2px;
  font-size: 18px;
  color: var(--border-strong);
}

.rv-section-title {
  min-width: 0;
  flex: 1;
}

.rv-section-title h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
}

.rv-section-title p {
  margin: 3px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.5;
}

.rv-count {
  margin-top: 1px;
}

.rv-tone-primary .rv-accent {
  background: var(--primary-color);
}

.rv-tone-primary .rv-section-icon {
  color: var(--primary-color);
}

.rv-tone-warning .rv-accent {
  background: var(--warning-color);
}

.rv-tone-warning .rv-section-icon {
  color: var(--warning-color);
}

.rv-tone-danger .rv-accent {
  background: var(--danger-color);
}

.rv-tone-danger .rv-section-icon {
  color: var(--danger-color);
}

.rv-tone-info .rv-accent {
  background: var(--info-color);
}

.rv-tone-info .rv-section-icon {
  color: var(--info-color);
}

.rv-tone-success .rv-accent {
  background: var(--success-color);
}

.rv-tone-success .rv-section-icon {
  color: var(--success-color);
}

.rv-descriptions {
  width: 100%;
}

.rv-descriptions :deep(.el-descriptions__label) {
  width: 104px;
  color: var(--text-secondary);
  font-size: 12px;
}

.rv-descriptions :deep(.el-descriptions__content) {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
}

.rv-value {
  color: var(--text-primary);
  font-weight: 500;
  overflow-wrap: anywhere;
}

.rv-value.rv-empty {
  color: var(--text-tertiary);
  font-weight: 400;
}

.rv-num {
  font-variant-numeric: tabular-nums;
}

.rv-summary {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 16px;
  padding: 14px 16px;
  border-left: 3px solid var(--primary-color);
  background: var(--primary-soft);
  color: var(--text-secondary);
}

.rv-summary .el-icon {
  flex: 0 0 auto;
  margin-top: 3px;
  color: var(--primary-color);
}

.rv-summary p {
  margin: 0;
  line-height: 1.75;
}

.rv-stack span,
.rv-stack small {
  display: block;
}

.rv-stack span {
  color: var(--text-primary);
  line-height: 1.6;
}

.rv-stack-secondary {
  display: flex;
  margin-top: 5px;
  gap: 8px;
  align-items: flex-start;
}

.rv-stack-secondary > span {
  color: var(--text-tertiary);
  line-height: 1.5;
}

.rv-locate {
  flex: 0 0 auto;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--primary-color);
  cursor: pointer;
  font-size: 11px;
  line-height: 1.5;
}

.rv-locate:hover {
  text-decoration: underline;
}

.rv-muted {
  color: var(--text-tertiary);
  line-height: 1.5;
}

.rv-kv {
  border-top: 1px solid var(--border-color);
}

.rv-kv-row {
  display: grid;
  grid-template-columns: minmax(100px, 0.42fr) minmax(0, 1fr);
  gap: 16px;
  padding: 11px 0;
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  line-height: 1.6;
}

.rv-kv-row span {
  color: var(--text-tertiary);
}

.rv-kv-value {
  color: var(--text-primary);
  font-weight: 500;
  overflow-wrap: anywhere;
  text-align: right;
}

.rv-list {
  display: grid;
  gap: 9px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.rv-list li {
  position: relative;
  display: flex;
  gap: 9px;
  align-items: flex-start;
  padding: 11px 12px 11px 30px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}

.rv-list li::before {
  position: absolute;
  top: 18px;
  left: 14px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--border-strong);
  content: '';
}

.rv-tone-primary .rv-list li::before {
  background: var(--primary-color);
}

.rv-tone-warning .rv-list li::before {
  background: var(--warning-color);
}

.rv-tone-danger .rv-list li::before {
  background: var(--danger-color);
}

.rv-tone-info .rv-list li::before {
  background: var(--info-color);
}

.rv-tone-success .rv-list li::before {
  background: var(--success-color);
}

.rv-list.rv-tone-danger li {
  padding-left: 12px;
  border-color: #f2d0cc;
  background: #fffafa;
}

.rv-list.rv-tone-danger li::before {
  display: none;
}

.rv-list .el-icon {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--danger-color);
}

@media (max-width: 1120px) {
  .rv-kv-row {
    grid-template-columns: 1fr;
    gap: 2px;
  }

  .rv-kv-value {
    text-align: left;
  }
}

@media (prefers-reduced-motion: reduce) {
  .rv-viewer * {
    animation: none;
  }
}
</style>
