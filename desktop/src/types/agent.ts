import type { TaskStatus } from './task'

export type AgentStep =
  | 'parse'
  | 'wait_confirm'
  | 'match'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type AgentRunStatus =
  | 'running'
  | 'waiting_confirm'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface AgentParseSummary {
  project_name: string | null
  project_code: string | null
  budget: string | null
  qualification_count: number
  raw_summary: string | null
}

export interface AgentMatchSummary {
  overall_match_score: number | null
  summary: string
  matched_count: number
  missing_count: number
  risk_count: number
}

export interface AgentStatus {
  run_id: string
  task_id: string
  thread_id: string
  current_step: AgentStep
  status: AgentRunStatus
  task_status: TaskStatus
  is_waiting_confirmation: boolean
  user_confirmed: boolean
  confirmation_note: string | null
  parse_result_id: string | null
  match_result_id: string | null
  parse_summary: AgentParseSummary | null
  match_summary: AgentMatchSummary | null
  error_message: string | null
  extra: Record<string, unknown>
  started_at: string
  completed_at: string | null
  created_at: string
  updated_at: string
}
