<script setup lang="ts">
import { computed } from 'vue'
import type { TagProps } from 'element-plus'
import type { TaskStatus } from '@/types/task'

const props = defineProps<{
  status: TaskStatus | string
}>()

const statusMap: Record<string, { label: string; type: TagProps['type']; effect: TagProps['effect'] }> = {
  created: { label: '待分析', type: 'info', effect: 'plain' },
  parsing: { label: '解析中', type: 'primary', effect: 'light' },
  analyzing: { label: '匹配中', type: 'primary', effect: 'light' },
  waiting_confirm: { label: '待确认', type: 'warning', effect: 'light' },
  generating: { label: '生成中', type: 'primary', effect: 'light' },
  completed: { label: '已完成', type: 'success', effect: 'light' },
  failed: { label: '失败', type: 'danger', effect: 'light' },
  running: { label: '运行中', type: 'primary', effect: 'light' },
  cancelled: { label: '已取消', type: 'info', effect: 'plain' },
}

const meta = computed(() => statusMap[props.status] ?? {
  label: props.status,
  type: 'info' as const,
  effect: 'plain' as const,
})
</script>

<template>
  <el-tag :type="meta.type" :effect="meta.effect" size="small" round>
    <span v-if="status === 'parsing' || status === 'analyzing' || status === 'generating' || status === 'running'" class="status-dot" />
    {{ meta.label }}
  </el-tag>
</template>

<style scoped>
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 5px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  50% {
    opacity: 0.35;
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-dot {
    animation: none;
  }
}
</style>
