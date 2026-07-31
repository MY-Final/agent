import type { ExpiryWarningItem } from './qualification'
import type { TaskStatus } from './task'

export interface DashboardTaskCounts {
  total: number
  running: number
  waiting_confirm: number
  completed: number
  failed: number
}

export interface DashboardRecentTask {
  id: string
  project_name: string
  status: TaskStatus
  created_at: string
  file_count: number
}

export interface DashboardPendingTask {
  id: string
  project_name: string
  created_at: string
}

export interface DashboardSummary {
  task_counts: DashboardTaskCounts
  pending_confirm_tasks: DashboardPendingTask[]
  warnings: ExpiryWarningItem[]
  warning_expired: number
  warning_expiring: number
  recent_tasks: DashboardRecentTask[]
}
