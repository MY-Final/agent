export type FieldType = 'text' | 'number' | 'money' | 'date' | 'boolean'
export type SectionKind = 'grid' | 'table' | 'key_value' | 'list'
export type SectionTone = 'default' | 'primary' | 'warning' | 'danger' | 'success' | 'info'
export type ColumnVariant = 'text' | 'muted' | 'stack' | 'tag'

export interface FieldDefinition {
  key: string
  label: string
  type: FieldType
  required?: boolean
}

export interface ColumnDefinition {
  key: string
  label: string
  type: FieldType
  required?: boolean
  variant?: ColumnVariant
  secondary_key?: string | null
  secondary_prefix?: string | null
  truthy_label?: string | null
  falsy_label?: string | null
  truthy_tag?: string | null
  falsy_tag?: string | null
  width?: number | null
  min_width?: number | null
}

export interface SectionDefinition {
  id: string
  title: string
  subtitle?: string | null
  kind: SectionKind
  tone?: SectionTone
  icon?: string | null
  fields?: FieldDefinition[]
  columns?: ColumnDefinition[]
}

export interface ParseTemplate {
  version: string
  sections: SectionDefinition[]
}

export interface ParseResult {
  template: ParseTemplate
  data: Record<string, unknown>
  raw_summary: string | null
  confidence: number | null
}

export interface ParseResultRecord {
  id: string
  task_id: string | null
  file_id: string | null
  source_object_keys: string[]
  template_id: string | null
  template_version: string | null
  is_rejected: boolean
  reject_reason: string | null
  status: 'success' | 'failed'
  result: ParseResult | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ParseSourceTextItem {
  filename: string
  extraction_method: string | null
  text: string
}

export type RiskLevel = 'none' | 'low' | 'medium' | 'high'

export interface MatchItem {
  category: string
  requirement: string
  company_status: string
  is_matched: boolean
  risk_level: RiskLevel
  comment: string | null
}

export interface MatchReport {
  overall_match_score: number | null
  summary: string
  matched_items: MatchItem[]
  missing_items: MatchItem[]
  risk_items: MatchItem[]
  suggestions: string[]
}

export interface MatchResultRecord {
  id: string
  task_id: string | null
  parse_result_id: string | null
  status: 'success' | 'failed'
  result: MatchReport | null
  error_message: string | null
  created_at: string
  updated_at: string
}
