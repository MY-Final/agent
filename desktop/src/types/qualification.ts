export type CertificateStatus = 'valid' | 'expired' | 'revoked'

export interface QualificationCertificate {
  id: string
  name: string
  level: string | null
  specialty: string | null
  cert_number: string | null
  issuing_authority: string | null
  valid_from: string | null
  valid_to: string | null
  status: CertificateStatus
  is_currently_valid: boolean
  file_object_key: string | null
  remark: string | null
  created_at: string
  updated_at: string
}

export interface PerformanceRecord {
  id: string
  project_name: string
  project_amount: string | null
  currency: string
  start_date: string | null
  end_date: string | null
  is_completed: boolean
  owner_name: string | null
  location: string | null
  related_qualification: string | null
  description: string | null
  file_object_key: string | null
  created_at: string
  updated_at: string
}

export interface PersonnelCertificate {
  id: string
  person_name: string
  cert_type: string
  specialty: string | null
  cert_number: string | null
  valid_from: string | null
  valid_to: string | null
  is_on_job: boolean
  is_currently_valid: boolean
  file_object_key: string | null
  remark: string | null
  created_at: string
  updated_at: string
}

export interface CompanyProfile {
  id: string
  company_name: string
  legal_person: string | null
  registered_capital: string | null
  establish_date: string | null
  address: string | null
  contact_info: string | null
  extra_info: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface CertificateInput {
  name: string
  level?: string | null
  specialty?: string | null
  cert_number?: string | null
  issuing_authority?: string | null
  valid_from?: string | null
  valid_to?: string | null
  status?: CertificateStatus
  remark?: string | null
}

export interface PerformanceInput {
  project_name: string
  project_amount?: number | string | null
  currency?: string
  start_date?: string | null
  end_date?: string | null
  is_completed?: boolean
  owner_name?: string | null
  location?: string | null
  related_qualification?: string | null
  description?: string | null
}

export interface PersonnelInput {
  person_name: string
  cert_type: string
  specialty?: string | null
  cert_number?: string | null
  valid_from?: string | null
  valid_to?: string | null
  is_on_job?: boolean
  remark?: string | null
}

export interface CompanyInput {
  company_name: string
  legal_person?: string | null
  registered_capital?: number | string | null
  establish_date?: string | null
  address?: string | null
  contact_info?: string | null
}

export interface ExpiryWarningItem {
  id: string
  kind: 'certificate' | 'personnel'
  title: string
  detail: string
  valid_to: string | null
  days_left: number | null
  status: 'expiring' | 'expired' | 'revoked' | 'off_job'
}

export interface ExpiryWarnings {
  items: ExpiryWarningItem[]
  expired_count: number
  expiring_count: number
}

export interface QualificationImportResult {
  created: number
  failed: number
  errors: string[]
}
