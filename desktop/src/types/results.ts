export interface QualificationItem {
  category: string
  description: string
  is_mandatory: boolean
  original_text: string | null
}

export interface ParseResult {
  project_name: string | null
  project_code: string | null
  budget: string | null
  duration: string | null
  location: string | null
  purchaser: string | null
  qualifications: QualificationItem[]
  scoring_method: Record<string, unknown>
  disqualification_items: string[]
  key_dates: Record<string, unknown>
  other_key_points: string[]
  raw_summary: string | null
  confidence: number | null
}

export interface ParseResultRecord {
  id: string
  task_id: string | null
  file_id: string | null
  source_object_keys: string[]
  status: 'success' | 'failed'
  result: ParseResult | null
  error_message: string | null
  created_at: string
  updated_at: string
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
