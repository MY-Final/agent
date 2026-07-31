export interface LlmUsageStats {
  total_calls: number
  success_calls: number
  failed_calls: number
  total_tokens: number
  total_cost: string
  avg_latency_ms: number | null
}

export interface PurposeUsageStats {
  purpose: string
  calls: number
  success_calls: number
  total_tokens: number
  total_cost: string
}

export interface ModelUsageStats {
  model: string
  calls: number
  total_tokens: number
  total_cost: string
}

export interface TaskCostStats {
  task_id: string
  task_name: string
  calls: number
  total_tokens: number
  total_cost: string
}

export interface DailyUsageStats {
  date: string
  calls: number
  total_tokens: number
  total_cost: string
}

export interface TaskFlowStats {
  total_runs: number
  completed_runs: number
  failed_runs: number
  success_rate: number | null
  avg_duration_seconds: number | null
}

export interface StatsSummary {
  llm: LlmUsageStats
  tasks: TaskFlowStats
  by_purpose: PurposeUsageStats[]
  by_model: ModelUsageStats[]
  by_task: TaskCostStats[]
  daily: DailyUsageStats[]
}
