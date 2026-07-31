import { ref } from 'vue'
import { defineStore } from 'pinia'
import { taskApi } from '@/api/tasks'
import type { TaskListItem, TaskStatus } from '@/types/task'

export const useTasksStore = defineStore('tasks', () => {
  const items = ref<TaskListItem[]>([])
  const total = ref(0)
  const loading = ref(false)

  async function fetchTasks(status?: TaskStatus, keyword?: string): Promise<void> {
    loading.value = true
    try {
      const result = await taskApi.list({
        page: 1,
        page_size: 100,
        status,
        keyword: keyword?.trim() || undefined,
      })
      items.value = result.items
      total.value = result.total
    } finally {
      loading.value = false
    }
  }

  return { items, total, loading, fetchTasks }
})
