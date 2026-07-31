export type TaskStatus =
  | 'created'
  | 'parsing'
  | 'analyzing'
  | 'waiting_confirm'
  | 'generating'
  | 'completed'
  | 'failed'

export interface TaskFile {
  id: string
  task_id: string
  original_filename: string
  object_key: string
  file_size: number
  content_type: string
  uploaded_at: string
}

export interface TaskListItem {
  id: string
  project_name: string
  remark: string | null
  source: string | null
  status: TaskStatus
  created_at: string
  updated_at: string
  file_count: number
}

export interface TaskDetail extends Omit<TaskListItem, 'file_count'> {
  parse_template_id: string | null
  files: TaskFile[]
}

export interface TaskListData {
  items: TaskListItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface TaskCreateInput {
  project_name: string
  remark?: string | null
  source?: string | null
  parse_template_id?: string | null
}

export interface DownloadUrlData {
  url: string
  expires_in: number
  filename: string
}
