<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheckFilled, CircleCloseFilled, WarningFilled } from '@element-plus/icons-vue'
import type { MatchItem, MatchResultRecord, RiskLevel } from '@/types/results'
import { formatDate } from '@/utils/format'

const props = defineProps<{
  record: MatchResultRecord | null
  loading?: boolean
}>()

const result = computed(() => props.record?.result ?? null)

const riskLabel: Record<RiskLevel, string> = {
  none: '无风险',
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

function riskType(level: RiskLevel): 'success' | 'info' | 'warning' | 'danger' {
  return { none: 'success', low: 'info', medium: 'warning', high: 'danger' }[level] as
    | 'success'
    | 'info'
    | 'warning'
    | 'danger'
}

interface MatchGroup {
  key: 'matched_items' | 'missing_items' | 'risk_items'
  label: string
  description: string
  icon: typeof CircleCheckFilled
  tone: string
  items: MatchItem[]
}

const groups = computed<MatchGroup[]>(() => [
  {
    key: 'matched_items',
    label: '已满足',
    description: '公司现有资料能够明确覆盖的要求',
    icon: CircleCheckFilled,
    tone: 'matched',
    items: result.value?.matched_items ?? [],
  },
  {
    key: 'missing_items',
    label: '缺失项',
    description: '当前知识库中未找到满足条件的资料',
    icon: CircleCloseFilled,
    tone: 'missing',
    items: result.value?.missing_items ?? [],
  },
  {
    key: 'risk_items',
    label: '风险项',
    description: '有效期、金额或关键词处于边界的要求',
    icon: WarningFilled,
    tone: 'risk',
    items: result.value?.risk_items ?? [],
  },
])
</script>

<template>
  <div v-loading="loading" class="result-panel">
    <template v-if="record?.status === 'failed'">
      <el-alert
        title="资质匹配失败"
        :description="record.error_message || '未记录具体错误，请查看后端日志。'"
        type="error"
        :closable="false"
        show-icon
      />
    </template>

    <template v-else-if="result">
      <section class="match-summary">
        <div class="score-block">
          <span class="score-label">综合匹配度</span>
          <strong>{{ result.overall_match_score === null ? '-' : Math.round(result.overall_match_score) }}</strong>
          <span v-if="result.overall_match_score !== null" class="score-unit">/ 100</span>
        </div>
        <div class="summary-block">
          <span>匹配结论</span>
          <p>{{ result.summary }}</p>
          <small>生成于 {{ formatDate(record?.created_at) }}</small>
        </div>
        <div class="metric-strip">
          <div><strong>{{ result.matched_items.length }}</strong><span>已满足</span></div>
          <div><strong>{{ result.missing_items.length }}</strong><span>缺失</span></div>
          <div><strong>{{ result.risk_items.length }}</strong><span>风险</span></div>
        </div>
      </section>

      <section v-for="group in groups" :key="group.key" class="result-section">
        <div class="section-heading">
          <div class="group-title" :class="group.tone">
            <el-icon><component :is="group.icon" /></el-icon>
            <div>
              <h3 class="section-title">{{ group.label }}</h3>
              <p class="section-subtitle">{{ group.description }}</p>
            </div>
          </div>
          <el-tag effect="plain">{{ group.items.length }} 项</el-tag>
        </div>

        <el-table v-if="group.items.length" :data="group.items" stripe>
          <el-table-column prop="category" label="类别" width="100" />
          <el-table-column prop="requirement" label="招标要求" min-width="250" />
          <el-table-column prop="company_status" label="公司现状" min-width="250" />
          <el-table-column label="风险" width="100" align="center">
            <template #default="scope">
              <el-tag :type="riskType(scope.row.risk_level)" effect="plain" size="small">
                {{ riskLabel[scope.row.risk_level as RiskLevel] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="comment" label="说明" min-width="180">
            <template #default="scope">{{ scope.row.comment || '-' }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else :description="`暂无${group.label}`" :image-size="64" />
      </section>

      <section class="result-section suggestions-section">
        <div class="section-heading">
          <div>
            <h3 class="section-title">处理建议</h3>
            <p class="section-subtitle">基于当前知识库匹配结果给出的后续动作</p>
          </div>
        </div>
        <ol v-if="result.suggestions.length" class="suggestion-list">
          <li v-for="(item, index) in result.suggestions" :key="item">
            <span>{{ index + 1 }}</span>
            <p>{{ item }}</p>
          </li>
        </ol>
        <el-empty v-else description="暂无处理建议" :image-size="64" />
      </section>
    </template>

    <div v-else class="empty-block">
      <el-empty description="确认解析结果并完成匹配后，这里将展示报告" :image-size="88" />
    </div>
  </div>
</template>

<style scoped>
.result-panel {
  min-height: 360px;
}

.match-summary {
  display: grid;
  grid-template-columns: 170px minmax(0, 1fr) 260px;
  min-height: 150px;
  border-bottom: 1px solid var(--border-color);
  background: #fbfcfb;
}

.score-block,
.summary-block,
.metric-strip {
  display: flex;
  align-items: center;
  padding: 24px;
}

.score-block {
  position: relative;
  flex-direction: column;
  justify-content: center;
  border-right: 1px solid var(--border-color);
}

.score-label {
  color: var(--text-tertiary);
  font-size: 12px;
}

.score-block strong {
  margin-top: 5px;
  color: var(--primary-color);
  font-family: "Segoe UI", sans-serif;
  font-size: 42px;
  font-weight: 700;
  line-height: 1;
}

.score-unit {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.summary-block {
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
}

.summary-block > span {
  color: var(--text-tertiary);
  font-size: 12px;
}

.summary-block p {
  margin: 7px 0 5px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
  line-height: 1.7;
}

.summary-block small {
  color: var(--text-tertiary);
}

.metric-strip {
  justify-content: space-between;
  border-left: 1px solid var(--border-color);
}

.metric-strip div {
  display: grid;
  min-width: 64px;
  gap: 4px;
  text-align: center;
}

.metric-strip strong {
  color: var(--text-primary);
  font-size: 22px;
}

.metric-strip span {
  color: var(--text-tertiary);
  font-size: 11px;
}

.result-section {
  padding: 24px;
  border-bottom: 1px solid var(--border-color);
}

.result-section:last-child {
  border-bottom: 0;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
}

.group-title {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.group-title > .el-icon {
  margin-top: 2px;
  font-size: 19px;
}

.group-title.matched > .el-icon {
  color: var(--success-color);
}

.group-title.missing > .el-icon {
  color: var(--danger-color);
}

.group-title.risk > .el-icon {
  color: var(--warning-color);
}

.suggestion-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.suggestion-list li {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--surface-muted);
}

.suggestion-list span {
  display: grid;
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: var(--primary-soft);
  color: var(--primary-dark);
  font-size: 11px;
  font-weight: 700;
}

.suggestion-list p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 1200px) {
  .match-summary {
    grid-template-columns: 150px minmax(0, 1fr);
  }

  .metric-strip {
    grid-column: 1 / -1;
    min-height: 80px;
    justify-content: flex-start;
    gap: 50px;
    border-top: 1px solid var(--border-color);
    border-left: 0;
  }
}
</style>
